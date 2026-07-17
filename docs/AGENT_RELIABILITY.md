# 研究 Agent 状态机、审核否决与恢复

## 1. 实际运行路径

项目虽然可以构建 LangGraph 图，但线上 SSE 路径实际调用的是
`DeepResearchGraph._run_simplified`。原因是手写异步状态机可以在每个 Agent 执行期间，
通过 `asyncio.Queue` 实时发送消息；当前 LangGraph 路径只保留为非主路径代码，不能在面试中表述为线上执行引擎。

```text
init
  ↓
planning ── checkpoint
  ↓
researching ── checkpoint
  ↓
analyzing（无数据需求时可跳过）── checkpoint
  ↓
writing ── checkpoint
  ↓
reviewing
  ├─ 审核通过 ───────────────→ completed / research_complete
  ├─ 缺证据 ─→ re_researching ─→ writing ─┐
  ├─ 文字问题 ─→ revising ─────────────────┤
  └─ 次数耗尽或审核不可解析 → review_failed / research_review_failed
                                           └→ reviewing
```

“循环停止”和“质量通过”是两个不同判断。只有 `phase=completed` 且
`review_status=approved` 才能发送 `research_complete`。

## 2. 审核终态契约

审核状态包含：

- `review_status`: `pending`、`approved` 或 `rejected`；
- `critical_issues`、`major_issues`、`unresolved_issues`：当前审核轮的问题数量；
- `completion_reason`: `review_passed`、`review_output_invalid`、
  `max_iterations_with_unresolved_issues` 等确定性终态原因；
- `iteration`: 已完成的审核次数，而不是已完成的修改次数。

审核模型的分数和 verdict 不直接可信。服务端会先归一化：

1. 只要存在 critical，最高质量分为 4，verdict 强制为 `major_issues`；
2. 存在 major 时，最高质量分为 6，verdict 至少为 `needs_revision`；
3. 分数低于 7 时，模型给出的 `pass` 会被撤销；
4. 审核 JSON 不可解析时失败关闭，直接进入 `review_failed`；
5. 达到最大审核次数但问题未清零时，停止自动修改但不批准报告。

拒绝事件仍携带草稿，方便人工查看和继续处理，但前端会加上“未通过质量审核”的警告，
且不会把该事件当成 `research_complete`。

## 3. 最大迭代次数为什么容易写错

旧实现从 `iteration=0` 开始，在审核不通过后才递增；第三次审核后还会执行一次修订，
但循环因 `iteration == max_iterations` 退出，最后那次修订没有再次审核。随后状态机又无条件写入
`completed`，导致严重问题被“次数用完”掩盖。

新语义是在每次审核完成时立即递增：

```text
审核 → iteration += 1
  ├─ pass                         → approved
  ├─ iteration >= max_iterations → rejected
  └─ 否则                         → 补充检索或修订
```

这样最大次数表示“最多允许多少次质量裁决”，不会产生未复核的最后一版。

## 4. Checkpoint 与真正的断点续跑

检查点在每个原子阶段结束后保存。状态中明确拆分两个字段：`phase` 表示当前正在执行或等待执行的阶段，
`last_completed_phase` 表示最近完整结束的原子阶段，也是线性流水线的恢复游标。
例如中途取消检索时保存 `phase=researching, last_completed_phase=planning`，恢复必须重新执行检索，
不能把“正在检索”误读成“检索已完成”。

| `last_completed_phase` | 恢复动作 |
| --- | --- |
| 空值 / `init` | 执行规划 |
| `planning` | 执行检索 |
| `researching` | 执行分析 |
| `analyzing` | 执行写作 |
| `writing` | 审核已保存草稿 |
| `reviewing` | 根据当前 `phase` 继续修订、补充检索或进入终态 |
| `completed` / `review_failed` | 终态，不应作为普通断点再次执行 |

恢复测试覆盖两个关键边界：从
`phase=reviewing, last_completed_phase=writing` 启动时，实际 Agent 调用序列只有
`critic`；从 `phase=researching, last_completed_phase=planning` 启动时，第一个重新调用的
Agent 是 `scout`，不会误跳到分析。

旧检查点没有 `last_completed_phase` 时，为了兼容会暂时把 `phase` 当作已完成阶段。
这种推断无法区分“正在执行”和“已执行完”，所以生产升级后应让旧任务自然结束或重新启动，
不将该兼容分支视为精确恢复保证。

检查点只能恢复到最近一个已完成原子阶段，不能恢复一个 Agent 内部执行到一半的网络请求。
这是 at-least-once 阶段执行语义，不是任意指令级快照。

## 5. 取消、异常与超时

### 用户取消

运行期间每次等待队列消息时都会检查 Redis 取消标志。发现取消后：

1. 取消当前 asyncio task；
2. 保存当前后端和 UI 状态；
3. 将 checkpoint 标为 `paused`，原因是 `cancelled_by_user`；
4. 恢复时清除旧取消标志并从检查点 phase 继续。

取消使用内部 `ResearchCancelled` 控制流立即退出当前阶段，因此半完成的规划、检索或写作不会被记录为
`completed`。旧取消标志在任何 `research_start/research_resumed` 事件之前清除，避免覆盖用户看到启动
事件后发出的新取消请求。取消实现位于 `core.research_control`，不从 graph 反向导入 router，
从而消除循环导入后落入“永不取消”fallback 的风险。

### Agent 异常

旧路径只记录日志并继续后续阶段，可能把缺少事实或草稿的状态送去审核。
现在异常会写入 `state.errors` 并重新抛出，顶层发送 `error` 事件，checkpoint 标为 `failed`，
且绝不发送 `research_complete`。

### 双层超时

- `AGENT_LLM_REQUEST_TIMEOUT_SECONDS=120`：OpenAI 兼容客户端的单次 HTTP 请求超时；
- `AGENT_LLM_MAX_RETRIES=1`：客户端自动重试上限；
- `AGENT_TIMEOUT_SECONDS=180`：一次 Agent `process` 的总时限，包括多次模型调用和本地处理。

总时限到达后，状态机取消 Agent task、记录错误并终止流程。asyncio 取消不能强制杀死已经进入线程的
同步 HTTP 调用，因此 HTTP 层超时仍然必要；两层解决的是不同问题。

## 6. 本轮发现并修复的真实故障

1. `unresolved_issues` 定义为整数，保存审核 checkpoint 时却调用 `len(int)`，首轮审核会异常；
2. 最大迭代耗尽后无条件写入 `completed`，critical 问题失去否决权；
3. 最后一次修订可能没有复核；
4. 恢复接口加载 checkpoint 后仍从规划重新执行；
5. Agent 异常被吞掉，流程继续运行；
6. LLM 和 Agent 没有明确超时；
7. 取消后 checkpoint 可能继续显示 `running`；
8. 前端只识别完成/错误/取消，不认识“执行结束但审核拒绝”。
9. 同一个 session 可以并发启动或恢复，多个状态机会覆盖同一 checkpoint；
10. V2 API 接收 `max_iterations` 却没有传给实际服务。
11. graph 反向导入 router 形成循环依赖，生产路径使用了永不取消的 fallback；
12. 清理旧取消标志晚于 `research_start`，可能覆盖刚发出的新取消；
13. 客户端断开后，已创建的 Agent task 仍继续调用模型；
14. 中途取消后，半完成阶段仍被写成 completed checkpoint。

这些故障都有确定性测试，不依赖真实模型输出：critical 否决、clean review 通过、状态机拒绝事件、
reviewing 恢复调用序列、Agent 异常和 Agent 超时。

## 7. 仍需验证的边界

- 同 session 已使用 Redis `SET NX EX` 原子互斥，锁持有者用 Lua compare-and-delete 释放；
  默认租约 3600 秒，超长任务尚未实现定时续租；
- 取消轮询间隔和外部 HTTP 终止时间仍受底层客户端影响；
- 旧 checkpoint 只对新增审核字段做运行时默认值补齐，尚无显式 schema version/migration；
- 尚未用真实本地模型跑完整的“取消—恢复—审核通过”端到端实验；
- checkpoint 保存失败目前记录日志但不阻止研究继续，需定义业务上是降级还是硬失败；
- failed 包含基础设施错误和审核拒绝两类，数据库状态可进一步拆为 `failed` 与 `needs_attention`。

并发锁失败关闭：锁已占用返回 HTTP 409，Redis 不可用返回 HTTP 503。锁在 SSE 生成器的
`finally` 中释放，因此正常完成、异常和客户端关闭生成器都会进入释放路径。V2 的
`max_iterations` 现在由 Pydantic 限制为 1–5 并传入 `DeepResearchV2Service`。

2026-07-17 已完成真实本地模型链路的“运行中取消 → checkpoint paused → resume →
重进未完成阶段 → 再次取消”。实验 session 在 `DeepScout` 运行期间取消后，持久化状态为：

```text
phase=researching
last_completed_phase=planning
status=paused
completion_reason=cancelled_by_user
```

恢复流首先返回 `research_resumed` 及上述两个阶段字段，然后只发出
`phase_skipped(planning)`，紧接着发出 `phase(researching)` 并重新启动 `DeepScout`。
两次取消均返回 `research_cancelled` 与 `[DONE]`；测试 checkpoint、取消标志与运行锁已清理。
该实验验证了取消、精确恢复游标和阶段重进，但没有声称完整报告最终审核通过。

2026-07-17 另一次真实本地模型实验不中途取消，完整执行 planning、researching、
analyzing、writing 和 reviewing，最终返回 `research_review_failed` 与 `[DONE]`。
Critic 原始结果虽然自报 `verdict=pass`，但同一结果中包含 1 个 critical、2 个 major 问题；
服务端规范化层将质量分限制为 4.0，并写入：

```text
phase=review_failed
last_completed_phase=reviewing
status=failed
review_status=rejected
completion_reason=max_iterations_with_unresolved_issues
critical_issues=1
major_issues=2
unresolved_issues=3
```

该实验证明了“模型说 pass”没有越过确定性严重问题否决权。草稿仍在拒绝事件中返回供调试，
但前端和持久化状态都明确标记为未批准，不能当成最终结论。

面试时应主动讲这些边界。可靠系统不是宣称“支持恢复”，而是能说明恢复粒度、重复执行语义、
终态判定以及失败后哪些输出仍可使用。
