# OpenROAD Markdown 语料入库验证

日期：2026-07-16

## 目标

扩展公开资料采集器，使其不仅支持 PDF，也能安全归档采用开放许可证、以 Markdown 维护的官方 EDA 文档。

## 来源治理

- 官方仓库：`The-OpenROAD-Project/OpenROAD-flow-scripts`。
- 固定提交：`bea7dcd7be7f26d1328f6058b01cf42bf4352aa2`。
- 许可：BSD-3-Clause。
- 下载域名：仅允许 `github.com` 和 `raw.githubusercontent.com`。
- 每份资料保存固定提交 URL、原始 Markdown、SHA-256、许可证和规范化前置信息。
- 不使用浮动的 `master` 文档作为可恢复版本。

## 新增语料

| 文档 | 切片数 | 主要覆盖 |
| --- | ---: | --- |
| OpenROAD Flow Configuration Variables | 60 | PPA/QoR、布局密度、CTS、routing、STA 配置 |
| OpenROAD Flow Scripts Overview | 8 | RTL-to-GDSII 全流程、工具分工、signoff |
| OpenROAD Flow Scripts RTL-to-GDSII Tutorial | 64 | 综合、floorplan、placement、CTS、routing、DRC/LVS、调试 |
| 合计 | 132 | 芯片设计与 EDA/IP |

入库后芯片设计与 EDA/IP 知识库包含 12 个完成文档、3372 个切片；四个半导体知识库合计 5448 个真实切片。数据库切片统计与 Milvus 实体数一致。

## 真实检索

评测问题：

1. RTL-to-GDSII 完整流程与工具。
2. `PLACE_DENSITY`、`CORE_UTILIZATION`、时钟约束与 PPA/QoR 调优。
3. routing、DRC、LVS、拥塞与时序报告。

Top-5 时第一个问题缺少相邻的 routing 片段，严格评测为 2/3；Top-6 时三个问题均包含完整证据，结果为 3/3。DeepScout 的本地检索默认 Top-10，因此实际 Agent 路径覆盖该证据范围。机器可读结果见 `reports/openroad_retrieval_2026-07-16.json`。

## 实现边界

当前 Markdown 管线适合固定 commit 的单文件官方文档。它不会递归抓取整个 Git 仓库，也不会自动跟随相对链接或把代码、图片和第三方 PDK 一并入库。这样可以控制版权范围、噪声和向量成本。
