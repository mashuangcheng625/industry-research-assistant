# 研究 Agent 可观测性

## 1. 目标与边界

可观测链路覆盖“模型请求 → Agent 任务 → 状态机阶段 → 研究终态 → checkpoint/互斥锁”。
指标不使用 `session_id`、query、证据文本或原始异常作 label，避免高基数、数据泄漏和不可控的存储成本。

`/metrics` 当前是进程内 Prometheus 指标。本地和单 worker 部署可直接使用；
多 worker 模式下，每个 worker 只看到自己的计数。在没有配置 Prometheus Python multiprocess mode
之前，不能把单个 worker 的 `/metrics` 误读为全局数据。

## 2. 指标设计

| 层级 | 指标 | 关键 label | 回答的问题 |
| --- | --- | --- | --- |
| 运行 | `industry_research_runs_total` | `resume`, `outcome` | 完成、审核拒绝、取消、异常和客户端断开各有多少 |
| 运行 | `industry_research_run_duration_seconds` | `resume`, `outcome` | 端到端延迟分布及恢复任务差异 |
| 并发 | `industry_research_active_runs` | 无 | 当前有多少 SSE 研究流正在执行 |
| 阶段 | `industry_research_phase_duration_seconds` | `phase`, `outcome` | 规划、检索、分析、写作和审核哪一段慢 |
| 阶段 | `industry_research_phase_transitions_total` | `phase`, `event` | 阶段启动或因断点恢复被跳过的次数 |
| Agent | `industry_research_agent_runs_total` | `agent`, `outcome` | 哪个 Agent 成功、异常或被取消 |
| Agent | `industry_research_agent_duration_seconds` | `agent`, `outcome` | 每种 Agent 的任务级耗时 |
| Agent | `industry_research_agent_timeouts_total` | `agent` | 状态机总超时触发次数 |
| LLM | `industry_research_llm_calls_total` | `agent`, `model`, `outcome` | 每个 Agent/模型的请求成功、失败和取消次数 |
| LLM | `industry_research_llm_duration_seconds` | `agent`, `model`, `outcome` | 模型请求延迟分布 |
| LLM | `industry_research_llm_tokens_total` | `agent`, `model`, `token_type` | 兼容端点有 usage 时的 prompt/completion token 用量 |
| 可靠性 | `industry_research_checkpoint_operations_total` | `operation`, `outcome` | checkpoint 保存/加载是否成功 |
| 可靠性 | `industry_research_run_lock_operations_total` | `operation`, `outcome` | 锁竞争、Redis 不可用或 owner 不匹配是否发生 |
| 可靠性 | `industry_research_cancellations_total` | `phase` | 用户通常在哪个阶段取消 |
| 质量 | `industry_research_review_outcomes_total` | `status`, `reason` | 审核通过与拒绝的结构化原因 |

`phase`、审核 `reason` 都通过白名单约束；未知值统一降级为 `unknown`。

## 3. 本地使用

后端启动后可直接检查：

```bash
curl -s http://127.0.0.1:8000/metrics | grep '^industry_research_'
```

启动可选 Prometheus profile：

```bash
make validate-observability
docker compose --profile observability up -d prometheus
```

Prometheus UI 位于 `http://127.0.0.1:9090`，配置通过
`host.docker.internal:8000` 抓取宿主机后端。配置内含 Agent 超时、研究运行错误、checkpoint 失败和
Redis 锁不可用四条告警规则。

## 4. 运行结果语义

- `approved`：Critic 审核通过，可作为最终报告。
- `review_failed`：已生成草稿，但存在未解决严重问题，不应当成最终结论。
- `cancelled`：状态机已观测到取消并保存 paused checkpoint。
- `client_disconnected`：SSE 消费者提前关闭；底层线程内 HTTP 请求可能要到客户端超时才真正返回。
- `error`：Agent、依赖或状态机异常。
- `incomplete`：图正常结束，却没有产生审核通过、审核拒绝、取消或错误事件；这本身是应调查的状态机异常。

## 5. 生产边界

- `/metrics` 未做应用层认证，生产环境应只向内网 Prometheus 暴露，或在反向代理层限制访问。
- token 指标依赖 OpenAI 兼容端点返回 usage；不返回时不会伪造估算值。
- Histogram bucket 根据当前本地 4B 实验延迟设置，模型或硬件变更后需重新校准。
- 指标适合聚合趋势与告警；单次故障定位仍需 checkpoint 状态和结构化日志。

## 6. 真实链路验证

2026-07-17 使用 `industry-qwen3:4b` 和本地封装测试库，完整执行一次
“UCIe 作用与标准缺口”研究。运行未发生 Agent 异常，但因 Critic 发现
1 个 critical 和 2 个 major 问题而进入 `review_failed`。这个区分非常重要：
Agent 成功率是执行可靠性，review outcome 才是产物质量门禁。

| 观测项 | 实测值 |
| --- | ---: |
| 运行终态 | `review_failed` |
| 端到端耗时 | 294.636 秒 |
| planning | 14.991 秒 |
| researching | 99.856 秒 |
| analyzing | 68.664 秒 |
| writing | 86.444 秒 |
| reviewing | 24.679 秒 |
| Agent 任务 | 6/6 执行成功 |
| LLM 请求 | 17/17 执行成功 |
| prompt / completion token | 27,233 / 13,339 |
| checkpoint 保存 | 6/6 成功 |
| 流结束后 active runs | 0 |

DeepScout 的 6 次 LLM 请求耗时总和为 253.930 秒，但 Agent 墙钟时间仅 99.857 秒，
因为多个章节并行检索与抽取。所以不能把并行子请求 duration 求和当成用户等待时间；
端到端 histogram 和 Agent histogram 分别回答不同问题。
