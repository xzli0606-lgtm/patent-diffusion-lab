# Paper reproduction / 论文复现

The v4 profile starts from supplied historical family/event inputs. It does not query PATSTAT, log in to EPO, retrain AI classifiers, or read archived results to calculate estimates. Source-roster records are counted separately. Database extraction and original matching are not reconstructed from scratch.

论文配置从两个输入包开始，不登录数据库，不读取历史结果生成估计。基础名册用于重新统计筛选数量；数据获取和原始母体匹配不属于这条自动化命令。

## Run / 运行

Use Python 3.12 and both archives from the same dataset version.

```sh
python -m pip install -r requirements.lock
python -m pip install --no-deps .
python -m patent_diffusion reproduce --ai AI_patent_families.zip --nonai nonAI_patent_families.zip --output outputs/paper --jobs 3
python -m patent_diffusion.verify --output outputs/paper --targets docs/manuscript_targets.json
```

The first command computes; the second reads targets only for checking. Append `--resume` to `reproduce` for an interrupted run with unchanged code, inputs and configuration. Completed stage hashes are checked. Never overwrite a previous run.

一次计算后再单独核对，目标结果不会成为计算输入。中断后可在代码、输入和配置均未改变时使用`--resume`；各阶段保留日志、耗时和校验值。

## Implemented analyses

- Four cumulative dated milestones; complete follow-up and pairwise classification exclusions.
- Matched conditional logit, pair-stratified Cox with Efron ties, matching-cell sandwich intervals, proportional-hazards time-trend diagnostics and piecewise models.
- Exposure-adjusted citation intensity and supporting count models.
- Whole-field-set references: common, non-AI donor, grant-cohort-stratified and rebuilt pools; supported-pair exclusions remain separate.
- Third-family threshold, pure cross-field and single-field rules, fixed five-year cohort, top-one-percent citation exclusions, missing-classification extreme bounds, fixed-pair focal-score AI sensitivity, waiting times and state occupancy.
- Prespecified Holm families, tables and long-form scalar outputs.

Formal settings in `patent_diffusion/reproduce.py`: 2,000 conditional bootstrap replications; reference simulations start at 2,000 and increase to at most 10,000 until MCSE is at most 0.1 pp; 200 rebuilt-pool replications. Diagnostic `demo` and `--smoke` settings are not formal reproduction evidence.

## Seeds and corrections

| Item | Frozen setting / correction |
|---|---|
| Fold assignment | 20260918 |
| Reference simulation | 20260919 + zero-based draw index |
| Conditional reference bootstrap | 20260920 |
| Rebuilt-pool pair weights | 20260921 |
| Rebuilt-pool field draw | 20270000 + zero-based draw index |
| Third-family and arrival-conditioned bootstrap | 20260930 |
| Cox clustering | Reset row index before grouping score residuals |
| Same-field waiting | Earliest arrival among fields tied for earliest establishment |
| 5Y first cross-field gap | Underlying counts, not subtraction of rounded rates |

Settings derive from original method records, not seed searches. The older 2026-10-07 audit used different bootstrap settings and an older figure target; its failures are not silently reclassified.

## Outputs and acceptance

`validation_report.csv` retains every target, original value, computed value, difference, tolerance, source and status. `outputs/tables/` contains Table 4, Table S1, third-family and waiting-time outputs. `outputs/all_result_scalars.csv` retains every numerical result. `outputs/opportunity_reference/all_reference_results.csv` separates observed, reference and residual differences. Figures are not redrawn; numerical source outputs remain available.

Both the first full run and the fresh-environment cold start passed all **410 listed numerical targets** at manuscript precision. All 59 parsed result files agreed exactly between runs. See the [acceptance record](ACCEPTANCE.md) for executed checks and boundaries.

Counts/indicators require exact agreement. Raw numbers use predeclared `rtol=1e-8`, `atol=1e-10`; displayed results use declared rounding precision. Tolerances are not relaxed after seeing differences.

首轮和冷启动各410项数值均通过显示精度核对；59个结果文件的解析值精确一致。上游数据库重建未执行；数据分发权限不由数值一致性推导。
