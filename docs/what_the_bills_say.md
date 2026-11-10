# What the bills say

Read from two K-Electric billing summaries and one detailed bill, all dated
10–12 November 2026, for the two connections at PLOT 140/H-2 PECHS.

Everything here is measured. Until these arrived, every rupee this project
displayed rested on two guesses.

## The connections

| | Account | Contract | Meter | Sanctioned | Tariff | Solar |
|---|---|---|---|---|---|---|
| Ground floor + basement | 0400006377759 | 30823658 | TY75237 | 19 kW | A-2B | **yes** |
| First floor + cafe | 0400006377837 | 30823674 | — | 37 kW | — | no |

The meter number on the October bill is **TY75237**, not the TU09890 that was
reported from memory. Worth checking which is right before either is quoted
to K-Electric.

## 1. Fixed charges are being billed on double the sanctioned load

October 2026, ground floor and basement:

```
Fixed Charges      38 units   Rs 1250.0000   Rs 47,500.00
Sanctioned load    19 kW
MDI                38 kW off-peak, 33 kW peak
```

The connection is sanctioned for 19 kW and the meter recorded a maximum
demand of 38. Fixed charges follow the maximum demand, so the building pays
**Rs 47,500 a month** where 19 kW would cost Rs 23,750.

**Rs 23,750 a month. Rs 285,000 a year.**

This is a different lever from everything else in this project. It is not
about how many units are used; it is about how many things are switched on
at the same instant. Nothing has to be used less — the same work spread
across the day instead of peaking together would cut the fixed charge.

It also explains something that looked wrong earlier. Several months on this
meter used more than a 19 kW connection could physically deliver, and the
first reading of that was that the sanctioned loads must have been swapped.
They are not. The building is simply drawing well past its sanctioned load,
which the MDI line states outright.

## 2. The tariff is time-of-use, and the evening is the expensive part

```
Variable Off Peak   9553 units   Rs 35.1500
Variable Peak       2070 units   Rs 43.8200
```

Peak is **17.8%** of consumption at **25% more** per unit on the energy
charge.

What one more unit actually costs, which is what switching an air
conditioner off actually saves:

| | Energy | + adders | + taxes (67.1%) | **Marginal** |
|---|---|---|---|---|
| Off-peak | 35.15 | 40.01 | ×1.671 | **Rs 66.9** |
| Peak | 43.82 | 48.68 | ×1.671 | **Rs 81.3** |

The adders are the quarterly adjustment (0.5194), fuel adjustment (1.1086)
and PHL surcharge (3.23), all charged per unit. The all-in average on the
bill is Rs 76.33, but an average is the wrong number for this: fixed charges
do not change when a room's unit goes off, so the saving is the marginal
cost, not the average.

**An empty room cooled through the evening costs 22% more than the same room
cooled through the afternoon**, and the evening is exactly when offices empty
and units get left on. The closing round is worth more than its hours
suggest.

The peak window is not printed on the summary page. 18:30–22:30 is what was
reported and matches K-Electric's winter window; it shifts in summer, so it
should be confirmed against a bill rather than trusted from here.

## 3. July 2026 on the first-floor account cannot be right

| Month | Units | Amount |
|---|---|---|
| June 2026 | 3,277 | Rs 259,767 |
| **July 2026** | **41,145** | **Rs 2,731,004** |
| August 2026 | 6,332 | Rs 474,511 |

41,145 units is **149%** of what a 37 kW connection can deliver in
thirty-one days, and seven times the months either side.

It may be a catch-up after months of estimated readings, a meter fault, or a
billing error. What it cannot be is a month that building actually used. If
it is an error it is worth roughly **Rs 2.4 million**.

It is loaded into `meter_bills` with that note on the row, and left out of
every average.

## What this changes

The money on the dashboard was computed at Rs 55 a unit. It is now Rs 67
off-peak and Rs 81 peak — so every figure shown before today was understated
by between a fifth and a half.

Twelve months to October across both connections: **Rs 16.0 million**.
