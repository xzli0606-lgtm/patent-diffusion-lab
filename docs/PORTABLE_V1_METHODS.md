# portable_v1 method contract / 方法契约

The portable_v1 specification was fixed on 2026-10-14. It defines the portable analysis separately from the paper reproduction profile. Each run writes its resolved configuration and method contract before loading the study outcome tables. The bundled contract and schema are package resources; unknown settings and changes to fixed thresholds are rejected. New scientific designs require a distinct version and justification, not edits selected for favorable effects.

portable_v1 于 2026-10-14 固定，与论文复现配置分别定义。每次运行先保存解析后的配置与方法契约，再读入研究输入。种子、组别、授权局、截止日、窗口、匹配单元、日历/队列锚定年均进入记录，不能按研究效果反复更改。

## Population, estimands and quality / 总体、估计量、质量

Two explicit string group labels define A and B. Exact matching within declared columns (including focal field) uses a seeded hash order, no replacement, and complete pairs. Clusters equal those matching cells; alternate cluster definitions are rejected. The group comparison is A minus B and the target is the **pair-weighted** mean, not an equal-weight mean of cells. All families in a pair must have a complete calendar-year window (1–5 years). Grant day and final anniversary are included; Feb 29 plus one year uses Feb 28. Zero-event families stay in the denominator.

两组按指定单元精确匹配；匹配与聚类单元一致，不能暗中更换协方差。每个匹配对等权，单元大小不同时用总和之比保留配对加权含义。观察窗使用日历周年、包含授权日和周年末日；闰年按日历偏移。零事件保留分母。

H1 and timing use all eligible pairs. Field endpoints exclude the whole pair if either family has an unclassified event in that window. Formal field analysis requires each nonempty group's classified-edge coverage ≥98.5%, and between-group missing-rate difference <1 percentage point when both denominators exist. An empty edge group has no missing records but an undefined edge-coverage ratio (null); zero total edges remains a legal zero-rate cohort. Failed quality permits H1/timing and explicitly exploratory complete-classification descriptions, not formal field inference.

分类排除按整对执行；报告候选边、缺失边、两组覆盖率、缺失差距和各层分母。0% 分类不能显示领域分析成功。没有候选边时覆盖率为 null，不将其伪写为 100%，但零事件观察本身合法。

Milestones: H1 first distinct external-family citation; H3 first nonfocal field arrival; H4 the second distinct family in an external field on a strictly later date; H5 first arrival of a previously unreached external field strictly after earliest H4. Same-day second families do not establish; fields appearing on H4 day do not constitute H5. Multi-field masks contribute all nonfocal bits. Third-family recurrence and fixed-longest-window cohort are supplementary sensitivities.

这些里程碑是累计嵌套事件。H4 不等于知识采纳/吸收；H5 不把 H4 当日新领域算为后续扩展。第三族规则和最长窗口固定队列结果另列，不能替换主定义。

## Models and uncertainty / 模型与不确定性

Conditional OR uses discordant matched pairs (A-only/B-only); single-cell 7:3 data therefore retain OR=7/3 while CI and p are null. Conditional-logit sandwich scores are aggregated by matching cell. Cox uses pair strata, Efron ties and matching-cell aggregated score covariance. At least 30 **informative/effective** cells are required for inferential intervals; this is a conservative version policy, not a universal theorem. Separation, convergence failure, singular/nonfinite/degenerate covariance and zero-event risk sets return reason-coded `NOT_ESTIMABLE`. Numeric tail underflow is bounded above zero. Point estimates may remain when only uncertainty is unsupported.

OR 与 Cox 的有效簇数、事件数、信息对数、收敛和不可估计原因均报告。PH 检查是 Schoenfeld 残差与秩时间相关的探索性诊断，不是聚类校正的正式 PH 检验；提示违反时单一 HR 需要谨慎。不存在有效推断时不自动换协方差，也不返回虚假的窄区间或 p=0。

## Opportunity reference / 机会参照

Matched pairs map deterministically to five folds. Donors exclude the entire target fold. Main donors pool A and B. Initial stratum: focal field × calendar-year lag band (≤1, >1–≤3, >3–≤5) × three-year calendar block. Fallback first drops calendar, then lag, **never focal field**. Every accepted pool needs ≥200 eligible edges and ≥50 distinct citing families. Unsupported events exclude their entire pair from that variant's reference estimand. Zero-event pairs need no donor draws. Shared citing families across target/donor folds are counted; pair exclusion does not eliminate all citation-network dependence.

保持每个目标族的引用次数、日期与完整领域集合抽样，改变引用族领域集合。对每个变体分别定义支持集合 S，在同一个 S 上计算 D_obs、D_ref、D_residual=D_obs−D_ref；单位为百分点。各组原始/参照率仍以 0–1 表示。变体交集额外重算两套比较，不能将不同分母结果相减。残余为条件描述差异，不是因果效应、机制份额或“被解释比例”。

Main/variant simulation starts at 2,000 draws, increments by 2,000 to 10,000, stopping when both H4/H5 MCSE ≤0.1 pp. MCSE is the simulation-replicate SD of the supported A−B reference contrast divided by sqrt(R); observations are fixed. H3 MCSE is also exposed, and its inference is withheld if it exceeds 0.1 pp. At the cap, precision failure is explicit. Smoke uses 50 draws and cannot establish formal inference.

主区间在已估计供体池条件下，以匹配单元为单位 bootstrap 2,000 次，整单元复制，以总和之比保持配对权重。区间采用 2.5/97.5 百分位；p 为以 bootstrap 标准误构造的近似双侧 Wald p，不能误称精确检验。少于 30 个支持单元或退化分布返回 null。预设主检验族为所有配置窗口的主参照 H4/H5；不可估计成员保留族大小，Holm 内部以 1 占位，展示仍为 null。敏感性不进入主检验族。

## Prespecified sensitivities / 预设敏感性

| Variant | Exactly what changes / 精确变化 |
|---|---|
| group_b_only_donors | donors restricted to the explicitly named second group; target groups unchanged / 仅限制供体组 |
| additional_grant_cohort_stratum | three-year grant cohort added to every fallback level / 授权队列条件全程保留 |
| unique_field_event_rule | score observed and simulated paths using only single-field masks; donor support/counts remain the original full path / 仅改变端点有效事件 |
| cross_only_event_rule | score observed and simulated paths excluding masks containing the focal field; original donor support remains / 同样仅改变端点有效事件 |
| reweighted_pool_fixed_support | resample matching cells; reweight donor edges by cell multiplicity within the original fixed pools / 固定支持内重加权 |

The last variant is **not full pool re-estimation**: fold assignments, support strata, fallback choices and the supported pair set remain fixed. Its outer bootstrap has 2,000 draws; each has 50 inner simulations, increments of 50 up to 2,000, H4/H5 MCSE ≤0.1 pp. Weighted sampling uses the exact cumulative sum of donor weights. An active zero-mass pool or zero target denominator fails the sensitivity explicitly. A failed inner precision check fails the whole sensitivity; no failed bootstrap is discarded. Audit records every attempted draw's inner count and MCSE. Smoke is diagnostic and has 200 outer draws with at most 50 inner draws.

旧 `_pool.py` 的固定配对支持、单路径 bootstrap 与隐式均匀 fallback 按历史原样保留，适用于重现其历史数值。新版并非仅改名：独立代码使用匹配单元权重、精确加权 CDF、零池失败和受控嵌套模拟。旧输出中的 `rebuild_pool_ci95_pp` 只能按旧版实际方法解释，不可宣称完整重估。供体池估计不确定性的主区间和这个敏感性区间也不能互换。

## Audit and statuses / 审计与状态

`run.json` records software/Python/dependency versions, code hashes and elapsed time. `input_manifest.json` has original-byte and normalized semantic hashes plus source declarations. `output_manifest.json` checks every report artifact. Sorted inputs, deterministic pair ordering and seed namespaces ensure row-order invariance. Different file formats may have different byte hashes despite equal semantic values. Replay requires the same inputs, configuration, method and environment; a new output directory is mandatory.

运行状态、模块状态和 `publication_acceptance` 分离。运行完成不保证推断成功；报告含限制即整体标记 `COMPLETED_WITH_LIMITATIONS`。所有 JSON 禁止 NaN/Infinity。论文证据状态始终不由单次计算自动确认。真实输入默认不进入报告下载，显式 `--include-data` 仅用于本地受控输出。
