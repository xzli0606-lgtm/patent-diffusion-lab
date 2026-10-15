# Standard portable input / 通用标准输入

`compare --profile portable_v1` accepts CSV (UTF-8; ID columns read as strings) or Parquet. It does not accept the old paper schema implicitly; use explicit column mappings or the historical profile. This standard input route does not certify a source adapter beyond the separately tested local PATSTAT path.

通用入口仅接受有明确数据字典和来源声明的标准表。CSV 字符串保留前导零；Parquet 浮点 ID 无条件拒绝，包括 1.0。重复 CSV 表头、映射后重名列、重复族 ID、重复族对边、同族边、缺失 ID 都报错。

| families column | Type / meaning |
|---|---|
| family_id | nonempty opaque string or exact integer in Parquet / 焦点 DOCDB 简单族 |
| grant_date | timezone-free calendar date / 声明局范围内最早合格授权日 |
| focal_field | integer 1..35 / 有依据的唯一焦点 WIPO35 领域 |
| group | string; labels must match configured groups exactly / 明确分组 |
| additional matching columns | complete values; supplied if configured / 可选匹配变量 |

`grant_quarter` is derived from grant_date. The default matches grant_quarter and focal_field. Matching and cluster columns must agree; matching must contain focal_field. Other group labels are counted as excluded, never silently assigned to A/B. Label direction is the order of `comparison.groups`.

`grant_quarter` 从授权日派生；默认匹配授权季度和焦点领域。额外匹配列必须完整，不做空值填补。其他组别行显式计入排除；数值样式组标签仍按字符串处理，例如 ["1","0"]。

| events column | Type / meaning |
|---|---|
| family_id | focal/cited family, must exist in families / 被引焦点族 |
| citing_family_id | external citing family / 引用族 |
| event_date | earliest eligible citation-publication day for this pair / 族对最早合格引用公开日 |
| field_mask | integer 0..2^35−1; bit k−1 indicates field k / 完整分类集合位掩码 |
| classification_missing | boolean true/false or 1/0 / 分类是否不完整 |

Example: fields {2,4} give mask `2 + 8 = 10`. A known complete set containing only focal field 1 has mask 1 and missing=false; it is not a cross-field event. Incomplete classification must have mask 0 and missing=true; mask 0 with missing=false is rejected. One unknown IPC makes the whole union incomplete under the local PATSTAT adapter. Zero-citation focal families remain in families with no event rows.

字段集合示例：{2,4} 对应 mask=10。只有焦点领域的已知集合与分类缺失不同，不能都填 0。事件不能早于焦点授权日、晚于截止日；标准表若包含此类记录将停止。原始关系表应先经适配器按明确策略排除并记录 lineage。

Column mappings are original-name→canonical-name, e.g. `inputs.family_columns={"my_family":"family_id"}`. Do not include a mapping that collides with an existing canonical column. Config paths for source/mapping manifests are relative to the config file; CLI data paths are relative to the current working directory.

来源声明所需字段、准备教程和完整命令见 [PREPARE_V1.md](PREPARE_V1.md)。配置实例见 [portable_v1.example.json](portable_v1.example.json)，运行时校验器还会检查语义关系与固定科学政策。
