# 半导体公开语料扩充记录

日期：2026-07-16

## 本轮新增全文

1. RISC-V Debug Specification 1.0：芯片设计、验证与调试接口。
2. NIST IR 8577：2024 年半导体与微电子标准、Chiplet、先进封装计量。
3. Metrology Gaps in the Semiconductor Ecosystem：前道工艺、材料、设备和先进封装计量缺口。
4. The Vision for the National Advanced Packaging Manufacturing Program：Chiplet、基板、热与电源、测试和可靠性。
5. Vision for Success: Facilities for Semiconductor Materials and Manufacturing Equipment：电子气体、湿化学品、光刻设备、沉积、刻蚀、检测和供应链。

全部资料来自 NIST 或 RISC-V International 的官方 HTTPS 端点，具有明确的公开使用或 CC-BY-4.0 权利信息，PDF 下载与文本抽取均成功。

## 入库结果

| 知识库 | 完成文档 | 切片数 |
| --- | ---: | ---: |
| 芯片设计与 EDA/IP | 9 | 3240 |
| 半导体材料与设备 | 8 | 656 |
| 晶圆制造与前道工艺 | 8 | 718 |
| 封装与测试 | 8 | 702 |
| 合计 | 33 个领域内文档实例 | 5316 |

同一权威资料可以进入多个领域知识库，因此表中的“领域内文档实例”不是去重后的源文件数量。去重后的获批全文为 12 份。

## 检索验收

- RISC-V DMI/JTAG 调试：命中 `riscv-debug-v1.0.md`。
- 材料设备与 EUV 供应链：命中 `nist-materials-equipment-vision-2023.md`。
- 三维结构、纳米材料与互操作计量缺口：命中 `nist-ir-8577.md`。
- Chiplet、热管理与缺陷检测：命中 `nist-ir-8577.md`。

结果：4/4 通过。机器可读报告见 `reports/source_expansion_retrieval_2026-07-16.json`。

## 下一批缺口

- EDA：需要归档 OpenROAD RTL-to-GDS、PPA、STA、布局布线和 DRC/LVS 官方文档。
- 前道工艺：需要补充刻蚀、沉积、CMP、清洗、SPC/FDC 的开放技术资料和公开数据集。
- 材料设备：需要补充硅片、光刻胶、电子气体、靶材及关键设备子系统资料。
- 封装测试：需要补充 DFT、2.5D/3D、TSV、混合键合、热可靠性和失效分析资料。

OpenROAD 等资料主要以版本化 Markdown 形式发布。下一步应扩展采集器，使其能从固定 Git tag/commit 安全归档 Markdown，而不是只支持 PDF。
