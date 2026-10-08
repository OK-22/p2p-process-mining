"""
Fallback data generator: a SIMULATED purchase-to-pay event log.

Only use this if the real BPI Challenge 2019 log is unavailable. The README
generator labels the project as synthetic when this file has been used.
Writes data/sample.csv (same columns as the real log) and data/SOURCE.txt.
"""
import os

import numpy as np
import pandas as pd

rng = np.random.default_rng(42)
N_CASES = 20000
N_VENDORS = 400
os.makedirs("data", exist_ok=True)

vendor_speed = rng.lognormal(0, 0.35, N_VENDORS)  # slow vendors are slow at every step
start = pd.Timestamp("2018-01-01", tz="UTC")


def wait(median_days, speed, sigma=0.8):
    return float(rng.lognormal(np.log(median_days * speed), sigma))


rows = []
for i in range(N_CASES):
    speed = vendor_speed[rng.integers(0, N_VENDORS)]
    t = start + pd.Timedelta(days=float(rng.uniform(0, 330)))
    case = f"{4500000000 + i}_00001"
    events = [("Create Purchase Order Item", 0.0)]
    if rng.random() < 0.15:
        events.append(("Change Price", wait(3, 1.0)))
    events.append(("Record Goods Receipt", wait(7, speed)))
    if rng.random() < 0.12:  # partial delivery: goods receipt repeats
        events.append(("Record Goods Receipt", wait(4, speed)))
    events.append(("Record Invoice Receipt", wait(10, speed)))
    if rng.random() < 0.18:  # invoice blocked for payment
        events.append(("Set Payment Block", wait(1, 1.0)))
        events.append(("Remove Payment Block", wait(12, speed, sigma=1.0)))
    events.append(("Clear Invoice", wait(9, speed)))
    for act, w in events:
        t += pd.Timedelta(days=w)
        rows.append((case, act, t.isoformat()))

pd.DataFrame(rows, columns=["case:concept:name", "concept:name", "time:timestamp"]).to_csv(
    "data/sample.csv", index=False
)
with open("data/SOURCE.txt", "w", encoding="utf-8") as f:
    f.write("Synthetic (simulated purchase-to-pay log)")
print(f"Wrote data/sample.csv with {len(rows):,} events across {N_CASES:,} cases (synthetic)")
