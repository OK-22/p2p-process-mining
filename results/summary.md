# Process mining results

Sample: 92,659 events across 20,000 cases

## Case duration (days)
- Median: 35.5
- 90th percentile: 78.0
- Mean: 43.2

## Process variants
- Distinct variants: 8
- Top 10 variants cover 100.0% of cases

## Rework (an activity repeated within a case)
- Cases with rework: 2,392 (12.0%)
- Median duration with rework: 40.2 days vs 34.9 days without (difference +5.3 days)
- Most repeated activities (cases affected):
  - Record Goods Receipt: 2,392 cases (12.0%)

## Where the waiting time goes (top 5 transitions by total wait)
- Record Goods Receipt -> Record Invoice Receipt: 20,000 times, mean wait 14.5 days, 90th pct 29.9 days
- Record Invoice Receipt -> Clear Invoice: 16,330 times, mean wait 13.0 days, 90th pct 27.3 days
- Create Purchase Order Item -> Record Goods Receipt: 17,073 times, mean wait 10.4 days, 90th pct 21.4 days
- Set Payment Block -> Remove Payment Block: 3,670 times, mean wait 20.4 days, 90th pct 44.8 days
- Remove Payment Block -> Clear Invoice: 3,670 times, mean wait 13.0 days, 90th pct 27.7 days

## Early-warning rule, tested on held-out cases
Rule: raise an alert when any step waits longer than the 90th percentile wait for that step (thresholds learned from 70% of cases, tested on the other 30%).
- 'Late' means a total duration of at least 78.0 days (slowest 10% in training data)
- Test cases: 6,000; flagged: 1,860 (31.0%)
- Base rate of late cases: 10.0%
- Precision (flagged cases that end up late): 31.5%
- Recall (late cases that were flagged): 97.8%
- Lift over random picking: 3.2x
- Median warning time before a late case finishes: 66.7 days
