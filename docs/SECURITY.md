# 安全边界与部署要求

本项目是本地可复现的研究型 MVP，不是互联网生产环境的完整安全方案。以下规则属于不可绕过的最低边界。

## 身份与资源隔离

- `/chat`、`/research`、`/documents`、`/search` 和 `/attachments` 需要有效 JWT；
- 附件的上传、读取、列表、问答引用和删除均按 `user_id` 过滤；
- 登录、注册、普通高成本请求和 Research Agent 使用不同限流额度；
- 当前限流器为单进程语义。多 worker 或多实例部署必须迁移到 Redis 原子计数器，不能把单进程额度解释成集群额度。

## JWT 配置

`JWT_SECRET_KEY` 必须为至少 32 字符的非默认随机值。缺失、过短或使用仓库示例值时，应用拒绝启动。

隔离的本地 Docker 演示可以显式设置：

```dotenv
ALLOW_INSECURE_DEMO_SECRET=true
```

预发布、公开演示和生产环境必须使用：

```dotenv
ALLOW_INSECURE_DEMO_SECRET=false
JWT_SECRET_KEY=<随机生成的高强度密钥>
```

## 文件上传

- 默认最大 20 MiB，可通过 `MAX_UPLOAD_BYTES` 下调；
- 文件写入随机临时路径，不使用用户提供的路径；
- 用户文件名只保留 basename；
- 同时校验扩展名、MIME 和基础文件签名；
- 索引名称只接受受限字符集；
- 解析失败、超限和签名不符时清理临时文件；
- 文档解析在线程池执行，避免直接阻塞 ASGI 事件循环。

## Text2SQL 安全（P1-1）

`Text2SQLService.validate_sql` 的旧关键字黑名单已下线，全部改为
[`SQLGuard`](/home/xiaoma/projects/大模型项目/llm-application-portfolio/industry-research-assistant/backend/app/core/text2sql_guard.py)
AST 检查。守卫的硬性边界是：

- 只允许顶层 `SELECT`，包括合法的 `WITH` / `UNION`，并对 CTE 内部再次校验，禁止 `WITH x AS (DELETE ...) SELECT ...`；
- 拒绝 `INSERT` / `UPDATE` / `DELETE` / `MERGE` / `DROP` / `CREATE` / `ALTER` / `TRUNCATE` / `COPY` / `EXPLAIN` / `DO` / `CALL`；
- 拒绝 `pg_catalog` / `information_schema` / `pg_*` 等系统对象，以及 `pg_sleep` / `BENCHMARK` 等时间消耗函数；
- 拒绝 SQL 注释（含字符串字面量之外的所有 `--` / `/* */`），防止注释绕过；
- 表、列白名单分别存放在 `text2sql_guard.ALLOWED_TABLES` 中；当前仅允许
  `industry_stats`、`company_data`、`policy_data` 三个行业研究表；
- 行数上限默认 100，可通过 `TEXT2SQL_MAX_ROWS` 调整；SQL 中已声明的
  `LIMIT` 超过该上限会被拒绝，未声明的会被自动追加；
- `backend='sqlglot'` 为默认；`backend='dual'` 额外调用 `pglast`
  做 libpg_query 双引擎交叉，仅在调试场景下使用。

白名单目前是代码常量，对应 `backend/app/models/industry_data.py` 的 SQLAlchemy
模型字段。新增行业研究表时应同时更新 `text2sql_guard.ALLOWED_TABLES`，
否则表会被默认拒绝。守卫失败的判定作为结构化 `GuardResult` 返回，
`Text2SQLService.validate_sql` 仍以 `(ok, message)` 两元组对外暴露，
错误信息末尾追加 `[GUARD_CODE]` 便于上游定位。

相关单元测试在 `backend/test/test_text2sql_guard.py`（72 项）与
`backend/test/test_security_boundaries.py` 中 `test_text2sql_service_*`
覆盖。

## 多源 Provider 可靠性（P1-2）

新闻、招投标与股票行情三个外部数据源由
[`ProviderReliability`](/home/xiaoma/projects/大模型项目/llm-application-portfolio/industry-research-assistant/backend/app/core/provider_reliability.py)
包装后再发出请求，统一的硬性边界：

- 每个外部调用都有显式 per-attempt 超时（可通过
  `NEWS_PROVIDER_TIMEOUT_SECONDS`、`BIDDING_PROVIDER_TIMEOUT_SECONDS`、
  `STOCK_PROVIDER_TIMEOUT_SECONDS` 覆盖，默认 8–10 秒）和有限重试
  （默认 2 次，env 变量可调）；
- 5xx、连接错误、429 与超时属于"可重试"；4xx、JSON 解析失败、未知
  异常属于"终态"，不再重试；
- 失败路径绝不编造结果 —— `ProviderOutcome.ok=False` 时
  `data=None`、`degraded=True`，调用方根据 `error_code` 选择降级
  行为；
- 每个 service 维护最多 32 条最近 `ProviderOutcome` 滚动缓冲；
  通过 `last_outcome()` 提供给上层多源编排做拒绝式判断；
- 服务返回的 dict 在保留旧 `success`/`error` 字段的同时新增
  `degraded` 与 `provider_code`，便于调度器把"零结果"与"采集失败"
  区别对待，避免把降级数据当作证据写入 `multi_source_research` 的
  引文列表。

Text2SQL 的 `execute_sql` 在 P1-1 阶段已通过 `SQLGuard` 拿到 AST
层保护；数据库侧的超时建议在 PostgreSQL 会话级
`statement_timeout` 上设置（不在本 PR 范围）。

相关单元测试：`backend/test/test_provider_reliability.py`（30 项）。
后续若加入新外部数据源，应使用同一 `ProviderReliability` 包装
后再发出请求。

## 数据治理（P1-3）

新闻、招投标两类外部采集的数据由
[`data_governance`](/home/xiaoma/projects/大模型项目/llm-application-portfolio/industry-research-assistant/backend/app/core/data_governance.py)
统一处理，硬性边界：

- **去重**：除原有的 `source_url` / `bid_id` 唯一索引外，新增
  `dedup_key` 列。`news_dedup_key` / `bidding_dedup_key` 通过 NFKC 归一化 +
  SHA-256 摘要产出稳定身份——同一资讯从不同聚合源采集时会折叠为
  一行；新增 `create_all` 自动建表的部署会同时获得 `dedup_key`
  与 `parties` 列（`JSONB`），已有部署需要 `ALTER TABLE` 一次性补列
  （参见 `docs/SECURITY.md` 的「数据迁移」备注）。
- **实体归一**：`normalise_party_name` 把
  `中芯国际集成电路制造（上海）有限公司` 与
  `中芯国际集成电路制造(上海)股份有限公司` 都归一到
  `中芯国际集成电路制造`，下层 `extract_parties` 用 NFKC + 全角/半角
  冒号 + 多种角色关键词（采购人 / 招标人 / 中标人 / 供应商 等）抽取并
  存到 `BiddingInfo.parties`。结果可以是空 dict，宁可漏抽也不
  编造。
- **公告生命周期**：`cluster_lifecycle` 按
  `normalise_party_name` + 去噪后的标题前缀做最长 24 字符匹配，
  兼容「中芯国际」与「中芯国际集成电路制造」这种长短名字变体，
  把同一项目的 招标 / 中标 / 更正 链到一起；不同 buyer 或标题前
  缀差异不会被错误合并。
- **股票代码解析**：`StockCodeResolver` 替换旧的硬编码
  `COMPANY_STOCK_MAP`，每次解析都写入审计日志（最近 256 条），
  并把审计事件推送给可选的 `audit_sink`，方便生产侧在
  `metric`、`log` 中跟踪公司名识别命中与失败。`config/stock_mapping.py`
  保留为薄 shim，导入名不变。
- **失败行为**：去重失败、解析失败、匹配失败都属于"宁可不写
  入"，由 `NewsCollectionService` / `BiddingService` 自身的
  `ProviderReliability` 一起构成完整链路，绝不编造内容。

相关单元测试：`backend/test/test_data_governance.py`（47 项）。
数据迁移说明：上述模型字段新增后，旧部署应通过手工 `ALTER TABLE`
或 Alembic 迁移补齐 `industry_news.dedup_key`、
`bidding_info.dedup_key` 与 `bidding_info.parties` 三列；为空时去重
逻辑会自然回退到 URL / bid_id 唯一索引，不会出错。

## 尚未覆盖的生产能力

- TLS 终止、WAF 和反向代理上传限制；
- Redis/网关级分布式限流；
- refresh token、token 撤销和密钥轮换；
- 恶意文档沙箱、病毒扫描和内容安全审查；
- 密钥托管、审计日志、备份、HA 与灾难恢复。

这些能力未完成前，不应将项目描述为“生产级安全平台”。
