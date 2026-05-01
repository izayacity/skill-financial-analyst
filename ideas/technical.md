## I. Naïve Composite Buy Score
Add 1 point for each:
- RSI24 ≥ 52
- RSI24 − RSI6 ≥ 18
- RSI12 − RSI6 ≥ 10
- RSI ordering correct (RSI-6 < RSI-12 < RSI-24)

| Score | Simple interpretation |
| ----- |-----------------------|
| 4     | Strong Buy            |
| 3     | Buy                   |
| 2     | Watchlist             |
| 1     | Weak                  |
| 0     | Avoid                 |

## II. Features
Use a shifted sigmoid so thresholds map to ~0.5 probability.
σ(x) = 1 / (1 + e^(−x))

### Feature 1 — Long-Term Trend Strength
2.1.1 Definition:
F1 = RSI24 − 52

2.1.2 Meaning:
Positive → trend strong
Negative → weak trend

Typical range:
−10 to +15

2.1.3 Normalization:
S1 = σ(0.25 ⋅ F1)

(Why 0.25:
Keeps RSI24 deviations from saturating too quickly.)

### Feature 2 — Short-Term Panic Spread
2.2.1 Definition:
F2 = RSI24 −RSI6

2.2.2 Meaning:
Key measure of dip depth inside trend.
Typical large-cap range:
- 5–30
Critical threshold:
F2 ≥ 18

2.2.3 Normalization:
S2 = σ(0.18 ⋅ (F2 − 18))

### Feature 3 — Mid-Term Pressure Spread
2.3.1 Definition:
F3 = RSI12 − RSI6

2.3.2 Meaning:
Measures short-term selling pressure.
Typical range:
- 3–18
Critical threshold:
F3 ≥ 10

2.3.3 Normalization:
S3 = σ(0.22 ⋅ (F3 − 10))

### Feature 4 — Short-Term Reversal Signal (3-day RSI6 slope)
2.4.1 Definition:
ΔRSI6(3) = RSI6(t)−RSI6(t−3)

2.4.2 Meaning:
Positive → selling slowing
Negative → selling accelerating

| ΔRSI6(3) | Meaning         |
| -------- | --------------- |
| ≥ +6     | Strong reversal |
| +3 to +6 | Valid turn      |
| 0 to +3  | Weak turn       |
| < 0      | Falling         |

2.4.3 Normalization:
S4 = σ(0.35 ⋅ ΔRSI6(3))

### Feature 5 — Mid-Term Stabilization (3-day RSI12 slope)
2.5.1 Definition:
ΔRSI12(3) = RSI12(t) − RSI12(t−3)

2.5.2 Meaning:
Positive → pressure stabilizing
Negative → trend still weakening
Less volatile than RSI6.

2.5.3 Normalization:
S5 = σ(0.3 ⋅ ΔRSI12(3))

### Feature 6 — Reversal Pattern
2.6.1 Definition:
RSI6(t−2) > RSI6(t−1)
AND
RSI6(t) > RSI6(t−1)

R = 1 IF reversal detected ELSE 0

2.6.2 Meaning:
Day t−1 is a local minimum.

| Condition         | S6  |
| ----------------- | --- |
| No reversal       | 0.5 |
| Reversal detected | 1.0 |
This avoids harsh zero penalties.

2.6.3 Normalization:
S6 = 0.5 + 0.5R

### Feature 7 — RSI6 Curvature
2.7.1 Definition:
C6 = RSI6(t) − 2RSI6(t−1) + RSI6(t−2)

R = 1 IF reversal detected ELSE 0

2.7.2 Meaning:
Curvature measures whether downward momentum is slowing. This detects reversal earlier than slope alone.
Curvature varies more widely than slope, so normalization must be gentle.

| Value | Meaning                        |
| ----- | ------------------------------ |
| > 0   | Downward momentum decelerating |
| >> 0  | Strong reversal building       |
| ≈ 0   | No acceleration change         |
| < 0   | Downtrend accelerating         |


| C6       | Meaning                      |
| -------- | ---------------------------- |
| ≥ +3     | Strong reversal acceleration |
| +1 to +3 | Reversal forming             |
| 0        | Neutral                      |
| < 0      | Still falling                |


2.7.3 Normalization:
S7 = σ(0.28 ⋅ C6)

### Feature 8 — Distance from 50-Day Moving Average
2.8.1 Definition:
D(MA50) = (Price − MA50) / MA50

2.8.2 Meaning:
Expressed as percentage. This measures how deep the pullback is relative to trend.

| D(MA50)    | Meaning           |
| ---------- | ----------------- |
| 0% to −2%  | Mild pullback     |
| −2% to −5% | Healthy dip       |
| −5% to −8% | Deep dip          |
| < −8%      | Risk of breakdown |

−3% to −6% is typically optimal buy territory. So, Centered at: −4%. Above MA is a weak signal.

2.8.3 Normalization:
S8 = σ(−18(D(MA50) + 0.04))

### Feature 9 — Distance from Support Level
2.9.1 Definition:
D(SUP) = (Price − Support) / Support

2.9.2 Meaning:
This measures structural risk. Requires: Nearest technical support.

| D(SUP) | Meaning          |
| ------ | ---------------- |
| 0–2%   | Ideal entry zone |
| 2–5%   | Acceptable       |
| >5%    | Late entry       |
| <0%    | Support broken   |

Best buy zone: Within 0–3% above support. Centered at: +2%.

2.9.3 Normalization:
S9 = σ(−14(D(SUP) − 0.02))

### Feature 10 — ATR-Normalized Pullback Depth
2.10.1 Definition:
For each day t:
TRt = max(High(t) − Low(t), ∣ High(t) − Close(t−1) ∣,∣ Low(t) − Close(t−1) ∣)

For the first 14 periods, Simple Moving Average (SMA):
ATR14 = 1/14 * ∑TRi(i=[1,14])

After the first 14, Wilder’s Smoothing (Standard):
ATR(t) = (ATR(t − 1) ⋅ 13 + TRt) / 14 = ATR(t−1) + 1/14 * (TRt − ATR(t−1))

D(ATR) = (RecentHigh − Price) / ATR14

2.10.2 Meaning:
Average True Range to fix misleading raw percentage pullbacks between volatile and stable stocks.
- RecentHigh = highest price in last 10–20 days
- ATR14 = 14-day ATR

Assume:
High = 105
Low = 100
Previous Close = 102

Compute:
High − Low = 5
|High − PrevClose| = |105 − 102| = 3
|Low − PrevClose| = |100 − 102| = 2
TR=max(5,3,2)=5

ATR14(initial) = (4+5+3+6+5+4+7+6+5+4+6+5+4+5) / 14 = 69 / 14 ≈ 4.93
This is equivalent to:
- 93% weight on past ATR
- 7% weight on new TR
So ATR changes gradually.

| Day | TR |
| --- | -- |
| 15  | 8  |
| 16  | 6  |
| 17  | 7  |

ATR15 = (4.93 ⋅ 13 + 8) / 14 = (64.09 + 8) / 14 = 72.09 / 14 ≈ 5.15

| D(ATR)  | Meaning             |
| ------- | ------------------- |
| < 1.0   | Minor pullback      |
| 1.0–2.0 | Healthy dip         |
| 2.0–3.0 | Deep pullback       |
| > 3.0   | Potential breakdown |

Best buy zone: 1.5–2.5 ATR. That range historically captures strong dip-buy opportunities.
Centered near: 1.8 ATR. This produces high scores in the ideal dip zone.

2.10.3 Normalization:
S10 = σ(1.2(D(ATR) − 1.8))

### Feature 11 — Volatility Regime
2.11.1 Definition:
V(ratio) = ATR14 / ATR50

2.11.2 Meaning:
Measures: Current volatility vs baseline. This feature adjusts expectations between stock with Low-volatility trends
and stock with High-volatility corrections.

| Vratio  | Meaning             |
| ------- | ------------------- |
| < 0.8   | Quiet trend         |
| 0.8–1.2 | Normal              |
| 1.2–1.6 | Elevated volatility |
| > 1.6   | Turbulent regime    |

Best buying occurs in: 0.9–1.3; Not too calm, not chaotic.
Centered at: 1.1; This rewards stable-but-active volatility.

2.11.3 Normalization:
S11 = σ(−5(V(ratio) − 1.1))

### Feature 12 — Relative Volume Spike (RVOL)
2.12.1 Definition:
RVOL = Volume(t) / Avg(Volume20)

2.12.2 Meaning:
Measures whether buying activity is expanding during a pullback or reversal.
- Volume = today's volume
- Avg(Volume20) = 20-day average volume

| RVOL    | Meaning                     |
| ------- | --------------------------- |
| < 0.8   | Weak participation          |
| 0.8–1.1 | Normal                      |
| 1.1–1.5 | Strong activity             |
| > 1.5   | Institutional participation |

Best reversal behavior typically occurs at: RVOL = 1.2 – 1.6
Centered near: 1.2 RVOL. This rewards meaningful participation.

2.12.3 Normalization:
S12 = σ(3(RVOL − 1.2))


### Feature 13 — Volume–Price Divergence
2.13.1 Definition:
V(trend) = Avg(Volume5) / Avg(Volume20)

2.13.2 Meaning:
Detects selling exhaustion, which is a powerful reversal indicator.
IF: V(trend) < 1, THEN: Volume is declining.
Centered at: 0.9; Encourages: Declining sell pressure.

2.13.3 Normalization:
S13 = σ(−4(V(trend) − 0.9))

## III. Multifactor technical reversal detection model
### structure
Momentum Layer
RSI spreads:
S1 — RSI24 strength
S2 — RSI24 − RSI6 spread
S3 — RSI12 − RSI6 spread

Timing Layer
RSI slopes + reversal:
S4 — RSI6 slope
S5 — RSI12 slope
S6 — Reversal confirmation

Acceleration Layer
RSI curvature:
S7 — RSI6 curvature

Structure Layer
MA + support:
S8 — MA50 distance
S9 — Support distance

Volatility Layer
ATR depth + regime:
S10 — ATR-normalized pullback
S11 — Volatility regime

Volume Participation Layer
Volume signals:
S12 — Relative volume spike
S13 — Volume divergence

### Weight Distribution
Score = 0.17 * S1 + 0.14 * S2 + 0.08 * S3 + 0.10 * S4 +0.06 * S5 + 0.05 * S6 + 0.06 * S7 + 
0.08 * S8 + 0.05 * S9 + 0.07 * S10 + 0.05 * S11 + 0.05 * S12 + 0.04 * S13

Total = 1.00

| Score     | Rating     |
| --------- | ---------- |
| ≥ 0.91    | Strong Buy |
| 0.80–0.91 | Buy        |
| 0.65–0.80 | Watch      |
| 0.50–0.65 | Weak       |
| < 0.50    | Avoid      |
