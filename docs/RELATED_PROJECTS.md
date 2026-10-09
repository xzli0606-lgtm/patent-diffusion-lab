# GitHub 同类项目调研与实现取舍

检索日期：2026-10-09。目标是为 Patent Diffusion Lab 选择合适的开源交付形式。
这是限定范围的仓库调研，不是穷尽搜索、软件性能评测或方法新颖性证明。

## 检索与核验方法

使用 patent/PATSTAT/citation network、patent analysis Python、bibliometrics/scientometrics、reproducible scientific Python package 等组合检索，沿 README 中的关联项目扩展。筛选优先考虑领域相关性、可安装性、真实代码目录、示例/测试、许可证正文和维护时间，而非星数。
对下列12个仓库读取 GitHub 官方元数据、最新提交、文件树及 README/许可证/部分打包配置；原始全文证据保存在本地研究输出，公开仓库只保存来源链接与元数据。未运行第三方项目，因而不声称这些项目当前可以安装或通过测试。
原始桌面论文路径在本次检查中已不存在；方法对照使用工作区已有的 v3 全文提取、2026-10-07复现对比报告和原型冻结约定。历史论文全文没有进入发布包。

## 核查结果

| 仓库 | 相关性与定位 | 许可证核验 | 最近提交日期 | 取舍 |
|---|---|---|---|---|
| [Patent2net/P2N-v3](https://github.com/Patent2net/P2N-v3/tree/43fc9500fcb65b364bd34c255e235efc4b9670b4) | 专利采集与统计分析套件 | CeCILL-B (license text) | 2024-02-06 | 学习面向研究者的安装与导出说明；其采集、Web和Docker体系不进入当前版本。 |
| [JYProjs/patentpy](https://github.com/JYProjs/patentpy/tree/be573fcbeb0b05abe4541b3f15dcb9ef9434e538) | USPTO数据转表格的Python包 | MIT | 2022-02-09 | 借鉴简短安装命令、输入/返回值和可运行示例；数据采集保持在本工具上游。 |
| [cverluise/PatCit](https://github.com/cverluise/PatCit/tree/a2a5d7fa6664b2f33edfe60d353c13bf5f97fb84) | 专利非专利文献引用提取/增强 | MIT | 2020-12-23 | 借鉴按数据产品和复现步骤组织文档；不引入其NPL提取流程。 |
| [cortext/patstat](https://github.com/cortext/patstat/tree/ae02ee130ecfe21cef3096a73e0a167fdee22481) | PATSTAT清洗与增强SQL脚本 | MIT | 2020-11-16 | 借鉴记录数据来源和分类规则；不把数据库重建变成开源用户的入门门槛。 |
| [volfpeter/uspto-patent-citation-graph](https://github.com/volfpeter/uspto-patent-citation-graph/tree/9f24422d62fedd38ebcbbf7437bb5960abf78bd5) | 按需采集专利引用图 | MIT | 2025-05-05 | 借鉴小型Python包和最小调用示例；不添加在线API、缓存数据库或图遍历功能。 |
| [SciSciCollective/pyscisci](https://github.com/SciSciCollective/pyscisci/tree/acd38735ae1b23cf8b668e8947ccd833ca60ccac) | 科研计量指标与网络分析库 | MIT | 2026-08-04 | 主要参照：指标与示例对应，方法、API和数据接入分层；本项目保留四里程碑专长。 |
| [dspinellis/alexandria3k](https://github.com/dspinellis/alexandria3k/tree/479a00689464c41837096a86f457b32f1d48ce87) | 可复现计量研究的CLI与Python接口 | GPL-3.0 (GitHub detection) | 2026-07-26 | 主要参照：CLI、文档、examples、tests、CITATION.cff和打包元数据；不复制GPL实现。 |
| [mirkolai/pybiblionet](https://github.com/mirkolai/pybiblionet/tree/045f250381a8588966c47d2139be6105a2c3347c) | 文献引文与合作网络指标 | GPL-3.0 (GitHub detection) | 2026-03-30 | 借鉴面向具体分析任务的说明与软件引用；不引入NLP模型或网络中心性计算。 |
| [KonstantinosPetrakis/PatentInspector](https://github.com/KonstantinosPetrakis/PatentInspector/tree/1823e25ee697ce3720aa1a5f5a6f63521ac1767e) | Django/Vue专利分析Web应用 | GPL-3.0 (GitHub detection) | 2023-12-01 | 作为前后端成本对照；其数据库、API和界面较重，当前选择离线包与报告。 |
| [scientific-python/cookie](https://github.com/scientific-python/cookie/tree/55ef55c2b406c7a4a2244ff246506d823e640ad6) | 科学Python工程指南与模板 | BSD-3-Clause | 2026-10-07 | 主要工程参照：pyproject元数据、测试和CI；只采用当前所需部分。 |
| [timtroendle/cookiecutter-reproducible-research](https://github.com/timtroendle/cookiecutter-reproducible-research/tree/fb6325cc343a852e995e63cb8f3bb0db24a255f4) | 可复现研究目录与报告流程 | MIT | 2025-07-14 | 借鉴演示数据、运行脚本和报告串联；当前不增加Snakemake/Pandoc/集群依赖。 |
| [mtcberlin/epo-tip-svelte-patstat-explorer](https://github.com/mtcberlin/epo-tip-svelte-patstat-explorer/tree/e00a727ddde542dbb4cff00f1fb1d6d96fef4ff6) | PATSTAT交互探索界面 | PROPRIETARY; not open source | 2026-05-21 | 排除：LICENSE.txt明确保留全部权利，公开可见不等于开源；仅记录筛选理由。 |

GitHub 返回的 NOASSERTION 不自动代表没有许可：P2N-v3 的正文是 CeCILL-B；PATSTAT Explorer 则是专有许可。最近提交时间只是维护信号，不代表质量或可运行性。

## 采用的具体形式

1. 保留轻量 Python 包及命令行。借鉴 pySciSci/Alexandria3k 的任务入口和方法说明，而不移植其算法。
2. 新用户先执行 demo：400对纯合成数据、三个窗口和主要机会参照，避免依赖私人研究环境。
3. validate 先检查字段、日期、配对与分类覆盖；analyze 读取预处理文件。数据获取与匹配不扩展到第一版。
4. README 提供最短可运行路径；详细方法、数据字典、结果解释、差异和范围放入 docs。
5. 添加可安装构建、Windows/Ubuntu CI配置、边界回归测试、许可证和软件引用信息。
6. JSON保存版本、哈希和种子；Markdown输出便于阅读。结果保持观察性解释。

## 保持的研究特色与边界

在已检查的README和公开目录中，没有发现明确宣称同时实现本研究严格H4、H5定义、原有配对模型与相同机会参照约定的项目。这只是本次检索的观察，不能证明全球不存在同类实现，也不构成论文新颖性结论。
本项目重点在日期顺序、不同引用族、完整WIPO35集合、同日排除以及保留引用机会的参照，而不是通用专利检索、中心性排名或NLP。已有修复后的研究算法继续作为计算基础。

## 本轮不采用的扩展

暂不加入前后端、账号系统、在线数据上传、云数据库、专利API和大模型。PatentInspector等表明这些功能涉及独立的部署和维护体系；当前公开入口无需这些部件即可运行。后续若做交互界面，应复用经过测试的计算包。

## 代码来源与许可证

本次借鉴是工程组织和用户使用流程层面的参考，没有从上述仓库复制或翻译实现代码。各项目许可证不转授给本项目；Patent Diffusion Lab采用用户确定的Apache-2.0。现有研究脚本来源保留在PROVENANCE.json。
完整检索快照、固定提交和检查文件链接见 [REPOSITORY_SNAPSHOT.json](REPOSITORY_SNAPSHOT.json)。
