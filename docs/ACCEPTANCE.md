# Version 0.2.0 acceptance / 验收记录

Recorded 2026-10-14. Real study inputs are not distributed in this repository.

| Check | Executed result |
|---|---|
| Full analysis from preprocessed family/event inputs | Completed |
| Fresh-environment full analysis from the two ZIPs | Completed in 34 min 38.43 s; exit 0 |
| Manuscript numerical checklist | 410 / 410 PASS in both runs |
| Parsed full-result outputs between runs | 59 / 59 exactly equal |
| Additional comparison against frozen formal archives | 834 raw scalar values exactly equal |
| Independent chronological event scanner | 464,516 families; 3,944,388 edges; zero date/indicator mismatches |
| Automated tests including local UI integration | 26 passed |
| Real-data public/reviewer redistribution permission | Unconfirmed; data retained locally |
| Upstream database extraction and original cohort construction rerun | Not performed |

The cold-start environment installed the locked dependencies into a new virtual
environment. Analysis used only the source snapshot and both data archives. A
Python audit hook denied network connections and access to the original research
directories. Original results were used only in subsequent comparisons. The
recorded maximum resident set size was 3,126,216 KiB for a process/child measured
by GNU time; this is not the aggregate memory of all three parallel workers.

All 18 Parquet result tables and all parsed JSON/CSV result values agreed exactly.
Source-path separators and hashes of differently serialized JSON are metadata:
each source hash was verified against its own file, while parsed values were
compared separately. No numerical tolerance was relaxed. The predeclared raw
tolerance was rtol=1e-8, atol=1e-10; exact equality was achieved.

The final scientific calculation modules match the cold-run source hashes.
Subsequent changes harden ZIP manifest validation and add an independent audit
entry point, tests and documentation. The final ZIP validator and independent
scanner were rerun against the same two archives and cold-run outputs.

The one-year H3/H4/H5 piecewise time models are explicitly non-estimable because
only one prespecified interval exists. This is a structural diagnostic, not an
omitted estimate presented as successful. Three- and five-year models ran.

## Boundary / 边界

These checks establish reproducibility of the listed manuscript results from
the supplied preprocessed inputs. Source-roster files allow sample-flow counts
to be recounted, but do not independently prove completeness of the original
PATSTAT query, family construction, AI label acquisition or original matching.
They do not establish causal effects, organizational adoption, predictive
performance, or data redistribution rights.

410项论文数值和全样本事件逻辑均已验收。两个数据包足以重算本次清单中的分析结果，
但不能等同于从原始数据库重新抽取并验证全部上游构造过程。通用CLI与本地界面支持
用户明确分组的同领域跨国、跨技术路线匹配比较；完整机会参照及论文敏感性分析通过
冻结的 `reproduce` 配置运行，尚未整合为通用界面选项。

See [reproduction instructions](REPRODUCTION.md), [portable guide](PORTABLE_GUIDE.md)
and [distribution review](DISTRIBUTION_REVIEW.md).
