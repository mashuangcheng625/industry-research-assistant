# Embedding 路由与双路检索设计

## 目标

系统同时保留百炼 `text-embedding-v4` 与本地 `bge-m3`，但不在同一向量空间中混用两者。
默认使用云端索引，本地索引用于离线与隐私场景，混合模式用于可评测的双路召回。

## 实施状态

- 已实现三种路由、模型指纹与独立 Collection 命名。
- 已实现同切片双索引入库、RRF 去重融合与 `qwen3-rerank` 精排。
- 已实现单路故障降级和 `degraded_route` 状态。
- 当前默认查询模式仍为 `cloud`，入库模式为 `hybrid`。
- 新双索引尚未用真实语料重建，旧 Collection 尚未删除。

## 路由模式

```env
EMBEDDING_ROUTING_MODE=cloud
# cloud / local / hybrid
```

| 模式 | Embedding | 检索行为 | 用途 |
| --- | --- | --- | --- |
| `cloud` | `text-embedding-v4` | 只查云端向量索引 | 默认线上路径 |
| `local` | `bge-m3` | 只查本地向量索引 | 离线演示、隐私数据 |
| `hybrid` | 两者 | 双路召回、RRF 融合、百炼重排 | 高召回率实验 |

Embedding 路由不做静默自动切换。模型与 Collection 必须一起切换，否则查询向量与入库向量
不在同一向量空间，检索结果不可信。

## Collection 契约

每个业务知识库对应两个独立 Collection：

```text
kb_{knowledge_base}_text_v4_1024_v1
kb_{knowledge_base}_bge_m3_1024_v1
```

两个 Collection 共用相同的切片规则、`document_id` 和 `chunk_id`，以便融合时去重。每条记录增加：

- `embedding_provider`：`bailian` 或 `ollama`；
- `embedding_model`：精确模型 ID；
- `embedding_dimensions`：固定为 `1024`；
- `embedding_version`：当前为 `v1`；
- `content_hash`：用于判断双索引切片是否一致。

旧的无后缀 Collection 只读保留，在新索引完成校验前不删除。

## 入库流程

1. 文档解析和切片只执行一次。
2. 为每个切片生成稳定 `chunk_id` 和 `content_hash`。
3. 使用 `text-embedding-v4` 批量生成云端向量。
4. 使用 `bge-m3` 批量生成本地向量。
5. 分别写入对应 Collection，任一路失败不污染另一路。
6. 记录每路的成功数、失败数、模型版本和耗时。

## 混合检索

`hybrid` 模式的固定流程：

1. 两路各召回 Top 20。
2. 以 `chunk_id` 去重。
3. 使用 Reciprocal Rank Fusion（RRF）融合排名，默认 `k=60`。
4. 取融合后 Top 20 调用 `qwen3-rerank`。
5. 根据上下文 Token 预算保留最终 Top 5–10。

```text
RRF(d) = Σ 1 / (60 + rank_i(d))
```

不直接加权求和两种 Embedding 的原始相似度，因为两者分数分布不可比。

## 失败与降级

- `cloud`：云端 Embedding 不可用时明确报错，不静默查本地 Collection。
- `local`：本地 Ollama 不可用时明确报错，不将数据发往云端。
- `hybrid`：允许单路降级，但响应和指标中必须显示 `degraded_route`。
- Rerank 失败：使用 RRF 排名，不丢弃已召回证据。
- 索引模型指纹与当前配置不匹配：拒绝检索并提示重建索引。

## 可观测性

每次检索记录：

- requested/resolved route；
- 每路召回数、耗时和异常类型；
- 去重前后候选数；
- Rerank 耗时与 Token 用量；
- 最终证据的来源路由；
- 是否发生降级。

健康接口只暴露模型 ID、路由和可用性，不暴露 Key 或内部请求地址。

## 评测门槛

在将 `hybrid` 设为默认前，使用同一份固定评测集对比 `cloud` / `local` / `hybrid`：

- Recall@5、Recall@10、MRR@10、nDCG@10；
- 严格标识符命中率；
- 有证据回答率和引用正确率；
- P50/P95 延迟；
- 单次查询云端 Token 与费用；
- 单路故障时的降级成功率。

`hybrid` 只在检索质量显著提升且 P95 延迟增幅可接受时才能升为默认；否则继续以 `cloud`
为默认，`hybrid` 作为可选研究模式。

## 实施顺序

1. 引入模型指纹与 Collection 命名器。
2. 拆分云端/本地 Embedding Provider。
3. 改造入库流程生成双索引。
4. 实现路由选择、RRF 和单路降级。
5. 接入 `qwen3-rerank`。
6. 增加评测、指标和状态展示。
7. 新索引验收后，再单独确认是否删除旧 Collection。
