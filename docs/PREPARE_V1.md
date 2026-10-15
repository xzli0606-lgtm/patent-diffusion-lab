# Preparing local PATSTAT records / 本地 PATSTAT 数据准备

## Verified source contract / 已核实来源契约

The adapter `patstat_local_v1` was checked against the **EPO PATSTAT Global Spring data catalog, version 5.25**. [Official EPO catalog](https://link.epo.org/web/searching-for-patents/business/patstat/data-catalog-patsat-global-spring-en.pdf). This is field/schema verification, not a claim to have queried a licensed live database. Other catalog versions require a new explicit verification.

适配器按该版本官方数据字典定义表与字段；研究者需核查实际导出的完整性。使用其他版本时，应先确认字段及其语义兼容。

| Local table | Verified PATSTAT fields | Meaning / 含义 |
|---|---|---|
| applications | TLS201_APPLN: APPLN_ID, DOCDB_FAMILY_ID | application → DOCDB simple family / 申请归族 |
| publications | TLS211_PAT_PUBLN: PAT_PUBLN_ID, APPLN_ID, PUBLN_DATE, PUBLN_AUTH, PUBLN_FIRST_GRANT | dated publication, office, Y/N first grant / 公开日、局、首次授权 |
| citations | TLS212_CITATION: PAT_PUBLN_ID, CITED_PAT_PUBLN_ID, CITED_APPLN_ID | citing publication → cited publication or application / 引用指向被引 |
| classifications | TLS209_APPLN_IPC: APPLN_ID, IPC_CLASS_SYMBOL | all IPC records for exported family members / 族成员全部 IPC |
| mapping | TLS901_TECHN_FIELD_IPC: IPC_MAINGROUP_SYMBOL, TECHN_FIELD_NR | versioned IPC main-group → technology field / 带版本主组映射 |
| roster | researcher: DOCDB_FAMILY_ID, GROUP, PRIMARY_IPC_CLASS_SYMBOL | focal universe, explicit group, justified primary IPC / 候选名册、分组、主分类 |

Catalog verification includes the TLS901 table (PDF page 89), PUBLN_DATE (page 301; unknown sentinel 9999-12-31), and PUBLN_FIRST_GRANT (page 302; Y/N). Column names are case-insensitive after an optional explicit original→canonical column map. Identifiers remain opaque strings; zero is only the documented dummy cited-publication/application sentinel, not a valid focal family/application ID.

字段经列映射后忽略大小写。CSV 全列按字符串读取；Parquet ID 接受字符串或无缺失整数，拒绝浮点、浮点样式文本和空值。保留前导零和超大整数。`0` 仅用于被引公开/申请的缺失哨兵；焦点族及申请不允许虚拟 0 ID。

## Export and declare / 导出与声明

Prepare the six local CSV/Parquet files. Export all applications/publications/classifications needed to resolve focal and citing DOCDB families, plus every eligible citation record through the cutoff. A roster with only positive citations is invalid for research: start with the complete focal universe, including zero-citation families. Database extraction is performed by the researcher under their access rights; this package does not connect to PATSTAT.

六张本地表必须覆盖所有需要的族成员、公开、分类及截止日前合格引用。必须先构造完整焦点名册，不能从“被引专利列表”代替总体。工具可核对连接完整性，但不能发现源数据库导出遗漏的未知记录。通过 manifest 的 `export_completeness` 明确导出范围和局限。

`python -m patent_diffusion.demo_v1 --output tutorial` creates a complete executable manifest with table paths, SHA-256, snapshot, group definition, declared office scope, cutoff, catalog version, classification version, completeness statement and policies. Replace its artificial files with your legally available exports, compute each SHA-256 using `hashlib.sha256(Path(path).read_bytes()).hexdigest()`, and record the actual provenance. Do not relabel synthetic mapping as an official mapping. Supply licensed TLS901 content locally; the package distributes only a synthetic four-main-group mapping generator.

生成器输出可执行 manifest。换成真实导出时逐项填写来源和 checksum，不要只修改文件名。`group_definition` 应包含分组及主 IPC 的选择依据与并列规则；roster 中指定主 IPC 必须实际出现在该族分类记录中，且唯一映射到 WIPO35。若依据不足，停止该适配分支，不取最小领域、不随意选日期。不同国家的授权起点可比性需由研究者判断。

## Exact transformation / 转换规则

1. Join application and publication IDs to DOCDB simple family; reject broken links and duplicate key IDs. Select the earliest dated `PUBLN_FIRST_GRANT=Y` publication in the declared office scope through cutoff. No eligible grant stops preparation.
2. Map citing publication to citing family and cited publication/application to focal family. If both cited IDs are supplied they must agree. Exclude within-family, nonfocal/nonpatent, invalid-date, after-cutoff and pre-grant records with recorded dispositions. `pregrant_policy` and `invalid_date_policy` are `stop` or `exclude_records`. Never clamp dates to grant dates.
3. Among remaining eligible records, choose the earliest event for each focal/citing family pair; ties are deterministic. All original citation rows remain in lineage, including later duplicates and exclusions.
4. Normalize IPC to main group, join the versioned mapping, union all WIPO35 fields across exported citing-family applications. Any unmapped IPC, or no classification records, yields `classification_missing=true` and mask 0. This is missing information, not a known empty external-field set.
5. Produce one focal row from the roster even when there are no events. Preserve the complete mask for multi-field families. Dates on grant/cutoff anniversaries are included.

逐步规则对应：连接归族→声明局范围内最早合格授权→公开引用映射→按策略记录排除→族对最早合格引用→全族分类集合→完整焦点名册输出。多字段不是只选一个引用领域；只有焦点唯一领域来自研究者有依据的主分类。无效日期及授权日前记录不做静默修补。

## Run and inspect / 执行与核查

Use the full commands in the README. The same adapter processes the synthetic tutorial and researcher exports. Generated `comparison.json` defaults to smoke. Its source-manifest paths are relative to that configuration file; CLI `--families` and `--edges` are relative to the shell directory. `docs/portable_v1.example.json` is an alternative fully resolved example. Runtime validation (`portable_config.resolve`) is authoritative; the bundled JSON Schema additionally documents syntactic shape.

| Output | Audit purpose / 审计用途 |
|---|---|
| families.parquet, events.parquet | canonical input including zeros / 标准输入 |
| family_lineage.csv | application→family / 申请归族 |
| grant_lineage.csv | all eligible grant candidates; family minimum is selected / 合格授权候选及最早日 |
| citation_lineage.csv | every source citation row, mapped IDs/date, disposition / 每条原始引用的去向 |
| classification_lineage.csv | original IPC, main group, mapped field and family / 分类连接 |
| source_manifest.json | declarations, scope, cutoff and limitations / 来源声明 |
| classification_mapping_manifest.json | version, mapping SHA-256 and union rule / 映射追踪 |
| preparation_audit.json | row counts, exclusions, duplicates, zero-citation families / 流程计数 |
| output_manifest.json | byte hashes of generated files / 输出校验 |

Keep the original export manifest and all six source files locally: their hashes bind lineage to the input. The adapter never uploads them. Do not distribute lineage from real records merely because software code is open-source. Standard-input users must supply a source manifest with dataset_kind (`synthetic` or `researcher_supplied`), source, snapshot, family_definition (`DOCDB simple family`), group_assignment, classification_mapping and grant_rule; add grant_office_scope and cutoff for machine cross-checks. Missing underlying source evidence cannot be repaired by inventing declarations.

保留原始 manifest 与六张源表才能闭合追溯链。发布下载默认只有汇总；真实 lineage 同样属于真实数据。标准输入的来源声明是研究者陈述，不是软件认证，必须有可核查材料支持。
