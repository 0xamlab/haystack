# quotes_question_set.json

16 objective, numerically-scoreable questions against the real
`test_files/Processed_Quotes.csv` corpus (33,125 parsed rows), for benchmarking
an LLM+tool-calling system's numeric answers against fixed ground truth.

## How ground truth was derived

Every `ground_truth` value in `quotes_question_set.json` was computed directly
with pandas on `test_files/Processed_Quotes.csv` -- never via the Algenta SDK or
its Mojo kernels, so a bug shared between "ground truth" and "system under test"
can't make a wrong answer look right. Example (values reproduce exactly):

```python
import pandas as pd
df = pd.read_csv("test_files/Processed_Quotes.csv", low_memory=False)

df["UNIT_PRICE"].dropna().quantile(0.9)                       # q01 -> 1905.48
df["EXT_PRICE"].dropna().quantile(0.25)                        # q02 -> 1275.25
df["EXT_PRICE"].dropna().quantile(0.5)                         # q03 -> 6052.1
df["UNIT_PRICE"].mean()                                        # q04 -> 779.182035...
df["UNIT_PRICE"].std(ddof=1)                                    # q05 -> 2331.963152...
df["UNIT_PRICE"].min(), df["UNIT_PRICE"].max()                 # q06 -> 0.0, 215000.0
(df["STATUS"] == "LOST").sum()                                  # q07 -> 14673
df.loc[df["CUST_TYPE"] == "OEM", "EXT_PRICE"].sum()             # q08 -> 169562999.02
df.loc[df["STATUS"] == "ORDER", "QUANTITY"].mean()              # q09 -> 261.723926...
df["QUANTITY"].sum()                                            # q10 -> 3436556.0
df["CUSTOMER_NO"].nunique()                                     # q11 -> 2008
df["STATUS"].dropna().nunique()                                 # q12 -> 12
(df["AUTO_QUOTED"] == "Y").sum() / df["AUTO_QUOTED"].notna().sum()  # q13 -> 0.03963...
df.groupby("CUST_TYPE")["UNIT_PRICE"].mean().sort_values(ascending=False)  # q14 -> MILITARY, 12515.95
df.groupby("STATUS")["EXT_PRICE"].mean().sort_values(ascending=False)     # q15 -> QTE, 60485.014002
df.dropna(subset=["UNIT_PRICE", "QUANTITY"])[["UNIT_PRICE", "QUANTITY"]].corr().iloc[0, 1]  # q16 -> -0.071331...
```

## Independent cross-check (second parser, not pandas)

Four of the values (q06 min/max, q07 count, q10 sum, q11 nunique) were
additionally recomputed using Python's stdlib `csv.DictReader` -- a completely
separate CSV parser implementation from pandas's C parser -- and matched
exactly:

```python
import csv
rows = list(csv.DictReader(open("test_files/Processed_Quotes.csv", newline="", encoding="utf-8", errors="replace")))
len(rows)                                                           # 33125 (matches pandas row count)
sum(1 for r in rows if r["STATUS"] == "LOST")                       # 14673 (matches q07)
prices = [float(r["UNIT_PRICE"]) for r in rows if r["UNIT_PRICE"]]
min(prices), max(prices)                                            # 0.0, 215000.0 (matches q06)
qtys = [float(r["QUANTITY"]) for r in rows if r["QUANTITY"]]
sum(qtys)                                                            # 3436556.0 (matches q10)
len({r["CUSTOMER_NO"] for r in rows if r["CUSTOMER_NO"]})            # 2008 (matches q11)
```

This also confirms the earlier phase's note about `wc -l` (46,573) vs. the
parsed row count (33,125): both parsers independently land on 33,125 rows, so
the difference is embedded newlines inside quoted CSV fields, not a parsing
bug in either tool.

## Hand spot-checks

- q06 max ($215,000.00): row `PART_NUMBER=902-00001-05`, `STATUS=LOST`,
  `EXT_PRICE=$430,000.00` -- exactly 2x UNIT_PRICE, consistent with a real
  quantity-2 quote even though that row's `QUANTITY` cell itself is null.
- q06 min ($0.00): real rows with an unpriced/zero-priced quote line (e.g.
  `PART_NUMBER=SL-2221M2C8`, `STATUS=QTE`); no negative values exist anywhere
  in `UNIT_PRICE`, `EXT_PRICE`, or `QUANTITY` (checked with
  `(df[col] < 0).sum() == 0` for all three).
- q16: deliberately paired `UNIT_PRICE` with `QUANTITY`, not `EXT_PRICE`,
  because `EXT_PRICE ~= UNIT_PRICE * QUANTITY` holds for ~80% of rows
  (18,738 / 23,269 within 1 cent), which would make a UNIT_PRICE-vs-EXT_PRICE
  correlation trivially/tautologically high rather than a genuine test.

## Scoring

See each question's `scoring` block in `quotes_question_set.json` for the
exact rule (`exact_int`, `exact_string`, `tolerance_abs`, or
`tolerance_abs_multi` for questions with more than one required field, e.g.
q06's min+max or q14/q15's category label + its average). All ground truth
values and tolerances were fixed before any LLM/tool-calling answer existed.
