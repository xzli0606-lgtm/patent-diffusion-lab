# Data sources and access / 数据来源与获取

Patent Diffusion Lab processes researcher-supplied local records. The software licence covers code, documentation and synthetic generators; external data follow the relevant provider's terms.

工具处理研究者提供的本地记录。软件许可适用于代码、文档与合成数据生成器；外部数据按提供方的条件获取和使用。

| Source | Use and preparation |
|---|---|
| [EPO PATSTAT](https://www.epo.org/en/about-us/observatory-patents-and-technology/observatory-tools/patstat) | Application, publication, family, citation and IPC records; local exports are described in [PREPARE_V1.md](PREPARE_V1.md). |
| [USPTO AI Patent Dataset](https://www.uspto.gov/ip-policy/economic-research/research-datasets/artificial-intelligence-patent-dataset) | AI labels where required by the study design; record the release and definition. |
| [AIPat](https://github.com/yusu2022/AIPat-Data-and-Methods-for-Identifying-Artificial-Intelligence-Related-Patents) | Patent-level AI scores where applicable; preserve attribution and the score threshold. |
| [PatentsView](https://data.uspto.gov/support/transition-guide/patentsview) | Bibliographic and classification resources; check identifier, family and classification compatibility. |

Retain source edition, export date, coverage, identifier definitions and mapping version. Obtain records needed to resolve focal and citing families through the cutoff. A citation-only extract cannot establish a complete focal population including zero-citation families.

保留来源版本、导出日期、覆盖、标识符定义和映射版本。记录须覆盖截止日前所需焦点族与引用族；仅有正引用记录的提取不能代表含零引用族的完整总体。

The synthetic tutorial requires no external data access. Before sharing records or derived tables, check their governing terms and institutional arrangements. See [DATA_POLICY.md](../DATA_POLICY.md) for local handling and issue-reporting guidance.
