# 给后续模型的项目交接说明

## 1. 任务目标

继续完善“证据驱动行业研究平台”，采用以下正式定位：

> 通用研究平台负责专业知识库、新闻政策、招投标、产业数据库、Text2SQL、公司行情和
> Research Agent；半导体全产业链是第一个完成来源治理、检索、引用、评测、可靠性和部署
> 深度闭环的垂直领域。

不要把项目退化成 PDF 聊天机器人，也不要把已接入但未专项验证的多源能力包装成完成态。

## 2. 开始前必须阅读

按顺序阅读：

1. `README.md`
2. `docs/MULTI_SOURCE_RESEARCH_PLATFORM.md`
3. `docs/PROJECT_CLOSURE_ROADMAP.md`
4. `docs/LEARNING_AND_INTERVIEW_GUIDE.md`
5. `docs/RAG_EVALUATION_PROTOCOL.md`
6. `docs/AGENT_RELIABILITY.md`
7. `docs/PERFORMANCE_AND_LOAD_TESTING.md`

然后运行：

```bash
git status -sb
git log --oneline -5
make check
make validate-observability
```

先确认现有进程、容器和工作区状态，不要盲目清理数据卷、杀死已有后端或覆盖用户修改。

## 3. 已验证事实

以下数字可以引用，但不能外推：

- 来源注册表：17 个候选，15 个 approved，2 个 metadata-only；
- 真实规范化语料：12 份 PDF、1,327 页、5,256 个块、4 个半导体集合；
- development 消融：dense single 3/20、dense multi 7/20、hybrid multi 20/20；
- regression 混合检索 + 邻居：20/20；
- regression 端到端：严格质量 16/20，SLA 20/20，拒答 4/4，P95 12.477 秒；
- 并发 4：8/8、P95 10.217 秒；并发 8：16/16、P95 19.919 秒；
- 上下文压力：600,400 输入 token，证据预算内选取 3,002/6,000；
- 后端测试：469 项（459 unit + 10 integration，含 Redis 持久任务故障恢复）；前端 lint/build 通过；Prometheus 7 条规则有效；
- Agent 真实运行：取消和精确恢复已验证；另一次完整审核因 1 critical、2 major 正确进入
  `research_review_failed`，没有被错误放行。

这些结果来自固定本地数据与本地 4B 模型，不等于开放业务准确率，也不等于生产容量。

## 4. 重要实现边界

- `rrf_score` 存在，但当前最终排序不是 RRF；
- 当前在线 SSE 使用显式编排逻辑，不是 LangGraph 图执行；
- 语义裁判默认关闭，本地 4B 实验仅 9/20，且出现非法 verdict 后失败关闭；
- 主聊天与 Research Agent 已接入默认 32K 总预算，统一计算指令、问题、历史、记忆、证据和
  输出预留；6,000-token 继续作为证据子预算。Memory 摘要、Text2SQL、语义裁判和旧
  ReAct/DR-G 兼容链路也已覆盖；
- 词法召回仍会扫描候选文本，不适合大规模生产索引；
- `/metrics` 已支持 multiprocess 聚合并提供 Grafana 看板；OpenTelemetry 为 opt-in；数据库已有覆盖 14 张表的
  Alembic 两段迁移链，CI 已配置隔离库往返迁移与 ORM schema drift 门禁；
- 新闻、招投标、Text2SQL、股票有真实代码与入口，但缺少和 RAG 同等级的专项评测；
- blind-v2 已首次运行，但因知识库映射和金标来源缺陷转为已解盲诊断集；
  下一次泛化结论必须使用经过来源预校验、由独立维护者制作的 blind-v3；
- 原始 PDF、私有 80 题答案、本地 `.env`、数据库和依赖目录都必须保持 Git 忽略；
- GitHub 仓库已公开（MIT License），公开前的 5 项人工确认已于 2026-07-18 全部清零。

## 5. 当前代码地图

| 目标 | 入口 |
| --- | --- |
| FastAPI 与健康检查 | `backend/app/app_main.py`、`backend/app/core/health.py` |
| RAG 在线请求 | `backend/app/router/chat_router.py` |
| 检索与上下文 | `backend/app/service/retrieval_service.py` |
| 引用与 grounding | `backend/app/service/grounding_service.py` |
| Agent 状态机 | `backend/app/service/deep_research_v2/graph.py`、`state.py`、`service.py` |
| 新闻与招投标 | `news_collection_service.py`、`news_router.py` |
| 结构化数据 | `database_explorer.py`、`text2sql_service.py`、`database_router.py` |
| 股票接入 | `stock_service.py`、`deep_research_v2/agents/scout.py` |
| 行业配置 | `backend/app/config/industry_config.py`、`frontend/src/store/industry.ts` |
| 评测脚本 | `backend/app/scripts/evaluate_*`、`run_retrieval_ablation.py` |
| 事实报告 | `reports/` |

## 6. 推荐的下一项主任务

上一版推荐的多源黄金路径 A/B/C 已完成：统一 Evidence 契约、冻结 fixture 和 12 题门禁均已入库。
Redis 限流也已改为单次 Lua 原子执行，并在 Redis 故障时降级到保留本进程历史的本地窗口。
不要重复实现。`CitationLocator` 的生产链路接入也已完成：Evidence、Chat、Research Writer/API
和前端来源卡片都保留旧字段并新增统一定位对象，联合评测器会校验 anchor 与 source kind。
10 条模型调用路径、40 组同规模预算边界矩阵也已通过。下一项主任务是制作经过来源预校验的
blind-v3，或推进可扩展词法索引与连续数据库迁移验收。

### 已完成的上一黄金路径（历史记录）

原目标是：

> “结合权威技术资料、近期政策、设备招投标和上市公司数据，分析先进封装设备国产化机会、
> 受益环节与风险。”

分三步：

### A. 统一多源证据契约

定义 `Evidence` 数据结构，至少包含 `evidence_id`、`source_kind`、`publisher`、`url`、
`published_at`、`retrieved_at`、`as_of`、`locator`、`content`、`content_hash`、`quality_tier` 和
`license_or_terms`。为 PDF、新闻、招投标、SQL 行和行情分别写适配器与契约测试。

验收：Writer 与前端不需要按工具类型读取不同的来源字段；每条证据都能定位、复核并判断时效。

### B. 建立可重复的多源 fixture

不要让 CI 调真实收费 API。保存一个经过授权、脱敏、带固定时间点的小型数据快照，并对外部
provider 使用 mock/contract test。所有实时调用必须有超时、失败降级和来源时间字段。

验收：无外部 Key 的 CI 可以完整执行联合研究 smoke；某个 provider 失败时报告明确降级，
不会编造对应来源结论。

### C. 建立 12 题专项评测

按 `MULTI_SOURCE_RESEARCH_PLATFORM.md` 的分布设计 12 题，逐题人工核验工具选择、来源类型、
数字口径、引用定位、推断标识、冲突披露和拒答。

验收：报告包含逐题结果和失败原因；评测脚本非零退出可作为 CI 门禁；答案键不进入公开测试文件。

## 7. 其他问题优先级

### P0

- ~~确认 GitHub Actions 全绿~~ 已完成；
- ~~完成统一多源证据契约~~ 已完成（`evidence_contract.py` + `evidence_adapters/`）；
- ~~完成一个可重复的多源联合研究 smoke~~ 已完成（`make evaluate-multi-source`）；
- ~~确认公开授权并发布 MIT 仓库~~ 已完成。

### P1

- ~~Redis 限流改为单次 Lua 原子执行，并在故障时降级到本地窗口~~ 已完成；
- ~~将 `ContextBudget` 接入主 Chat/Agent 请求组装和输出预留~~ 已完成；
- ~~将 `CitationLocator` 接入 Writer、API 响应与前端证据展示~~ 已完成；
- 由独立维护者制作经过来源预校验的 blind-v3。

### P2

- 可扩展倒排检索和持久化任务队列；
- 定时异地备份、TLS 与密钥托管；
- 进一步拆分 ECharts 图形算法、ClamAV 和历史报告索引整理。

## 8. 不要做的事

- 不要删除新闻、招投标、Text2SQL 或股票模块；它们属于平台层；
- 不要为了“全绿”降低质量阈值、删除失败样例或把问题答案重新放回 test/hidden；
- 不要声称 20/20 是真实业务 100%；
- 不要用模糊字符串相似度替代来源定位和证据支持判断；
- 不要让 LLM 的 `verdict=pass` 绕过 critical/major 确定性否决；
- 不要提交 `.env`、原始 PDF、私有答案、数据库、模型权重或 `node_modules`；
- 不要重建旧 Milvus 数据卷，除非先按 runbook 备份、审计并获得用户确认；
- 不要未经用户明确授权就公开仓库、发送消息、删除远端资源或推送新提交。

## 9. 可直接复制给其他模型的提示词

```text
你将继续维护仓库 industry-research-assistant。

项目正式定位：证据驱动行业研究平台，通用层包含知识库 RAG、新闻政策、招投标、产业数据库、
Text2SQL、公司行情和 Research Agent；半导体全产业链是第一个完成深度语料与评测闭环的垂直领域。

开始前完整阅读 README.md、docs/NEXT_MODEL_HANDOFF.md、
docs/MULTI_SOURCE_RESEARCH_PLATFORM.md、docs/PROJECT_CLOSURE_ROADMAP.md、
docs/RAG_EVALUATION_PROTOCOL.md 和 docs/AGENT_RELIABILITY.md。先运行 git status -sb、
git log --oneline -5、make check、make validate-observability，不要覆盖现有修改或破坏运行中的容器。

当前最优先任务：制作经过来源预校验的 blind-v3，或推进可扩展词法索引与连续数据库迁移验收。
`CitationLocator`、全部直接模型调用和预算压力矩阵均已闭环，不要重复实现。

必须保持事实边界：半导体 RAG 已深度验证；新闻、招投标、Text2SQL、股票目前是已接入但未完成
同等级专项评测。不能把固定集 20/20 称为真实准确率，不能把在线 SSE 称为 LangGraph 执行，
不能把 rrf_score 称为最终 RRF 排序。任何新增能力必须有失败处理、测试、机器可读报告和文档。

请先检查现状并给出小步计划，然后实现 P0 的下一项；完成后运行相关测试和全量 make check，
汇报修改文件、验证结果、剩余风险。未经明确授权不要公开、推送或删除 GitHub 资源。
```
