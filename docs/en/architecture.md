# Architecture

> English translation of [arquitetura.md](../arquitetura.md). Table and
> column names stay in Portuguese, as they are in the database.

## Why three layers

The medallion pattern exists to separate three responsibilities that a
spreadsheet mixes together: **keeping what arrived**, **deciding what it
means** and **serving it for consumption**.

In practice the separation pays off when a rule changes. Fixing the
classification of a transaction does not require going back to the
original file — the silver layer is simply reprocessed from bronze,
which was never altered.

```
files ──> bronze ──> silver ──> gold ──> Power BI / HTML panels
          copy       meaning    consumption
```

### bronze — faithful copy

Stores the data as it arrived, with no type conversion. Columns are
`varchar` even for dates and amounts, because an invalid value must not
break the load: it comes in as text and silver decides what to do.

Every row carries **lineage**: which file it came from, which sheet,
and at which position. Any number can be audited back to its source.

Bronze stores **each event once**, not one copy per file. The decision
comes from the real process: statements are downloaded several times a
month, always covering the previous period, so they overlap almost
entirely. Persisting everything would mean keeping eight copies of the
same data. Fidelity to the raw data is not lost: the files stay on disk
and the load can be re-run from them.

### silver — meaning

Here the data gets types, classification and a standardized
vocabulary. One table per business entity, already unifying sources
of the same nature — both credit cards, for instance, live in the same
table with a column identifying which one.

This is also where inconsistencies between sources are resolved: the
sign of the amount, the spelling of labels, and flagging rows that are
not transactions.

### gold — consumption

A dimensional star schema, optimized for reading. Facts are
deliberately kept apart:

| Fact | Subject |
|---|---|
| `fato_investimento` | Investment account movements |
| `fato_movto_financ` | Cash flow and personal spending — checking account and credit cards |
| `fato_familia` | Shared household expenses, with who paid each one |
| `fato_dia` | Daily habits journal — one snapshot per day |
| `fato_dia_habito` | The same journal in long format, one row per day per habit |
| `fato_avaliacao_fisica` | Bioimpedance and body measurements, 2008 to 2026 |
| `fato_manutencao_auto` | Car services and repairs, with mileage |

They are not mixed because they answer different questions about
different money. A dividend and a lunch do not belong in the same
analysis; and household spending comes out of a fund that two people
contribute to — adding it to personal spending would count two
people's expenses as one person's.

**But they share dimensions.** `fato_movto_financ` and `fato_familia`
use the same `dim_area_financ`, `dim_categoria_financ` and
`dim_grupo_financ`, because the area/category/group vocabulary largely
overlaps. That makes it possible to compare "how much I spent on food
on my own" with "how much the household spent on food" along the same
axis, without duplicating the dimension. Categories that exist on only
one side — `MORADIA` (housing) and `DIARISTA` (cleaning) only exist for
the household — coexist without conflict.

The habits journal has nothing in common with the financial facts
except the calendar — and that is exactly enough: `dim_calendario` is
the same table, so crossing spending and habits on the same date needs
no extra bridge.

### Why the journal has two facts

It is the only source modeled twice, because the two questions asked
of it have incompatible shapes:

- *"how much water did I drink per month"*, *"did I train more on work
  days?"* — need **one row per day**, everything side by side. That is
  `fato_dia`.
- *"how is adherence to each habit evolving?"* — needs **one row per
  day per habit**. Without it, every form question becomes its own DAX
  measure and adding a new question forces a report rebuild. That is
  `fato_dia_habito`.

The wide format alone would make the habits panel unworkable; the long
format alone would make it impossible to add up liters of water without
mixing units. Keeping both costs nothing, and the daily score is
computed only once, at load time, from the same rule.

**The adherence rule is data, not code.** What counts as a goal met
lives in `dim_habito`, in the columns `DS_RESPOSTA_DESEJADA`,
`VL_META_MINIMA` and `FL_APURA_ADERENCIA`. The load just applies it.
Deciding that the late-night snack is optional, or changing the water
goal, is an `UPDATE` followed by a new load — and re-running the SQL
script does not undo the change, because the seed only inserts what is
missing.

There are **two ways to adhere**, and the dimension says which applies
to each habit: reaching a numeric threshold (`VL_META_MINIMA`, today
only water, in liters per day) or giving the expected answer
(`DS_RESPOSTA_DESEJADA`, everything else). Water is the only habit
measured as a number, so it carries the value in `VL_MEDIDA` in the
long fact — but anyone summing liters should use
`fato_dia.VL_AGUA_LITROS`, because `VL_MEDIDA` would start mixing units
if a second numeric habit appeared.

`FL_META_AGUA`, in the wide fact, is copied from the long fact instead
of recomputed: the goal is applied once, and the two tables cannot
diverge if the threshold changes.

The dimension also separates **goal** from **context**: training is an
objective, having family at home is a circumstance. Context does not
enter the daily score, but it still works as a filter — and that is how
one finds out, for example, that training happens on most work days and
on few days off.

### Body assessments and the long-series problem

It is the longest series in the project — assessments from 2008 to 2026
— and the only one whose **definition changed along the way**. Until
2013 the report brought circumferences, blood pressure and heart rate;
from 2018 onward it is bioimpedance. Only five metrics exist in both
eras: weight, BMI, body fat %, fat mass and height.

That is not a defect to fix, it is a fact to declare.
`FL_SERIE_CONTINUA` flags the five, and the long-term panel filters on
it. Without it, the 18-year chart shows lines that start or stop in the
middle, and the reader concludes something happened when only the
device changed.

The most dangerous case is `Massa Muscular` × `Massa Muscular/Ossea`
(muscle mass vs. muscle + bone mass). They never coexist: the first
appears from 2018 in one range, the second until 2013 in a range about
25 kg higher, because it includes bone mass. They are **distinct**
metrics in the dimension, on purpose. Unifying them because of the
similar name would produce a 25 kg drop that never happened.

**The change lives in the fact.** Assessments are irregular — from 21
days to almost five years apart — so "previous assessment" matches no
calendar period. `VL_MEDIDA_ANTERIOR` and `VL_VARIACAO` are computed at
load time, against the last time that metric was *measured*, not
against the previous assessment: skipping a measurement must not open
a gap in the comparison.

`DS_SENTIDO_MELHOR` says which direction is better for each metric,
and stays **null** where there is no universal answer — weight, BMI and
height depend on the current goal; blood pressure is best within a
range, not at an extreme. Marking a direction there would be faking
certainty.

### Car maintenance and the only view in the model

The service history alone answers *"how much have I spent"*. The same
spreadsheet has a second sheet saying every how many kilometers each
category must be replaced. Crossed, the two answer *"what is coming
due"*, and that is where the data stops being an archive. Hence
`gold.vw_manutencao_prevista`.

It is a view and not a table because the result depends on the current
mileage, which changes with every load: materializing it would invite
reading a stale number.

**Two vehicles with independent odometers.** One car until November
2025, another since then. `dim_veiculo` exists because of this —
without the split, the new car's mileage would look like a step back
from the old car's, and every prediction would be wrong. The view only
considers the active vehicle for the same reason.

**The honest limit of the prediction.** `NR_KM_ATUAL` comes from the
highest mileage ever recorded, and mileage is only recorded at the
workshop. Right after a visit everything shows as *up to date* by
construction, and the prediction only becomes meaningful as the car is
driven without being serviced. A real alert would require logging the
odometer periodically, with date and vehicle.

**It is not linked to the financial fact**, even though part of these
expenses shows up on the credit card bill. Here the subject is the
vehicle — what was replaced, at what mileage — not the money; adding
both would count the same expense twice.

---

## Modeling decisions

### The category hierarchy is not a hierarchy

Spending has three classification levels — area, category and group —
but the data showed that **they do not form a tree**: the same group
appears under different categories over time, and the same category
under different areas.

Modeling it as a navigable hierarchy would produce ambiguous totals.
The dimension has one row per **distinct combination** of the three,
which is what the data actually is.

### Detail and summary levels

A credit card expense exists on two planes:

```
checking account:  card bill payment         <- summary (the parent)
                   │
card:              ├── grocery purchase      <- detail (the children)
                   ├── gas station purchase
                   └── pharmacy purchase
```

Adding both planes counts the same expense twice. The `DS_NIVEL`
attribute separates them, and **the expense measure must filter
`ANALITICO`** (detail). The summary level is used to reconcile with the
bank statement and to see the monthly cash-out on cards.

The level is not guessed: it comes from a field each source already
provided — the classification group in the checking account, and an
indicator column in the card file.

### Surrogate keys are never renumbered

Dimensions grow on their own: an asset or category that shows up for
the first time gets a new row. But **the key of an existing member
never changes**, because the fact points to it.

Rule-derived attributes, on the other hand, are updated. Otherwise an
improved rule would only apply to new records — which is exactly what
happened when an asset class stayed flagged as unclassified after the
rule covering it already existed.

### Members for missing values

Every dimension has a member with key `-1` representing "not
informed" or "not applicable". The fact never needs a null foreign key,
and the report shows a readable label instead of a blank row.

---

## Event identity

Each transaction has a `hash_negocio`: a SHA-256 of the normalized
business key. It is what allows deduplication across files and what
links the same event across layers.

The composition of the key depends on what the source offers:

| Source | Business key |
|---|---|
| Investments | date + description + amount + **running balance** |
| Checking account | date + description + amount + **occurrence number** |
| Cards | date + description + amount + bill date + occurrence |

The balance is in the key on purpose: in a statement with a running
balance, two real identical transactions on the same day have
different balances, while a row entered twice repeats the balance.
That is how 20 silent duplicates were identified with certainty.

Where there is no balance — the bank statement has only date,
description and amount — the key uses an occurrence counter. Two
identical purchases on the same day are real events and both are kept.

The constraint is `UNIQUE` in the database. **Deduplication no longer
depends on the script being correct.**

---

## Documentation inside the database

Every table and every column has a description stored as an *extended
property*, applied by a utility (`dbo.sp_documenta`) that every DDL
script uses.

The view `gold.vw_glossario_dados` exposes this as a queryable table,
with type, nullability, column role and business description. It is the
source of the [glossary](../glossario.md) (Portuguese) and can become a
page in Power BI itself.

Keeping the documentation in the database, rather than in a separate
document, has a practical reason: it travels with the backup, is not
lost in a folder reorganization, and sits next to the object it
describes — which is where someone looks when they have the question.
