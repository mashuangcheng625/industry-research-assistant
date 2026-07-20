# 检索消融实验与设计结论

日期：2026-07-17

## 实验边界

- 仅使用可见的 development 和 regression 标签，不读取 test/hidden 答案；
- Top-K 为 3，每个场景在独立进程运行，避免环境开关串组；
- 运行时使用旧 Milvus 2.3 索引。其设计库有已知历史重复块，所以结果必须在
  2.6 全量重建后复现，才能成为新基线；
- “hybrid”指 dense、词法、分面词和文档覆盖度的确定性加权融合，当前没有
  cross-encoder 或 LLM reranker，不得把融合排序说成模型重排。

复现命令：

```bash
make ablate-retrieval-development
```

## Development 结果

| 场景 | 严格通过 | MRR | nDCG@3 | 平均术语组覆盖 | P50 | P95 | 首题/最大 | 邻接块 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 单查询 dense | 3/20 | 0.5938 | 0.5541 | 52.60% | 460.6ms | 535.3ms | 896.1ms | 0 |
| 多查询 dense | 7/20 | 0.6146 | 0.6039 | 73.33% | 525.2ms | 703.0ms | 1287.7ms | 0 |
| 混合 + 多查询 | 20/20 | 0.7083 | 0.7185 | 100% | 1072.5ms | 2788.6ms | 3817.5ms | 0 |
| 混合 + 多查询 + 邻接 | 20/20 | 0.7083 | 0.7185 | 100% | 1136.4ms | 3251.0ms | 4035.2ms | 9 |

关键观察：

1. dense 检索对正例都会返回结果，但金标来源、专业术语覆盖和无证据拒答很差；
   “有结果”不等于“召回了可用证据”。
2. 多查询把平均术语组覆盖从 52.60% 提到 73.33%，但单独使用时 4 道无证据题
   全部误召回；扩写提高 recall 的同时会放大假阳性。
3. 混合融合是 development 上的主要增益：严格通过 +13，MRR +0.0938，
   nDCG@3 +0.1147，但 P95 增加约 2.09s。
4. development 上邻接扩展额外带回 9 块，却没有质量增益；不能只凭理论声称有效。
5. 混合首题比预热 P50 慢约 3 倍，主要是首次全库词法快照与缓存构建；
   因此要分开报告冷启动、P50、P95 和最大值。

## Regression 邻接复核

| 场景 | 严格通过 | MRR | nDCG@3 | P95 | 邻接块 |
| --- | ---: | ---: | ---: | ---: | ---: |
| 混合 + 多查询 | 19/20 | 0.7812 | 0.8385 | 2757.7ms | 0 |
| 混合 + 多查询 + 邻接 | 20/20 | 0.7812 | 0.8385 | 2902.3ms | 21 |

邻接扩展没有改变金标文档排名，但为 `process-digital-twin-013` 补齐了相邻段中的
`control or optimization`。因此它解决的是“已找对文档后的跨段证据完整性”，
不是“金标文档召回排名”。这个区别是解释 MRR/nDCG 不变但严格通过提升的关键。

## 当时的下一步

- 将全库 Python 词法扫描替换为可扩展 sparse/BM25 候选召回，降低冷启动和 P95；
- 在 development 上单独引入 cross-encoder reranker 场景，比较排名收益、延迟与成本；
- 在 Milvus 2.6 新库复现 regression/development，然后由独立评测者运行经过来源预校验的新 blind-v3。

## 2026-07-20 双路 Hybrid 复现

旧索引限制已经消除。本轮在 Milvus 2.6.17 上使用 36 个已审核文档任务，按 1,200
字符切成 5,256 块，并分别写入百炼 `text-embedding-v4` 与本地 Ollama `bge-m3`
两个 1,024 维索引；四个知识库共 8 个集合。PostgreSQL 与两个向量路由逐文档对账
全部通过，无重复 chunk id、重复文档位置、非法文档 id 或数量差异。

运行链路为：双路向量召回 → 各路 dense/词法/分面融合 → RRF 去重 → 百炼
`qwen3-rerank` → 分面多样性选择。最后一步保留复合问题各子问题的证据席位，避免
cross-encoder 只留下语义相似但证据维度重复的段落。

| 数据集 | 严格通过 | 正例召回 | 负例拒绝 | 金标 Recall@5 | MRR | nDCG@5 | P95 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| development | 20/20 | 16/16 | 4/4 | 16/16 | 0.6615 | 0.7119 | 6489.4ms |
| regression | 20/20 | 16/16 | 4/4 | 16/16 | 0.8021 | 0.8534 | 5478.5ms |

相较于只按 rerank 分数截断，development 从 17/20 提升到 20/20，金标 Recall@5
从 15/16 提升到 16/16；MRR 从 0.8646 降到 0.6615。这是有意选择“复合问题证据
覆盖优先于第一条排名”，不应只展示通过率而隐藏排名代价。冻结 regression 同样从
19/20 提升到 20/20，未出现质量回退。

本轮机器可读证据：

- 双路入库：[canary](../reports/hybrid_ingestion_canary_2026-07-20.json)、
  [全量执行](../reports/hybrid_ingestion_full_2026-07-20.json)、
  [只读一致性审计](../reports/hybrid_ingestion_audit_2026-07-20.json)；
- development：[融合前](../reports/hybrid_retrieval_development_2026-07-20.json)、
  [分面融合后](../reports/hybrid_retrieval_development_facet_fusion_2026-07-20.json)；
- regression：[融合前](../reports/hybrid_retrieval_regression_2026-07-20.json)、
  [分面融合后](../reports/hybrid_retrieval_regression_facet_fusion_2026-07-20.json)；
- 独立真实来源探针：[4/4 结果](../reports/hybrid_real_source_retrieval_2026-07-20.json)。

当前下一步是将全库 Python 词法扫描替换为可扩展 sparse/BM25 候选召回，并对
Hybrid 的 P95 和冷启动延迟做专项优化。blind-v2 已解盲且存在金标映射缺陷，不再用于
调参；下一次泛化结论必须来自来源预校验并在代码冻结后首次运行的 blind-v3。
