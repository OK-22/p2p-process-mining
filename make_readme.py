"""Builds README.md from results/metrics.json. Run after analyze.py."""
import json

m = json.load(open("results/metrics.json", encoding="utf-8"))
synthetic = m["source"].lower().startswith("synthetic")


def pct(x, d=0):
    return "n/a" if x is None else f"{x * 100:.{d}f}%"


def days(x, d=1):
    return "n/a" if x is None else f"{x:.{d}f}"


lift = "n/a" if m["lift"] is None else f"{m['lift']:.1f}x"
lead = days(m["lead_median"], 0)
top_rw_name, top_rw_n = m["top_rework"][0] if m["top_rework"] else ("n/a", 0)
top_tr = m["top_transitions"][0] if m["top_transitions"] else ["n/a", 0, 0, 0, 0]

data_line = (
    f"**Data:** {m['source']}. Results show the method working, not real-world performance."
    if synthetic
    else f"**Data:** {m['source']}, public purchase-to-pay event log (random sample of {m['cases']:,} cases)."
)

rework_diff = ""
if m["median_with_rework"] is not None and m["median_without_rework"] is not None:
    d = m["median_with_rework"] - m["median_without_rework"]
    rework_diff = (
        f" Cases with rework take a median of {days(m['median_with_rework'])} days "
        f"versus {days(m['median_without_rework'])} days without ({d:+.1f} days)."
    )

rw_rows = "\n".join(f"| {a} | {c:,} | {c / m['cases']:.1%} |" for a, c in m["top_rework"])
tr_rows = "\n".join(
    f"| {n} | {c:,} | {mean:.1f} | {p90:.1f} |" for n, c, mean, p90, _ in m["top_transitions"]
)

limits = (
    "- The event log is simulated, so the bottlenecks were designed into it. The value of this repo is the pipeline: "
    "discovery, an early-warning rule, and an honest train/test evaluation. Swap in a real log to get real findings.\n"
    if synthetic
    else "- Cases are purchase order items from one company, sampled at random. Findings may not transfer to other processes.\n"
)

readme = f"""# Purchase-to-Pay Process Mining and Early-Warning Automation

> {pct(m['rework_pct'])} of cases involve rework. A simple early-warning rule flags {pct(m['recall'])} of late cases with a median of {lead} days of notice (precision {pct(m['precision'])}, {lift} better than random picking).

{data_line}

## Define

Purchase-to-pay cases often finish late because steps stall or repeat, and owners usually find out only after the case is already late. Goal: find where time is lost, then build an automation that warns the owner while there is still time to act.

## Measure

- {m['events']:,} events across {m['cases']:,} cases
- Median case duration: {days(m['median_days'])} days; 90th percentile: {days(m['p90_days'])} days
- {m['variants']:,} distinct process variants; the top 10 cover {pct(m['top10_share'], 1)} of cases

![Case duration](docs/images/case_duration.png)

## Analyze

**Rework.** {m['rework_cases']:,} cases ({pct(m['rework_pct'], 1)}) repeat at least one activity.{rework_diff} The most repeated activity is "{top_rw_name}" ({top_rw_n:,} cases).

| Repeated activity | Cases | Share of cases |
|---|---|---|
{rw_rows}

![Rework](docs/images/rework.png)

**Where time goes.** The step transitions that accumulate the most waiting time:

| Transition | Times | Mean wait (days) | 90th pct wait (days) |
|---|---|---|---|
{tr_rows}

![Bottlenecks](docs/images/bottlenecks.png)

## Improve

An early-warning rule: raise an alert as soon as any step has waited longer than the 90th percentile wait for that step. Thresholds are learned from 70% of cases and the rule is scored on the other 30%, so the results are not measured on the data used to set the thresholds. "Late" means a total duration of at least {days(m['late_cut'])} days (the slowest 10% in the training data).

## Control

| Metric (held-out cases) | Result |
|---|---|
| Cases tested | {m['test_cases']:,} |
| Cases flagged | {m['flagged']:,} ({pct(m['flagged_pct'], 1)}) |
| Base rate of late cases | {pct(m['base_rate'], 1)} |
| Precision (flagged cases that end up late) | {pct(m['precision'], 1)} |
| Recall (late cases that were flagged) | {pct(m['recall'], 1)} |
| Lift over random picking | {lift} |
| Median warning before a late case finishes | {lead} days |

`results/alerts.csv` lists every flagged case with the step that triggered the alert and the days of warning. Re-running `analyze.py` reproduces every number here.

## Limitations and next steps

{limits}- Precision is moderate: the rule trades some false alarms for catching most late cases. A production version would tune the threshold per team to control alert fatigue.
- The alert fires from timestamps in a log. A live version would need a feed from the ERP and a workflow to route alerts to case owners (for example with UiPath or Celonis Action Flows).

## How to run

1. `pip install pm4py pandas numpy matplotlib`
2. Put the event log in `data/` (see `analyze.py` for the expected file) or run `python simulate_p2p.py` for simulated data
3. `python analyze.py` produces the results and charts
4. `python make_readme.py` rebuilds this README from the results
"""

with open("README.md", "w", encoding="utf-8") as f:
    f.write(readme)
print("Wrote README.md")
