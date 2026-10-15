> Historical 0.2/paper documentation. For the current default use [portable_v1](PORTABLE_V1_METHODS.md) and [preparation](PREPARE_V1.md). Old comparison commands require `--profile legacy_v0_2`; historical outputs are not new portable validation.

# Two-group comparison / 两组专利比较

Use Python 3.12 and install the exact dependencies in `requirements.lock`.
The workflow begins with local tables. No EPO account, server password, database
connection or original research directory is needed by the analysis commands.

流程从本地数据开始：校验字段、精确匹配、重建观察窗、计算里程碑、估计组间差异并导出报告。
账户登录和数据下载不属于自动化流程。

```sh
python -m pip install -r requirements.lock
python -m pip install --no-deps .
python -m patent_diffusion ui --workdir outputs/local-ui
```

Open the printed loopback address in your browser. Upload CSV/Parquet family and
event tables, explain the two groups, choose dates/windows, map column names, and
run. The resulting report and ZIP remain on your computer. Stop with Ctrl+C.

打开终端给出的本机地址，导入两个表、填写分组依据、设置日期和观察窗、映射字段，即可校验、
运行和下载。输入不会上传到互联网。大于1 GiB的文件请使用命令行。

## Input tables

| Family field | Meaning / 含义 |
|---|---|
| family_id | Globally unique family ID / 全局一致的专利族标识 |
| grant_date | Focal grant calendar date / 焦点授权日 |
| focal_field | WIPO35 integer 1–35 / 焦点技术领域 |
| group | One of the two configured group labels / 明确且互斥的组别 |
| additional matching columns | Optional exact-matching variables / 自定义精确匹配变量 |

| Event field | Meaning / 含义 |
|---|---|
| family_id | Cited focal family / 被引焦点专利族 |
| citing_family_id | Distinct citing family / 不同的引用专利族 |
| event_date | Earliest eligible citing-publication date / 首次合格引用公开日 |
| field_mask | Full WIPO35 field set as an integer / 完整领域集合的位掩码 |
| classification_missing | Boolean; true retains an unclassified event / 分类缺失标识 |

For fields `{2,4}`, `field_mask = 2**(2-1) + 2**(4-1) = 10`.
Never choose one field from a multiple-field event. Keep zero-citation families.
There must be one event per focal/citing-family pair; duplicates are rejected.
Dates are calendar dates without time zones. Grant anniversaries are inclusive;
29 February becomes 28 February in a non-leap anniversary year.

## Configuration and CLI

Save the following as `comparison.json`:

```json
{
  "comparison_type": "technology",
  "groups": ["Route A", "Route B"],
  "group_definition": "Mutually exclusive technical routes assigned by the researcher",
  "cutoff": "2026-06-30",
  "windows": [1, 3, 5],
  "matching_columns": ["grant_quarter", "focal_field"],
  "matching_seed": 20260907,
  "family_columns": {},
  "edge_columns": {}
}
```

```sh
python -m patent_diffusion compare --families families.csv --edges events.csv --config comparison.json --output outputs/comparison
```

Column maps use original names as keys and canonical names as values. For example,
`"family_columns": {"patent_family": "family_id"}`. Results are Group A minus Group B.
Matching is deterministic and without replacement, within exact configured strata.
The tool requires focal field in the strata and stops if no pairs have common support.
It reports candidate counts, matched pairs, unmatched fractions, strata, complete
follow-up pairs, classification-complete pairs, incidence, ORs and entry-time HRs.
Non-estimable models are reported explicitly, never replaced with invented estimates.

字段映射采用“原字段名: 标准字段名”。结果方向为A组减B组。未匹配样本、共同支持和不同窗口的
分母均保留在报告中。四个累积结果不是独立转移；组间差异不是因果效应。

For country comparisons set `comparison_type` to `country`, provide the group
labels and `country_basis`: `applicant`, `inventor`, `priority`, `grant_office`, or
`other_explicit`. Explain mixed-country assignment in `group_definition`. The tool
does not infer nationality or duplicate a family for multiple granting offices.

国家比较必须明确申请人国家、发明人国家、优先权国家或授权局。跨国专利族需先制定互斥分组规则，
一族保留一行。技术路线由使用者定义；工具不自动判定路线。

The generic command currently fits matched incidence and entry-time models.
Full opportunity-reference alternatives and all paper sensitivities use the frozen
paper `reproduce` command. These are not automatically imposed on a new country's
data. The older `analyze` command remains available for canonical matched input.

## Runnable synthetic example

```sh
python -m patent_diffusion.demo_compare --output outputs/example-input
python -m patent_diffusion compare --families outputs/example-input/families.csv --edges outputs/example-input/events.csv --config outputs/example-input/comparison.json --output outputs/example-result
```

This generated example is synthetic and cannot validate the manuscript.
