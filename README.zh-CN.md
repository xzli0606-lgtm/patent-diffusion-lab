# Patent Diffusion Lab

[English](README.md) · [方法契约](docs/PORTABLE_V1_METHODS.md) · [准备与教程](docs/PREPARE_V1.md) · [标准输入](docs/INPUT_SCHEMA_V1.md) · [结果解释](docs/VALIDATION_V1.md)

**郑州大学管理学院 · 姜红丙、李旭泽**

**版本 1.0.0 · Python 3.12 · Apache-2.0**

Patent Diffusion Lab 根据本地专利族与引用事件记录分析专利引用扩散，提供引用里程碑、两组匹配比较和交叉拟合机会参照，以及可追溯的输入、可复现的配置与数值报告。

标准输入研究使用 `compare --profile portable_v1`；配套论文的冻结分析使用 `reproduce`。两条流程的统计设定不同，详见[论文复现](docs/REPRODUCTION.md)与[通用方法契约](docs/PORTABLE_V1_METHODS.md)。

## 安装与合成教程

创建并激活 Python 3.12 虚拟环境后，在源码目录执行：

```sh
python -m pip install -r requirements.lock
python -m pip install --no-deps .
python -m patent_diffusion --version
python -m patent_diffusion.demo_v1 --output tutorial
python -m patent_diffusion prepare --source patstat-local --manifest tutorial/manifest.json --output tutorial/prepared
python -m patent_diffusion validate --profile portable_v1 --families tutorial/prepared/families.parquet --edges tutorial/prepared/events.parquet --config tutorial/comparison.json
python -m patent_diffusion compare --families tutorial/prepared/families.parquet --edges tutorial/prepared/events.parquet --config tutorial/comparison.json --output tutorial/result
python -m patent_diffusion ui --workdir local-ui
```

安装本地 wheel 时，将源码安装命令替换为 `python -m pip install --no-deps path/to/patent_diffusion_lab-1.0.0-py3-none-any.whl`。安装阶段需要依赖，分析阶段离线运行。每次使用新的输出目录，不覆盖、不自动续跑。

教程生成六张合成关系表，经同一个 PATSTAT 适配器得到 320 个焦点族、1,004 条去重引用边、62 个零引用族。示例四项 IPC 映射完全虚构，不能用于真实专利分类。默认 `smoke` 仅诊断；正式研究须事先把 `execution.mode` 改为 `formal`。正式模拟预算、供体阈值和最低有效簇数不能随效果调节。

查看 `report.html`、`results.json`、`method_contract.json`、`run.json` 和 `output_manifest.json`。`COMPLETED_WITH_LIMITATIONS` 表示存在不可估计或精度不足的模块，不能解释为全部成功。退出码 0 包括带限制的完成，FAILED 为 2；解释结果时须同时检查模块状态。

## 输入、方法与边界

支持 DOCDB 简单族、WIPO35、两个明确组别、同领域精确 1:1 无放回匹配、1–5 年完整日历观察窗。标准输入为 CSV/Parquet；原始准备支持本地 PATSTAT 导出，不包含登录、远程提取或云端计算。

H1 为首次外部族引用；H3 为首次非焦点领域到达；H4 为同一外部领域在严格更晚日期获得第二个不同族引用；H5 为最早 H4 后严格更晚日期出现此前未到达的新领域。它们描述引用事件，不直接代表采纳、吸收或因果机制。

提供条件 OR、配对分层 Cox、分类覆盖与有效簇门槛、五折配对交叉拟合、同领域支持回退、整组领域集合抽样、预设精度、匹配单元 bootstrap 与固定支持供体重加权敏感性。不可估计时保留描述结果并明确原因。所有参照残余均在同一支持样本上计算，不报告“机制解释份额”。

网页与 CLI 共用算法，可导入/导出配置、查看进度、取消、下载汇总报告。PATSTAT 原始准备走 CLI。默认下载不含族表和事件表；来源声明、汇总结果仍可能涉及敏感信息，公开权限由数据使用者判断。

## 论文复现

按[论文复现说明](docs/REPRODUCTION.md)使用同一版本的两份研究输入包计算论文结果。数值参考仅由计算完成后的独立验证命令读取。论文分析设定与随机种子保持固定。

早期通用比较配置可通过 `compare --profile legacy_v0_2` 使用；新的标准输入研究使用 `portable_v1`。两条流程的统计区别，包括供体重加权方法，见[方法契约](docs/PORTABLE_V1_METHODS.md)。

## 开发与复现记录

```sh
python -m unittest discover -s tests -v
python -m build
python tools/check_release.py
python -m twine check dist/*
```

状态码、精度要求和复现记录见[结果解释](docs/VALIDATION_V1.md)。研究者使用自己获准访问的本地记录，具体要求见[数据政策](DATA_POLICY.md)与[来源说明](docs/DISTRIBUTION_REVIEW.md)。合成教程数据由程序生成。引用软件请使用 [CITATION.cff](CITATION.cff)。
