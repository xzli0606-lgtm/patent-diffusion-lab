# Patent Diffusion Lab / 专利引用扩散分析工具

[English](README.md) · [方法说明](docs/METHODS.md) · [数据字段](docs/INPUT_SCHEMA.md) · [GitHub 调研与借鉴](docs/RELATED_PROJECTS.md)

**郑州大学管理学院 · 姜红丙、李旭泽**

本工具将论文中的四个累积引用里程碑、配对基础比较和机会条件参照整理为可本地运行的 Python 包。
当前是实验版：沿用论文方法和修复后的复现实现，记录与论文显示值的差异。
尚不包含全套论文敏感性分析，也不是新的全量复现报告。

## 四个里程碑

| 指标 | 含义 |
|---|---|
| H1 | 首次获得外部 DOCDB 专利族引用 |
| H3 | 首次到达非焦点 WIPO35 领域 |
| H4 | 同一外部领域在严格更晚日期获得另一个不同专利族的引用 |
| H5 | 最早 H4 之后，首次到达截至 H4 仍未到达的新外部领域 |

H2 是历史代码中“首次引用时间”的标签，不是第五个里程碑。
同日重复引用不构成 H4；已到达但未扎根的领域不算 H5 新领域。
这些指标是嵌套的累积结果，不能解释成因果阶段转换。

## 先运行不需要真实数据的示例

```sh
git clone https://github.com/xzli0606-lgtm/patent-diffusion-lab.git
cd patent-diffusion-lab
```

准备 Python 3.12，在本项目目录建立并激活虚拟环境，然后执行：

```sh
python -m pip install -e .
python -m patent_diffusion demo --output outputs/demo
```

示例在本地生成 400 对完全合成的专利族，运行 1/3/5 年窗口、配对模型与主要机会参照。
不需要账号、数据库权限或私人研究文件。首次运行需编译 Numba 内核，可能稍慢。
结果位于 `outputs/demo/results/report.md` 和 `run.json`；合成数据不会和论文值作实证比较。
再次运行时换一个输出目录，已有结果不会被覆盖。

## 使用自己的预处理数据

```sh
patent-diffusion validate --families data/families.parquet --edges data/edges.parquet
patent-diffusion analyze --families data/families.parquet --edges data/edges.parquet --output outputs/my-run --pairs 10000 --smoke
```

输入是已经匹配、已有 AI 标识、已归并到 DOCDB 族的两张 Parquet 表。
字段与去重规则见 [INPUT_SCHEMA.md](docs/INPUT_SCHEMA.md)。程序不查询 PATSTAT，也不重新匹配。
程序会先把完整输入表载入内存，再抽取配对；`--pairs` 不能限制输入读取占用的内存。
时间截点固定为 2026-06-30，随访窗按公历周年计算。

`--smoke` 最多使用 50 次参照模拟、200 次 bootstrap，仅用于诊断。
去掉此参数后使用主要参照的正式计算量和 MCSE 停止规则，但仍不是论文全部流程。
机会参照不足或精度不达标会在状态中体现；部分分段 Cox 无法估计时会明确记录，不填造数值。
极小样本或完全分离导致主比较没有有限估计时，程序停止并给出原因。

## 如何阅读结果

结果报告配对发生率、优势比、Cox 时间诊断、领域数模型、参照支持范围和剩余差异。
输入 SHA-256、软件版本、依赖版本、随机种子及方法约定哈希随 `run.json` 保存。
真实输入与论文全量值的差异是描述性诊断，不是复现通过/失败判定。
机会参照剩余差异也不是因果效应、机制份额或中介效应。

## 开源与署名

代码、工具文档和合成示例生成器使用 [Apache-2.0](LICENSE)。
项目署名为郑州大学管理学院，姜红丙、李旭泽，引用信息见 [CITATION.cff](CITATION.cff)。
真实数据、私人输出和论文全文不随仓库发布，见 [数据发布规则](DATA_POLICY.md)。
第三方库保持各自许可证。

本项目借鉴了相近开源软件的组织与交付方式，没有复制它们的实现代码。
调研范围、具体提交和选择依据见 [RELATED_PROJECTS.md](docs/RELATED_PROJECTS.md)。
