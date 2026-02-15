# Overnight Range Scenarios (06:00–09:00 ET)

This document describes the 17 scenarios used to classify morning price action (06:00–09:00 ET) relative to the **overnight range** (18:00 ET previous day → 06:00 ET). Scenarios **1–3** are bull (strength); **4–6** are the bearish inverse (weakness); **7–17** are gap scenarios (A–K) so that every day with data gets exactly one scenario. All times are Eastern (ET); the analysis uses `America/New_York` so EDT/EST is handled automatically.

---

## Overnight Range (Reference Levels)

For each session date **D**, the overnight range is:

- **Start:** 18:00 ET on day D−1  
- **End:** 06:00 ET on day D  

From the 1-minute bars in that window we compute:

| Level   | Definition              |
|--------|--------------------------|
| **High**  | Maximum high in the overnight session |
| **Low**   | Minimum low in the overnight session  |
| **Middle**| (High + Low) / 2                      |

These three levels are the reference for the 06:00–09:00 ET scenarios.

---

## Time Windows

- **06:00–09:00 ET:** Morning window used to **classify** the day into a scenario (price path and 09:00 close vs overnight high/mid/low).
- **09:00–16:00 ET:** Afternoon window used to **measure** outcomes (e.g., whether price stayed above overnight mid or above the 06:00–09:00 low).

---

## Scenario 1: Below Low, Close Above Mid

**Definition:** During 06:00–09:00 ET, price **traded below the overnight low** at least once, and at **09:00 ET the close was above the overnight middle**.

- **Price path (06–09):** Dips below the overnight low, then recovers so the 09:00 close is above the overnight mid.
- **Interpretation:** Early selling below the overnight range, then a recovery back through the middle—often a “washout then bounce” type of morning.

![Scenario 1: Price goes below overnight low, then closes above mid at 09:00](docs/overnight_scenario_1.png)

**Typical use:** Identify days where the overnight low was undercut in the first three hours but buyers reclaimed the midpoint by the open of the main session (09:00).

---

## Scenario 2: Above Low, Close Above High

**Definition:** During 06:00–09:00 ET, price **never traded below the overnight low** (lowest price ≥ overnight low), and at **09:00 ET the close was above the overnight high**. This scenario excludes cases that qualify as Scenario 3 (so price may have dipped below the overnight mid but stayed above the overnight low).

- **Price path (06–09):** Stays at or above the overnight low; may trade between low and mid or between mid and high; 09:00 close is above the overnight high.
- **Interpretation:** Respect for the overnight low with strength into the high—breakout above the range by 09:00 while holding the low.

![Scenario 2: Price stays above overnight low, closes above high at 09:00](docs/overnight_scenario_2.png)

**Typical use:** Strong mornings that hold the overnight low and close above the range; often treated as continuation/breakout setups.

---

## Scenario 3: Above Mid, Close Above High

**Definition:** During 06:00–09:00 ET, price **never traded below the overnight middle** (lowest price ≥ overnight mid), and at **09:00 ET the close was above the overnight high**.

- **Price path (06–09):** Stays at or above the overnight mid for the entire 06:00–09:00 window; 09:00 close is above the overnight high.
- **Interpretation:** Strongest of the three: no test of the lower half of the overnight range, and a close above the high by 09:00.

![Scenario 3: Price stays above overnight mid, closes above high at 09:00](docs/overnight_scenario_3.png)

**Typical use:** Highest-conviction “strength” mornings: no dip to mid, clear breakout above the overnight high by 09:00.

---

## Scenario 4: Above High, Close Below Mid (Inverse of 1)

**Definition:** During 06:00–09:00 ET, price **traded above the overnight high** at least once (max high in 06–09 > overnight high), and at **09:00 ET the close was below the overnight middle**.

- **Price path (06–09):** Spikes above the overnight high, then sells off so the 09:00 close is below the overnight mid.
- **Interpretation:** Early buying above the overnight range, then a rejection back through the middle—often a "failed breakout" or squeeze-reversal type of morning.

![Scenario 4: Price goes above overnight high, then closes below mid at 09:00](docs/overnight_scenario_4.png)

**Typical use:** Identify days where the overnight high was taken out in the first three hours but sellers reclaimed the midpoint by 09:00.

---

## Scenario 5: Below High, Close Below Low (Inverse of 2)

**Definition:** During 06:00–09:00 ET, price **never traded above the overnight high** (max high in 06–09 ≤ overnight high), and at **09:00 ET the close was below the overnight low**. This scenario excludes cases that qualify as Scenario 6 (so price may have traded above the overnight mid but stayed below the overnight high).

- **Price path (06–09):** Stays at or below the overnight high; 09:00 close is below the overnight low.
- **Interpretation:** Respect for the overnight high with weakness into the low—breakdown below the range by 09:00 while holding below the high.

![Scenario 5: Price stays below overnight high, closes below low at 09:00](docs/overnight_scenario_5.png)

**Typical use:** Weak mornings that hold below the overnight high and close below the range; often treated as breakdown/continuation short setups.

---

## Scenario 6: Below Mid, Close Below Low (Inverse of 3)

**Definition:** During 06:00–09:00 ET, price **never traded above the overnight middle** (max high in 06–09 ≤ overnight mid), and at **09:00 ET the close was below the overnight low**.

- **Price path (06–09):** Stays at or below the overnight mid for the entire 06:00–09:00 window; 09:00 close is below the overnight low.
- **Interpretation:** Strongest weakness: no test of the upper half of the overnight range, and a close below the low by 09:00.

![Scenario 6: Price stays below overnight mid, closes below low at 09:00](docs/overnight_scenario_6.png)

**Typical use:** Highest-conviction "weakness" mornings: no rally to mid, clear breakdown below the overnight low by 09:00.

---

## Scenario Comparison

**Bull scenarios (1–3)** use **min(low)** in 06:00–09:00 vs overnight levels. **Bear scenarios (4–6)** use **max(high)** in 06:00–09:00 vs overnight levels.

| Scenario | Extreme 06–09 vs overnight | Close at 09:00 vs overnight |
|----------|----------------------------|-----------------------------|
| **1**    | Min went **below** low     | **Above** mid               |
| **2**    | Min stayed **≥** low (can be below mid) | **Above** high |
| **3**    | Min stayed **≥** mid       | **Above** high              |
| **4**    | Max went **above** high    | **Below** mid               |
| **5**    | Max stayed **≤** high (can be above mid) | **Below** low |
| **6**    | Max stayed **≤** mid       | **Below** low               |

Scenarios are **mutually exclusive**. Each day is assigned exactly one scenario (1–17). Total days and **pct of total** are computed over all 17 scenarios.

---

## Scenarios 7–17 (Gap scenarios)

Days that do not match 1–6 are classified into gap scenarios 7–17 (A–K). Full definitions and interpretation are in [docs/OVERNIGHT_SCENARIO_GAPS.md](docs/OVERNIGHT_SCENARIO_GAPS.md).

| Scenario | Id | One-line description |
|----------|-----|------------------------|
| 7 | A | Below low, close ≤ mid (failed recovery) |
| 8 | B | Above low, close in (M, H] (recovery, no breakout) |
| 9 | C | Above low, close ≤ mid (hold low then fade) |
| 10 | D | Above mid, close < mid (gave back strength) |
| 11 | E | Above mid, close in [M, H) (strong range, no breakout) |
| 12 | F | Above high, close ≥ mid (spike then hold mid) |
| 13 | G | Above high, close in [L, M) (spike then sell to mid) |
| 14 | H | Above high, close < L (spike then collapse) |
| 15 | I | Below high, close ≥ low (no breakdown) |
| 16 | J | Below mid, close ≥ low (weak but hold low) |
| 17 | K | Inside range (min ≥ L, max ≤ H, close in [L, H]) |

**Outcome metrics:** Bull-type (1–3, 7–11) report above_mid, above_0609_low, above_18_09_low for 09:00–16:00 and **new_high_09_1130** (% of days a new high was made 09:00–11:30). Bear-type (4–6, 12–16) report below_mid, below_0609_high, below_18_09_high and **new_low_09_1130** (% of days a new low was made 09:00–11:30). Scenario 17 (K) reports both sets.

---

## Scenario Distribution

For each run, the tool reports **total days with a scenario** (number of days in the date range that were assigned scenario 1–17). For each scenario it then reports:

- **Count (n)** and **percentage of total** — what share of all scenario days fell into that scenario (the 17 percentages sum to 100%).

Example: if over a date range there are 517 days with a scenario, each scenario's share is reported as a percentage of that total.

---

## Outcome Metrics (09:00–16:00 ET)

For days in each scenario, the analysis reports:

1. **Pct price did not go below overnight mid**  
   Percentage of those days where the **lowest price in 09:00–16:00 ET** never went below the overnight middle (min(09–16) ≥ overnight mid).

2. **Pct price did not go below 06:00–09:00 low**  
   Percentage of those days where the **lowest price in 09:00–16:00 ET** never went below the **lowest price in 06:00–09:00 ET** (the morning low held as support in the afternoon).

### Morning extension (09:00–11:30 ET)

- **Bull-type (1–3, 7–11):** **new_high_09_1130** — Percentage of days where price made a **new high** between 09:00 and 11:30 ET (i.e. the high in 09:00–11:30 exceeded the high in effect at 09:00: max of overnight high and 06:00–09:00 high).
- **Bear-type (4–6, 12–16):** **new_low_09_1130** — Percentage of days where price made a **new low** between 09:00 and 11:30 ET (i.e. the low in 09:00–11:30 was below the low in effect at 09:00: min of overnight low and 06:00–09:00 low).

Scenario 17 reports both new_high_09_1130 and new_low_09_1130.

---

## Running the Analysis

From the repository root:

```bash
# Single day
python -m src.overnight_range_scenarios --symbol NQ --date 2026-02-13

# Date range (e.g. one year)
python -m src.overnight_range_scenarios --symbol NQ --start 2025-02-14 --end 2026-02-13
```

Optional: `--config`, `--db` to override config or database path.

---

## Generating the Graphics

The scenario diagrams are saved as PNGs in `docs/`. To create or refresh them, run from the repository root:

```bash
python -m src.draw_overnight_scenarios
```

This writes `overnight_scenario_1.png` through `overnight_scenario_6.png` into `docs/`. Requires `matplotlib`.

---

## Diagram Conventions

The graphics show a simplified **price (vertical) vs time (horizontal)** view:

- **Horizontal lines:** Overnight high (top), middle, and low (bottom).
- **06:00–09:00:** Classification window; the path in this window and the 09:00 close determine the scenario.
- **09:00–16:00:** Outcome window (not drawn in detail in the scenario diagrams; used only for the reported percentages).

All times are Eastern (ET).
