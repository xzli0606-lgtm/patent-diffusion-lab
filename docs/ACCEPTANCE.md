# Reproduction checks / 复现结果核查

The paper workflow computes estimates from supplied family/event archives. `manuscript_targets.json` is read only by the subsequent verification command.

```sh
python -m patent_diffusion reproduce --ai AI_patent_families.zip --nonai nonAI_patent_families.zip --output outputs/paper --jobs 3
python -m patent_diffusion.verify --output outputs/paper --targets docs/manuscript_targets.json
```

Read `validation_report.csv` for each target's computed value, reference value, difference, precision and status. Counts and indicators require exact agreement. Displayed values use declared rounding precision; raw floating-point comparisons use `rtol=1e-8` and `atol=1e-10` where specified. These rules are fixed before comparison.

逐项检查计算值、参考值、差异、精度和状态。计数与指标要求完全一致；展示值按预先声明的精度核对，适用的原始浮点比较使用固定容差。

Stage receipts record commands, output hashes, elapsed time and exit codes. Retain these with input manifests and the software environment. Numerical comparison covers the listed results from preprocessed inputs; source extraction and original cohort construction are upstream steps.

阶段记录保存命令、输出校验、耗时与退出码，应与输入声明和运行环境一起保留。数值核对覆盖预处理输入所对应的结果，原始提取与队列构造属于上游步骤。

The one-year H3/H4/H5 piecewise models have a single prespecified interval and are reported as non-estimable. See [Paper reproduction](REPRODUCTION.md) for analyses and outputs.
