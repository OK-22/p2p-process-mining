"""
Purchase-to-pay process mining + early-warning automation.

Run from the project folder:  python analyze.py

Reads data/sample.csv if it exists, otherwise loads data/BPI_Challenge_2019.xes,
takes a random sample of cases, and saves it as data/sample.csv for fast re-runs.

Outputs:
  results/summary.md      key numbers for the README
  results/alerts.csv      cases flagged by the early-warning rule (test split)
  docs/images/*.png       charts for the README
"""
import os

import matplotlib
import numpy as np
import pandas as pd

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

SRC = "data/BPI_Challenge_2019.xes"
SAMPLE_CSV = "data/sample.csv"
SAMPLE_N = 20000
CASE, ACT, TS = "case:concept:name", "concept:name", "time:timestamp"
MIN_TRANSITION_N = 50  # ignore rare transitions when learning thresholds
LATE_QUANTILE = 0.90   # "late" = slowest 10% of cases

os.makedirs("results", exist_ok=True)
os.makedirs("docs/images", exist_ok=True)
os.makedirs("data", exist_ok=True)


def load():
    if os.path.exists(SAMPLE_CSV):
        df = pd.read_csv(SAMPLE_CSV, usecols=[CASE, ACT, TS])
    else:
        import pm4py

        log = pm4py.read_xes(SRC)
        df = log if isinstance(log, pd.DataFrame) else pm4py.convert_to_dataframe(log)
        df = df[[CASE, ACT, TS]]
        n = df[CASE].nunique()
        ids = df[CASE].drop_duplicates().sample(min(SAMPLE_N, n), random_state=1)
        df = df[df[CASE].isin(ids)]
        df.to_csv(SAMPLE_CSV, index=False)
    df[TS] = pd.to_datetime(df[TS], utc=True, format="mixed")
    # stable sort keeps the original event order when timestamps tie
    return df.sort_values([CASE, TS], kind="stable").reset_index(drop=True)


df = load()
lines = []


def say(text=""):
    print(text)
    lines.append(text)


n_cases = df[CASE].nunique()
say("# Process mining results")
say()
say(f"Sample: {len(df):,} events across {n_cases:,} cases")

# ---------- 1. Case duration ----------
g = df.groupby(CASE)[TS]
dur = (g.max() - g.min()).dt.total_seconds() / 86400
say()
say("## Case duration (days)")
say(f"- Median: {dur.median():.1f}")
say(f"- 90th percentile: {dur.quantile(0.9):.1f}")
say(f"- Mean: {dur.mean():.1f}")

# ---------- 2. Variants ----------
variants = df.groupby(CASE)[ACT].apply(tuple)
vc = variants.value_counts()
say()
say("## Process variants")
say(f"- Distinct variants: {len(vc):,}")
say(f"- Top 10 variants cover {vc.head(10).sum() / n_cases:.1%} of cases")

# ---------- 3. Rework ----------
cnt = df.groupby([CASE, ACT]).size()
rew = cnt[cnt > 1].reset_index()
rework_ids = set(rew[CASE].unique())
case_df = pd.DataFrame({"dur": dur})
case_df["rework"] = case_df.index.isin(rework_ids)
by_rework = case_df.groupby("rework")["dur"].median()
rework_by_act = rew.groupby(ACT)[CASE].nunique().sort_values(ascending=False)
say()
say("## Rework (an activity repeated within a case)")
say(f"- Cases with rework: {len(rework_ids):,} ({len(rework_ids) / n_cases:.1%})")
if True in by_rework.index and False in by_rework.index:
    say(
        f"- Median duration with rework: {by_rework[True]:.1f} days "
        f"vs {by_rework[False]:.1f} days without "
        f"(difference {by_rework[True] - by_rework[False]:+.1f} days)"
    )
say("- Most repeated activities (cases affected):")
for act, c in rework_by_act.head(5).items():
    say(f"  - {act}: {c:,} cases ({c / n_cases:.1%})")

# ---------- 4. Where time is spent ----------
df["next_act"] = df.groupby(CASE)[ACT].shift(-1)
df["next_ts"] = df.groupby(CASE)[TS].shift(-1)
tr = df.dropna(subset=["next_act"]).copy()
tr["wait_days"] = (tr["next_ts"] - tr[TS]).dt.total_seconds() / 86400
tr["transition"] = tr[ACT] + " -> " + tr["next_act"]
tstats = tr.groupby("transition")["wait_days"].agg(
    n="count", mean="mean", p90=lambda s: s.quantile(0.9), total="sum"
)
tstats = tstats[tstats["n"] >= MIN_TRANSITION_N].sort_values("total", ascending=False)
say()
say("## Where the waiting time goes (top 5 transitions by total wait)")
for name, r in tstats.head(5).iterrows():
    say(f"- {name}: {int(r['n']):,} times, mean wait {r['mean']:.1f} days, 90th pct {r['p90']:.1f} days")

# ---------- 5. Early-warning automation (train/test split) ----------
rng = np.random.RandomState(1)
ids = case_df.index.to_numpy().copy()
rng.shuffle(ids)
cut = int(len(ids) * 0.7)
train, test = set(ids[:cut]), set(ids[cut:])

trn = tr[tr[CASE].isin(train)]
thr = trn.groupby("transition")["wait_days"].agg(n="count", p90=lambda s: s.quantile(0.9))
thr = thr[thr["n"] >= MIN_TRANSITION_N]["p90"]

late_cut = dur.loc[list(train)].quantile(LATE_QUANTILE)
test_ids = list(test)
is_late = dur.loc[test_ids] >= late_cut

tst = tr[tr[CASE].isin(test)].copy()
tst["thr"] = tst["transition"].map(thr)
tst["breach"] = tst["wait_days"] > tst["thr"]
br = tst[tst["breach"]].copy()
# the alert fires the moment a step has waited longer than its 90th-percentile time
br["flag_time"] = br[TS] + pd.to_timedelta(br["thr"], unit="D")
first = br.sort_values("flag_time").drop_duplicates(CASE).set_index(CASE)
case_end = df.groupby(CASE)[TS].max()
first["lead_days"] = (case_end.loc[first.index] - first["flag_time"]).dt.total_seconds() / 86400
first["late"] = first.index.map(is_late.to_dict()).astype(bool)

flagged = pd.Series(False, index=test_ids)
flagged.loc[first.index] = True
precision = is_late[flagged].mean() if flagged.any() else float("nan")
recall = flagged[is_late].mean() if is_late.any() else float("nan")
base = is_late.mean()
lead_late = first.loc[first["late"], "lead_days"]

say()
say("## Early-warning rule, tested on held-out cases")
say(
    "Rule: raise an alert when any step waits longer than the 90th percentile "
    "wait for that step (thresholds learned from 70% of cases, tested on the other 30%)."
)
say(f"- 'Late' means a total duration of at least {late_cut:.1f} days (slowest 10% in training data)")
say(f"- Test cases: {len(test_ids):,}; flagged: {int(flagged.sum()):,} ({flagged.mean():.1%})")
say(f"- Base rate of late cases: {base:.1%}")
say(f"- Precision (flagged cases that end up late): {precision:.1%}")
say(f"- Recall (late cases that were flagged): {recall:.1%}")
if base > 0 and precision == precision:
    say(f"- Lift over random picking: {precision / base:.1f}x")
if len(lead_late):
    say(f"- Median warning time before a late case finishes: {lead_late.median():.1f} days")

alerts = first.reset_index()[[CASE, "transition", "flag_time", "lead_days", "late"]]
alerts.to_csv("results/alerts.csv", index=False)

# ---------- charts ----------
plt.figure(figsize=(8, 4))
clip = dur.quantile(0.99)
plt.hist(dur.clip(upper=clip), bins=50)
plt.axvline(dur.median(), linestyle="--", label=f"median {dur.median():.0f} d")
plt.axvline(dur.quantile(0.9), linestyle=":", label=f"90th pct {dur.quantile(0.9):.0f} d")
plt.xlabel("Case duration (days, clipped at 99th percentile)")
plt.ylabel("Cases")
plt.title("Case duration distribution")
plt.legend()
plt.tight_layout()
plt.savefig("docs/images/case_duration.png", dpi=150)
plt.close()

top_rw = rework_by_act.head(8)[::-1]
plt.figure(figsize=(8, 4))
plt.barh([a[:40] for a in top_rw.index], top_rw.values)
plt.xlabel("Cases where the activity repeats")
plt.title("Most repeated activities (rework)")
plt.tight_layout()
plt.savefig("docs/images/rework.png", dpi=150)
plt.close()

top_tr = tstats.head(8)[::-1]
plt.figure(figsize=(9, 4.5))
plt.barh([t[:60] for t in top_tr.index], top_tr["total"].values)
plt.xlabel("Total waiting time (days, summed over the sample)")
plt.title("Where waiting time accumulates")
plt.tight_layout()
plt.savefig("docs/images/bottlenecks.png", dpi=150)
plt.close()

with open("results/summary.md", "w", encoding="utf-8") as f:
    f.write("\n".join(lines) + "\n")
print("\nSaved results/summary.md, results/alerts.csv and charts in docs/images/")

# ---------- metrics for the README generator ----------
import json  # noqa: E402

src_file = "data/SOURCE.txt"
source = (
    open(src_file, encoding="utf-8").read().strip()
    if os.path.exists(src_file)
    else "BPI Challenge 2019"
)


def num(x):
    return None if x is None or x != x else float(x)


metrics = {
    "source": source,
    "events": int(len(df)),
    "cases": int(n_cases),
    "median_days": float(dur.median()),
    "p90_days": float(dur.quantile(0.9)),
    "variants": int(len(vc)),
    "top10_share": float(vc.head(10).sum() / n_cases),
    "rework_cases": int(len(rework_ids)),
    "rework_pct": float(len(rework_ids) / n_cases),
    "median_with_rework": num(by_rework.get(True, float("nan"))),
    "median_without_rework": num(by_rework.get(False, float("nan"))),
    "top_rework": [[a, int(c)] for a, c in rework_by_act.head(5).items()],
    "top_transitions": [
        [name, int(r["n"]), float(r["mean"]), float(r["p90"]), float(r["total"])]
        for name, r in tstats.head(5).iterrows()
    ],
    "late_cut": float(late_cut),
    "test_cases": int(len(test_ids)),
    "flagged": int(flagged.sum()),
    "flagged_pct": float(flagged.mean()),
    "base_rate": float(base),
    "precision": num(precision),
    "recall": num(recall),
    "lift": num(precision / base) if base > 0 else None,
    "lead_median": float(lead_late.median()) if len(lead_late) else None,
}
with open("results/metrics.json", "w", encoding="utf-8") as f:
    json.dump(metrics, f, indent=2)
