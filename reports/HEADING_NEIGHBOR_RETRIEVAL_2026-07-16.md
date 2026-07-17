# 标题感知切片与相邻上下文检索验证

日期：2026-07-16

## 问题

OpenROAD Markdown 首次入库时按固定字符数切片。RTL-to-GDSII 流程问题在
Top-5 中命中了前半部分，但 routing 证据位于相邻切片，严格评测只有
2/3 通过。这是切片边界导致的上下文丢失，不是语料缺失。

## 实现

1. Markdown 按标题层级切分，每个切片都携带“文档位置：父标题 > 子标题”。
2. 对 Top-K 主召回扩展同一 `doc_id` 内的前后切片，默认最多补充 4 个；
   严禁跨文档拼接。
3. 对 `PLACE_DENSITY`、`CORE_UTILIZATION` 等大写缩写或下划线变量增加
   精确术语得分，解决语义相似但变量名不匹配的排序问题。
4. 强制重建时先按稳定 `doc_id` 删除旧切片，避免重复向量；可按
   `--candidate-ids` 只重建指定资料。

## 重建结果

| OpenROAD 文档 | 旧切片 | 标题感知切片 |
| --- | ---: | ---: |
| Flow Configuration Variables | 60 | 74 |
| Flow Scripts Overview | 8 | 15 |
| RTL-to-GDSII Tutorial | 64 | 102 |
| 合计 | 132 | 191 |

重建后数据库与 Milvus 统计一致：

| 知识库 | 文档 | 切片 |
| --- | ---: | ---: |
| 芯片设计与 EDA/IP | 12 | 3431 |
| 半导体材料与设备 | 8 | 656 |
| 晶圆制造与前道工艺 | 8 | 718 |
| 封装与测试 | 8 | 702 |
| 合计 | 36 | 5507 |

## 评测结果

- OpenROAD EDA 专项：3/3 通过，主召回 `top_k=5`。
- 半导体四方向回归：4/4 通过，主召回 `top_k=4`。
- 后端单元测试：20/20 通过。
- 相邻扩展后返回数可高于 `top_k`；主召回数仍然是 Top-K，多出的是有
  `chunk_index` 约束的同文档上下文。

机器可读结果：

- `reports/openroad_retrieval_heading_neighbor_2026-07-16.json`
- `reports/source_expansion_retrieval_after_heading_neighbor_2026-07-16.json`

## 结论

这一步将“找到相似段落”升级为“找到有标题位置和局部上下文的证据”。
当前题集仅用于工程回归，不代表整个半导体知识库的统计质量；下一步应
扩展为包含正例、负例和跨文档问题的 20 题以上评测集。
