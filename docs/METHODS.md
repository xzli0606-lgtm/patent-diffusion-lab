# Methods and implementation coverage

## Operational definitions

The analysis unit is a focal DOCDB simple family in an existing 1:1 matched pair.
A citation event is a unique external citing-family/focal-family edge with a
canonical date and whole WIPO35 citing-field set. Within-family links are excluded.
The cutoff is 2026-06-30. Windows end on the 1st, 3rd or 5th Gregorian anniversary
of the grant; both matched members must have complete follow-up.

H1 is any external-family citation by the horizon. H3 is any arrival into a
non-focal WIPO35 field. H4 requires a second distinct citing family in the same
external field on a date strictly later than that field's first arrival. The
family-level establishment time t0 is the earliest H4 among external fields.
H5 is the first arrival into an external field whose first arrival is strictly
after t0. It cannot occur without H4. A field reached on t0, or previously reached
but not established, is not a new field for H5. Same-day order never creates H4.

Example with focal field 1: family A reaches field 2 on day 10; B also reaches
field 2 on day 10; C reaches field 2 on day 20; D first reaches field 3 on day 20;
E first reaches field 4 on day 21. H3 = day 10, H4 = day 20, H5 = day 21. B alone
cannot establish, and D cannot count as post-establishment new-field arrival.

## Basic comparisons

- Matched-pair conditional logistic ORs use discordant pairs.
- Pair-stratified Cox models use Efron ties and matching-cell clustered scores;
  duration is elapsed days plus one. The repaired implementation resets row
  indices before aligning score residuals to matching cells.
- A PH diagnostic can trigger frozen 0–1, 1–3 and 3–5-year piecewise fits.
  Unidentified/singular or nonconvergent piecewise fits are explicitly unavailable.
- Established/new-field counts use conditional pair fixed-effect count ratios.
- Holm adjustment covers six H4/H5 incidence tests (two endpoints × three windows).

The H3 event-time output is an additional prototype diagnostic; the paper's H3
primary endpoint is binary cross-field reach. Do not present all Cox outputs as
published primary paper estimates. Finite primary logistic/count estimates
require informative outcomes in both groups. No continuity correction is invented
when a main estimate is unavailable.

## Main opportunity-conditioned reference

Matched pairs are assigned to five deterministic folds. Donors exclude the target
pair's whole fold. Pools combine AI and non-AI events within focal WIPO35,
citation-lag band (<=12, >12–36, >36–60 Gregorian months) and citation calendar
three-year block anchored at 2019. Fallback first drops calendar, then lag,
without crossing focal WIPO35. A donor pool needs >=200 edges and >=50 distinct
citing families. Unsupported events exclude the affected pair from this estimand.

Each focal family's event counts and dates stay fixed. Whole field masks are
resampled and the same H3/H4/H5 event algorithm is applied. Outputs include the
observed AI-minus-non-AI gap, expected reference gap and their difference in
percentage points. The pair bootstrap conditions on the estimated pools.

Normal settings start at 2,000 reference draws and add 2,000 up to 10,000 until
both H4 and H5 MCSE are <=0.1 percentage points. Bootstrap defaults to 2,000 draws.
Smoke mode caps these at 50 and 200 and carries no precision-pass claim.
Frozen seeds: folds 20260918, simulations 20260919 plus replicate index,
bootstrap 20260920. The separate `--seed` controls pair sampling only.

## Coverage by entry point

`reproduce` executes the full v4 analysis profile: main models, common/non-AI/grant-cohort references, rebuilt-pool bootstrap, third-family endpoint, stricter field rules, missingness bounds, fixed-cohort/top-tail/AI-label sensitivities, waiting times and prespecified Holm families. See [reproduction](REPRODUCTION.md).

`compare` accepts explicit country or technology groups and fits exact-matched incidence and entry-time models. `analyze` retains the original sampled canonical-input workflow. None retrieves databases or trains labels. Original source-population matching is upstream; generic matching is explicitly configured and audited.

The reference is conditional descriptive evidence. It does not identify causal
effects, mediation proportions, adoption, commercial use or mechanism shares.
Different windows have different eligible cohorts and cannot establish a single
cohort's transition process.
