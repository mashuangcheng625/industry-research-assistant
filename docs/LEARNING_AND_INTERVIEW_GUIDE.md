# 关键代码导读、方案权衡与面试深挖

## 1. 先用一句话讲清项目

这是一个通用证据驱动行业研究平台，并以半导体全产业链作为第一个深度垂直落地。
它不只是“把 PDF 放进向量库再调一次大模型”：通用层接入知识库、新闻政策、招投标、
结构化产业数据和公司信号；半导体层治理资料来源和授权，将长文档变成可定位证据，
用混合检索定位证据，约束模型只基于证据回答，将论断绑定到引用，并对资料不足、
运行中断、审核失败和并发退化给出可观测结果。当前深度指标来自半导体文档证据链，
不能直接外推到尚未完成专项评测的多源工具。

“证据驱动”在本项目中至少包含六层：

1. 证据的原始来源、版本、许可和 SHA-256 可查；
2. 切片能回到文档和位置，而不是只保留一段脱离上下文的文本；
3. 回答不得引用不存在的编号；
4. 引用的切片必须覆盖论断中的关键概念，不只是主题相似；
5. 无证据时拒答，不用模型常识偷偷补全型号和参数；
6. 审核未通过的研究草稿不能伪装成完成报告。

## 2. 全链路阅读地图

| 层 | 先读的代码 | 应带着什么问题读 |
| --- | --- | --- |
| 来源治理 | `service/source_governance.py` | 谁允许全文入库？路径、重复和哈希如何处理？ |
| PDF 规范化 | `scripts/renormalize_pdf_sources.py` | 页眉页脚、断词、标题和保留率怎么验证？ |
| 入库 | `scripts/ingest_approved_sources.py` | PostgreSQL 和 Milvus 不是一个事务，中断时怎么发现？ |
| 向量存储 | `service/milvus_service.py` | schema、距离度量、doc/chunk ID 和邻居如何对齐？ |
| 检索 | `service/retrieval_service.py` | 多查询、dense、lexical、精确术语和邻居各解决什么？ |
| 生成 | `service/chat_service.py` | 上下文预算、拒答、引用清洗和模型路由如何组合？ |
| 证据校验 | `service/grounding_service.py` | 引用合法、词法支持和语义蕴含有什么差异？ |
| 评测 | `scripts/evaluate_rag_answers.py` | 检索、质量、引用、拒答和 SLA 是否分开归因？ |
| Agent | `deep_research_v2/state.py` + `graph.py` | 当前阶段与安全恢复游标为什么不能是一个字段？ |
| 可观测 | `core/metrics.py` + `core/health.py` | 指标标签会不会高基数？存活与就绪有何不同？ |
| 运行 | `docker-compose.yml` + `start-services.sh` | 一键启动的成功条件是 sleep 还是真正依赖就绪？ |

## 3. 资料治理和 PDF 解析

### 3.1 输入契约

`SourceCandidate` 不只记录标题和 URL，还包含发布方、领域、文档类型、版本、
权威等级、许可策略、是否开放访问、抓取时间、本地路径和内容哈希。
`review_status=approved` 且存在规范化全文才能入库；`metadata-only` 不能因为“搜到了”
就绕过授权。

稳定 ID 由可审计字段生成，路径会转换成受管根目录下的可移植路径，
`resolve_managed_path` 防止队列文件把入库器引向管理目录之外。

### 3.2 为什么 PDF 解析不等于 `pdftotext`

`renormalize_pdf_sources.py` 使用 `pdftotext -raw` 保留尽可能多的原始页内文本，
再由 `normalize_pdf_text` 处理重复页边缘行、断词、空白和标题。新结果写入
`normalized-v2`，不覆盖旧索引文本，便于先 diff 后重建。

报告至少统计页数、原始/规范化字符数、字符保留率、标题数和剩余换页符。
字符变少本身不是质量提升的证据：需要结合页数、关键段落抽样、标题结构和后续检索
命中率判断是“去噪”还是“丢内容”。

### 3.3 切片的取舍

当前真实长文档默认以 1200 字符切片。它的优点是简单、稳定、可重现；缺点是不等于
token 长度，也不保证每块都是完整语义单元。项目用“标题恢复＋同文档邻居扩展”
缓解跨块断裂，而不是声称字符切片已经解决所有结构问题。

## 4. 可恢复入库与两库一致性

### 4.1 状态转移

`ingest_candidate` 先在 PostgreSQL 提交 `processing`，再解析、Embedding 和写入 Milvus，
成功后把文档改为 `completed` 并写入 `chunk_count`；可恢复异常转为 `failed`。
进程如果硬中断，`processing` 会保留，不会被静默当成完成。

### 4.2 为什么重试前先删旧向量

同一 candidate 重试时，如果上次已写入部分向量，直接 append 会生成重复切片。
代码用稳定文件名生成 `doc_id`，先 `delete_by_doc_id`；删除失败则中止重建，
因为“未更新”比“不知道有多少重复证据”容易恢复。

### 4.3 这仍不是分布式事务

PostgreSQL 和 Milvus 没有共享 ACID 事务。在“向量写入成功”与“数据库标记完成”
之间硬中断，仍可能留下孤儿向量。项目用稳定 ID、可重试删除和
`audit_ingestion_consistency.py` 做最终一致性对账，这是可恢复工程，不是两阶段提交。

更强的生产方案是影子 collection：先完整写新版并对账，再原子切换别名，
避免“删掉旧索引后新建失败”导致服务空窗。

## 5. 混合检索的真实计算路径

### 5.1 确定性多查询

`_build_query_plan` 保留原问，再根据可审计的中英领域词表生成子查询，最多默认
6 路。它不调 LLM，所以不会引入额外成本、改写幻觉和难复现波动。
多个查询一次批量 Embedding，减少 HTTP 往返。

局限是词表覆盖范围：新概念没有词表映射时，多查询不会自动发现同义词。
它适合术语稳定、高审计要求的垂域基线，不一定适合开放域搜索。

### 5.2 dense 候选

每个 query vector 从 Milvus 取候选。混合模式下候选池是 `max(top_k*4, 20)`，
同一 chunk 在多查询中出现时保留最高向量分，并累加 `1/(60+rank)` 的
`rrf_score`。

注意：当前 `rrf_score` 被计算和保留，但没有进入最终 `score` 公式。面试时不能说
“系统使用 RRF 融合完成排序”；准确说法是“已保留 RRF 信号，当前主排序
仍是加权分数”。

### 5.3 lexical 与精确标识符

`_lexical_tokens` 提取英文/数字 token 和中文双字组，无需外部分词服务。
词法分数是查询 token 覆盖率。混合基础分默认为：

```text
base = 0.75 * vector_score + 0.25 * lexical_score
```

对大写缩写、下划线术语等工程词，`exact_term_score` 默认以 0.20 权重重算分数。
对 `QFAB-X99` 这类同时含数字和分隔符的具体型号，使用硬门禁：一个都未精确命中
就不允许该文档进入上下文。这是无证据虚构型号拒答的关键防线。

当前 lexical 路径会最多扫描 10,000 个 chunk 并在应用层计分，对 5,256 块公开基准可行，
但不是大规模 sparse index。语料扩到百万块时应替换为 BM25/Elasticsearch/Milvus sparse vector，
不能只调大 `RAG_LEXICAL_SCAN_LIMIT`。

### 5.4 复合问题的概念覆盖

子查询含 focus terms 时，短语精确覆盖默认可占该子查询相关分的 0.55。
如果一份文档同时覆盖多个子查询，文档级 coverage 默认以 0.12 轻度加权。
`_select_facet_diverse_results` 会先给每个子查询留一个证据席位，再按总分补齐，
避免一个容易概念占满 Top-K。

文档级准入是“该文档有一块达到 dense 或 lexical 阈值”，然后保留它的其他候选块。
这有利于跨段证据链，但也可能带入同文档中分数低的块，因此后续还有单文档块数上限
和总上下文预算。

### 5.5 邻居扩展

seed 命中后，`_expand_with_neighbor_chunks` 只使用同一 `doc_id` 下 `chunk_index±1`
的块，不会跨文档取“位置上相邻”的无关内容。邻居分数从 seed 乘 0.95，
标记 `is_neighbor` 和 `neighbor_of`，可在评测里区分核心命中与连续性补充。

## 6. 上下文、生成、引用与拒答

### 6.1 上下文预算

`rerank_documents` 最终无论重排成功还是异常，都必须经过
`_filter_documents_by_token_limit`。默认检索证据上限是 6,000 token、最多 10 份证据。
单份超大文档会被跳过，后面更小的证据仍可入选。分词器异常时用 UTF-8 字节数
作为保守计数，不因异常放宽预算。

60.04 万 token 合成文档集被截到 3,002/6,000 token，但这只证明“证据预算”。
问题、系统指令、历史、长期记忆和输出尚未共享一个统一总 token 预算，这是真实缺口。

### 6.2 为什么先缓冲完整答案

模型客户端使用 stream，但服务端先将完整答案缓冲到 `model_answer`，清洗越界引用、
可选做结构化校验后再向客户端按 SSE 分块输出。这避免不存在的 `[[99]]`
先发到前端后才发现，代价是用户看不到真正的首 token，当前 SSE 是“校验后分块”
而非“模型实时 token”。

### 6.3 三层引用安全

- `sanitize_citations`：删掉不在 1..N 内的编号，解决引用合法性；
- 评测器的 concept-citation-chunk 对齐：关键概念出现在答案时，它所在句子必须有引用，
  且被引 chunk 要包含对应概念；
- 实验性结构化 grounding：模型输出原子 claim、citation IDs 和原文 quote，
  服务端检查编号、quote 子串、标识符和 lexical support，再由服务端渲染答案。

第一层不能证明引用支持论断；第二层仍是词法近似；第三层尽量缩小模型自由度，
但不是形式化逻辑证明。

### 6.4 为什么严格 grounding 默认关闭

自由文本回归严格质量 16/20；结构化 grounding 同集实验 12/20；
再加本地 4B 二次语义裁判后只有 9/20，P95 22.676 秒，并有 2 例非法 verdict
触发失败关闭。机制能阻止未验证 claim，但小模型的结构遵循和蕴含判断召回不足，
综合质量反而下降，所以作为默认关闭的实验开关保留。

这个决策体现的是“安全机制也必须接受端到端评测”，不是否定严格校验的价值。

## 7. 评测设计与泄漏防护

### 7.1 数据集分层

- regression 20：固定回归，防止已修能力倒退；
- development 20：用于消融和阈值开发；
- test 20 与 hidden 20：公开仓库只保留问题，答案键位于 Git 忽略的私有目录。

40 条有标签集和 40 条只问题集均在四个领域、五种题型上平衡。验证脚本会拒绝
问题集出现答案字段。

历史 test/hidden 标签曾经暴露给开发者，因此已有 15/20 和 18/20 只能作为阶段验收，
不是真正盲测。大改后要由独立复核者在代码冻结后生成 blind-v2。

### 7.2 为什么不只看一个 pass rate

`evaluate_case` 分开记录：

- API/SSE 是否成功；
- 延迟是否达 SLA；
- 金标来源是否被召回；
- 答案术语组是否覆盖；
- 引用编号是否合法；
- 金标来源是否被实际引用；
- 每个概念的答案句、引用和被引 chunk 是否对齐；
- 无证据题是否正确拒答。

这使“检索到了但模型没用”、“答案有术语但引用不支持”和“答案正确但超时”
能够分开归因。

### 7.3 消融证明什么

development 集上，单查询 dense 为 3/20，多查询 dense 为 7/20，混合多查询为 20/20，
MRR 0.7083、nDCG@3 0.7185、P95 2.789 秒。它证明在这个公开基准上精确术语和
复合概念覆盖带来显著收益，但不能外推成“任何半导体问题都 100% 召回”。

## 8. 研究 Agent 状态机

### 8.1 实际运行的不是 LangGraph 图

`DeepResearchGraph` 会构建 LangGraph 图，但 `run()` 中的线上 SSE 路径明确固定调用
`_run_simplified`。原因是现有 LangGraph `astream` 整合在该项目中会批量处理消息，
无法提供现有 UI 需要的实时队列消息。

所以面试准确说法是：“状态 schema 和备选图与 LangGraph 兼容，当前生产演示路径是
手写 asyncio 状态机，因为需要精确控制 SSE、取消、超时和 checkpoint 时机。”

### 8.2 `phase` 与 `last_completed_phase`

`phase` 表示当前正在执行什么；`last_completed_phase` 表示最近完整结束的原子阶段。
如果 DeepScout 执行到一半取消，checkpoint 中可以是：

```text
phase = researching
last_completed_phase = planning
```

恢复时跳过 planning，但必须从头重跑 Scout。如果只保存一个 `phase=researching` 并把它当成
“研究已完成”，就会将半成品当成后续分析的完整输入。

### 8.3 取消、超时和并发锁

Agent 任务由 `asyncio.create_task` 启动，主循环每最多 0.5 秒轮询消息队列和 Redis 取消标志。
取消或超时时先 `task.cancel()` 并 `await task`，避免背景 LLM 任务成为泄漏的孤儿任务。
同一 session 的运行锁已占用时返回 409；Redis 不可用时失败关闭为 503，而不是放任
两个状态机覆盖同一 checkpoint。

### 8.4 审核为什么有确定性否决

Critic 的文本结论也是 LLM 输出，可能在列出 critical 问题后又说 pass。
状态机将 `review_status`、`critical_issues`、`major_issues`、`unresolved_issues` 和
`completion_reason` 显式化，只有 `phase=completed` 且 `review_status=approved` 才能发出
`research_complete`。迭代耗尽但问题未解决时进入 `review_failed`。

真实本地运行中，模型原始 verdict 说 pass，但规则得到 1 critical、2 major、3 unresolved、
质量分 4.0，最终正确进入 `research_review_failed`。这比只演示一份看起来漂亮的报告
更能说明 Agent 系统的安全边界。

## 9. 并发、SSE 和可观测

### 9.1 事件循环阻塞案例

FastAPI 路由是 `async def` 不代表内部同步 SDK 自动变成非阻塞。原路由在 async generator 中
执行同步 Embedding、Milvus、重排和 OpenAI-compatible 流，占住 Uvicorn 事件循环。
修复为同步 generator 后，Starlette 用线程池迭代，单个 RAG 请求中的健康检查从
2.753 秒降到 0.081 秒。

这只解决服务线程调度，不会让单个 4B 模型无限并发。受控压测中，并发 4 吞吐
0.412 req/s、P95 10.217 秒；并发 8 吞吐只到 0.417 req/s，P95 升到 19.919 秒。
所以本地建议并发上限是 4。

### 9.2 指标不使用 session/query 作标签

Prometheus 记录 run/phase/agent/LLM/checkpoint/lock/cancel 的次数和延迟，标签只使用受控枚举。
如果把 session ID、query 或完整异常文本当 label，时序数会随请求无限增长，最终反过来
压垮监控系统。详细调试信息应放日志/trace，不是 metrics label。

### 9.3 liveness 与 readiness

- `/health/live`：只证明进程的事件循环能响应；
- `/health/ready`：并行检查 PostgreSQL、Redis 和 Milvus；完整 app profile 还检查生成模型
  和 Embedding 模型是否由 OpenAI-compatible `/models` 公布。

Ollama 常将无标签 `bge-m3` 公布为 `bge-m3:latest`，readiness 仅允许这一种规范化，
不用模糊子串匹配，避免配错相似模型也显示就绪。

## 10. 方案权衡速查表

| 决策 | 当前选择 | 优点 | 代价/何时换方案 |
| --- | --- | --- | --- |
| query expansion | 领域词表确定性改写 | 可审计、快、无额外 LLM | 词表覆盖有限；开放域可加受约束 LLM 改写 |
| lexical | 应用层 token 覆盖 | 简单可复现 | 百万块改 BM25/sparse index |
| fusion | 加权 dense + lexical + exact | 分数直观 | 需跨 query 归一化；可对比真正 RRF/学习排序 |
| rerank | 本地无 reranker 时保留混合分 | 纯本地、少依赖 | 质量上限受限；可接本地 cross-encoder |
| chunk | 1200 字符 + 邻居 | 稳定和容易对账 | 表格/长章节可用结构化分块 |
| citation output | 完整缓冲后清洗 | 不泄露越界引用 | 失去真 TTFT；可设计可回滚的句级校验流 |
| grounding | 自由文本默认，严格模式实验 | 基线质量更高 | 风险场景要换更强 verifier 并重评估 |
| Agent engine | 手写 asyncio 状态机 | SSE/取消/checkpoint 可精确控制 | 节点多后维护成本高；可重做 LangGraph 流式集成 |
| schema | 开发 `create_all` | 启动简单 | 生产必须建 Alembic 版本链、备份和回滚 |
| deploy | 本地 Compose profile | 作品集可复现 | 不是 HA/TLS/滚动发布 |

## 11. 真实失败案例手册

### 案例 1：向量召回看似高级，基线只有 3/20

根因：复合问题被单一 embedding 稀释，工程标识符和中英术语的精确覆盖不足。
修复：确定性多查询、lexical、exact identifier、facet diversity 和文档覆盖。
证据：development 消融 3/20 -> 7/20 -> 20/20。

### 案例 2：引用编号没越界，却不支持论断

根因：“引用合法”与“证据支持”被当成同一个指标。
修复：逐概念检查答案句、引用号和被引 chunk。
证据：历史宽松 20/20 在严格规则下变为 16/20。

### 案例 3：更严格的 verifier 让结果更差

根因：4B 模型不稳定遵循 JSON verdict，对跨语言蕴含偏保守；失败关闭降低了召回。
决策：保留实验开关但默认关闭，不用“机制更先进”代替端到端评测。

### 案例 4：Agent 迭代次数耗尽后被标成完成

根因：循环退出与质量审批被混在一个 terminal phase。
修复：显式 `review_status`、严重问题计数和 `completion_reason`，未批准则 `review_failed`。

### 案例 5：取消后“恢复”跳过了半完成 Scout

根因：将当前 `phase` 误当成已完成游标。
修复：增加 `last_completed_phase`，实测取消点保存 researching/planning，恢复时重跑 Scout。

### 案例 6：并发 2 几乎没有吞吐增益

根因：async generator 内部运行同步 RAG 链路，堵住事件循环。
修复：改为同步 iterable，由 StreamingResponse 线程池迭代。
限制：并发 8 时模型仍饱和，线程池不是推理加速器。

### 案例 7：并发 8 “质量降到 50%”是错误实验

根因：并发 8 误换了一道原本就不通过引用支持的题，与前四档输入不同。
处理：保留错误报告作为反例，用原两题重跑，受控结果为 16/16。

### 案例 8：重排异常路径绕过 token 预算

根因：`except` 直接返回排序前 10 份文档。
修复：将上下文过滤抽成所有路径必经的确定性函数，并增加异常测试。

### 案例 9：容器已运行，Embedding 却不可用

根因：readiness 只检查三个存储；加模型检查后又发现 Ollama 公布
`bge-m3:latest` 而配置是 `bge-m3`。
修复：app profile 开启模型 readiness，仅规范化可省略的 `:latest`。

### 案例 10：Compose 配置正确，镜像却构建不了

根因：历史 Dockerfile 位于 `backend/app/`，新 build context 默认在 `backend/` 查找。
修复：移到上下文根，真实构建并做一次性容器 smoke。
教训：`docker compose config` 通过不代表 Dockerfile 和依赖能构建。

### 案例 11：旧 Milvus 实体数和可查数不一致

只读审计发现设计库一份文档有 138 个重复 `(doc_id, chunk_index)`，并存在实体统计
比可查结果多 1。决策是保留旧卷作审计证据，不在新 Milvus 2.6 服务上直接打开
2.3 数据，而是从受审 Markdown 重建隔离卷。

## 12. 面试深挖问答

### Q1：为什么不只用向量检索？

垂域问题包含大量型号、缩写、变量名和多概念并列。Embedding 适合语义近似，但会稀释
精确字符串和复合问题的小众概念。本项目的消融也支持这一点：单 dense 3/20，
加多查询 7/20，加 lexical/exact/facet 后 20/20。

### Q2：0.75/0.25 权重是“最优”吗？

不是全局最优声明，而是在 development 基准上冻结的工程配置。要证明更优，需在不看 test
答案的情况下做网格/贝叶斯搜索、分领域稳定性分析，最后用新 blind-v2 验收。

### Q3：为什么不直接用 LLM 做 query rewrite？

基线优先需要可复现和可审计。词表改写没有额外请求、不会改写出不存在的术语。
当语料和问题开放度增大时，可将 LLM rewrite 作为候选召回通道，但要保留原问、记录改写、
限制数量并通过消融证明增益。

### Q4：邻居块会不会引入无关内容？

会有这个风险，所以实现上使用 `(doc_id, chunk_index)` 定位、默认窗口 1、限制最大邻居数，
并在总上下文预算中二次筛选。它解决跨块语义断裂，不是无条件把整章都放入模型。

### Q5：为什么不只看 Recall@K？

Recall@K 只说金标证据是否在候选中。用户还关心排名、答案是否使用它、引用是否支持
具体论断、无证据时是否拒答、以及时延。因此同时报 Recall/MRR/nDCG、金标引用、
concept support、refusal 和 latency。

### Q6：引用合法与 faithful 有什么差别？

`[[2]]` 在两个证据中存在，只能证明合法。如果第 2 块说“UCIe 是互连标准”，回答却说
“它保证零故障”，引用仍不 faithful。需将原子论断与被引证据做支持判定。

### Q7：为什么 lexical support 不等于 entailment？

证据可能包含同样的主体、数字和术语，但否定关系、比较方向、因果方向或适用范围相反。
lexical 是高召回的确定性近似检查，语义蕴含需要更强 NLI/verifier 或人工复核。

### Q8：为什么无证据拒答要用确定性文本？

用户明确要求搜索但没有任何证据时，再调模型会让它用参数知识填充空白。
确定性拒答可保证这个边界不受温度和模型版本影响。

### Q9：为什么要区分 current phase 和 completed cursor？

取消可能发生在任意 `await`。当前阶段只说正在哪里，不能证明该阶段的输出完整。
恢复必须从最近完整的原子阶段之后重跑，否则会消费半成品状态。

### Q10：为什么 Redis 不可用时不直接运行？

同 session 锁和取消标记是正确性控制面，不是可有可无的性能缓存。Redis 不可用时放行会让两个
状态机覆盖 checkpoint，所以应返回 503 失败关闭。

### Q11：为什么 Critic 也不能被盲信？

Critic 仍是概率模型，会生成自相矛盾的问题列表和结论。应将严重问题计数、未解决数和
审批状态结构化，用确定性规则决定是否能进入 completed。

### Q12：为什么后端 async 仍会阻塞？

`async def` 只在内部操作真正 `await` 非阻塞 I/O 时让出事件循环。同步 OpenAI SDK、Milvus 和
CPU 重排在 async generator 中仍会整段占用循环。要么换 async client，要么显式进线程池。

### Q13：为什么并发 8 吞吐不再增长？

服务器调度已不阻塞，但所有请求仍竞争同一个本地模型实例。当推理计算成为瓶颈，
新请求只是排队：吞吐持平，延迟近似成倍上升。

### Q14：当前的长上下文保障完整吗？

不完整。已保证检索证据在任何重排路径都不超 6,000 token，并拒绝超过 8,000 字符的问题。
但总 prompt 还包括系统规则、历史和记忆，应改为统一动态预算并保留输出空间。

### Q15：如何证明入库没有静默丢数据？

对比来源队列、PostgreSQL 文档状态/chunk_count、Milvus 可查实体、稳定 doc/chunk ID 和重复键。
对旧库的审计必须只读，失败报告不能为了“绿”而修数据。

### Q16：为什么不可以说“准确率 100%”？

20/20 是特定 development 检索门槛，不是真实问题分布的答案准确率。公开语料小，test/hidden 历史受污染，
且端到端严格质量只是 16/20。可以报“在冻结基准和指定门槛下的通过数”，不能外推。

### Q17：为什么不把旧 Milvus 卷直接升级打开？

跨大版本直接复用存储不能保证内部元数据兼容，旧库本身又已有重复和计数不一致。
保留旧卷作审计样本，在新 2.6 隔离卷中从受审文本重建，更容易证明结果正确。

### Q18：为什么容器 healthy 不能只看进程在跑？

进程可以在 PostgreSQL 密码错、Milvus 不可达或 Ollama 没有 Embedding 模型时仍然返回 liveness。
只有就绪检查包含必要依赖并失败关闭，调度器才不会把不能服务的实例放进流量。

### Q19：这个项目距离生产还缺什么？

至少包括：真正 blind-v2 与专家标注、统一总 prompt 预算、大规模 sparse index、
更强 grounding verifier、Alembic 迁移、备份恢复、TLS/密钥托管、多副本、分布式 trace、
多 worker metrics 聚合、持续 soak test 和公开授权确认。

### Q20：你在这个项目中最能体现工程能力的部分是什么？

不是某个 prompt，而是把一个“能聊天的 demo”变成可审计闭环：不同层的指标分开归因，
失败路径不冒充成功，严格机制也必须接受实验，并且每个简历数字都能对应命令和报告。

## 13. 四周深入学习与动手验收

### 第 1 周：数据和检索

- 手画一份 PDF 从 registry 到 citation 的 ID 传播图；
- 独立实现简化中文双字组 lexical score；
- 从报告重建 dense/multi-query/hybrid 消融表；
- 为一道失败题手算 vector/lexical/exact/document coverage 各信号的影响；
- 解释 RRF 信号为何尚未参与最终分数。

验收：不看代码，在白板上写出从 query plan 到 neighbor expansion 的完整步骤和主要默认参数。

### 第 2 周：生成、grounding 和评测

- 构造一个“引用合法但不支持”的反例；
- 给一个 claim 分别用 lexical、quote substring 和 NLI 判定，比较误报/漏报；
- 手动分解一条 `quality_passed=False` 报告；
- 说明为什么结构化模式 12/20 不应默认上线；
- 设计 blind-v2 的冻结、评测和解盲流程。

验收：能在 10 分钟内区分 retrieval failure、generation omission、citation mismatch、
unsupported claim 和 SLA failure。

### 第 3 周：Agent 和可靠性

- 手画 planning -> researching -> analyzing -> writing -> reviewing -> revise/re-research 状态机；
- 对“Scout 中途取消”写出 checkpoint 前后状态；
- 解释为什么运行锁失败要 503；
- 注入 Agent timeout、checkpoint save failure 和 Critic 自相矛盾；
- 从 Prometheus 指标恢复一次运行的耗时和结果。

验收：能说明手写状态机与现有 LangGraph 备选路径的真实差异，不把库依赖写成线上能力。

### 第 4 周：服务工程和演示

- 复现事件循环阻塞与线程池修复原理；
- 画出并发 1/2/4/8 的吞吐与 P95 曲线；
- 解释 liveness/storage readiness/model readiness；
- 在干净镜像中运行三题 demo 并打开证据切片；
- 以失败案例结尾，讲清尚未完成的生产缺口。

验收：做一次 15 分钟演示，每个数字都能现场指向 JSON 报告或复现命令。

## 14. 数字速查：可以说什么，不能说什么

| 可核验事实 | 安全表述 | 不安全外推 |
| --- | --- | --- |
| 17 candidates / 15 approved / 2 metadata-only | 来源队列有审批和授权门禁 | “数据完全覆盖半导体全产业链” |
| 12 PDF / 1327 页 | 公开基准文档规模 | “海量企业级知识库” |
| 5256 chunks / 4 collections | 全语料 Lite smoke 对账通过 | “生产 Milvus 集群验证通过” |
| development hybrid 20/20 | 冻结开发基准上严格通过 | “检索准确率 100%” |
| regression answer 16/20 | 严格概念-引用-切片门槛通过 16 题 | “问答准确率 80%” |
| refusal 4/4 | 四道冻结无证据题全部拒答 | “对任意幻觉都能 100% 拦截” |
| 并发 4 P95 10.217s | 本机、本地 4B、两题闭环压测结果 | “生产 SLA 为 10 秒” |
| 154 tests | 本地工程门禁 153 unit + 1 Milvus Lite integration 通过 | “系统没有 bug” |
| 干净镜像 smoke | Python 3.12/Node 22 容器可构建并就绪 | “已完成生产部署” |
