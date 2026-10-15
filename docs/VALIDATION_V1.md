# Interpreting and checking results / 结果解释与核查

## Execution modes / 运行模式

`smoke` provides a short diagnostic run for installation and input preparation. `formal` applies the simulation budgets, support requirements and uncertainty rules in the [method contract](PORTABLE_V1_METHODS.md). Set the study configuration before examining group differences.

`smoke` 用于检查安装、输入与流程；`formal` 使用方法契约规定的模拟预算、支持要求和推断规则。查看组间差异前固定研究配置。

| Status | Interpretation / 含义 |
|---|---|
| COMPLETED | Processing and applicable module checks completed / 流程及适用模块检查完成 |
| COMPLETED_WITH_LIMITATIONS | Inspect estimation, coverage and precision restrictions / 检查估计、覆盖及精度限制 |
| NOT_ESTIMABLE | Model or interval unsupported; read its reason code / 不支持模型或区间估计，查看原因码 |
| PRECISION_NOT_MET | Simulation budget reached before the specified MCSE / 达到模拟预算后仍未满足预设 MCSE |
| FAILED | Processing stopped; inspect error and input validation / 流程停止，检查错误及输入校验 |

CLI exit code 0 includes completion with limitations; exit code 2 denotes failure. Review effective clusters, matching retention, classification exclusions, reference support and estimand denominators alongside coefficients.

退出码 0 包括带限制的完成，退出码 2 表示失败。解释系数时，应同时检查有效聚类数、匹配保留率、分类排除、参照支持及各估计量分母。

## Reproducibility record / 复现记录

Keep input files and source manifests with `configuration.json`, `method_contract.json`, `run.json`, `input_manifest.json` and `output_manifest.json`. Repeat analyses in a new directory with the same software, locked dependencies, inputs and configuration. Compare numerical values and semantic input hashes; byte hashes may differ across file serialisations.

保存输入、来源声明、配置、方法契约、软件环境和输入输出校验。重跑使用新目录，同时核对数值和语义哈希。

Independently recount milestone dates, including zero-event families and same-day citations. For new studies, document coverage and fix the research question, groups, field assignment, office scope, cutoff, windows, matching cells, seeds and audit sample before reading effect estimates. Software tests assess implementation; scientific applicability requires evidence from the study population.

独立核算里程碑时检查零事件族和同日引用。新研究须记录覆盖范围，在查看效果前固定问题、组别、领域、授权局、截止日、窗口、匹配单元、种子和核查样本。软件测试检验实现，科学适用性需要研究总体的证据。

## Software checks / 软件检查

```sh
python -m unittest discover -s tests -v
python -m build
python tools/check_release.py
python -m twine check dist/*
```

Tests cover identifiers, date boundaries, zero events, classification coverage, matching, inference guards, donor weighting, precision failures, replay and local browser operations. Numerical paper checks use the [reproduction workflow](REPRODUCTION.md).
