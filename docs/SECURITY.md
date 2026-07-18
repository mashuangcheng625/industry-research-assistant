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

## 尚未覆盖的生产能力

- TLS 终止、WAF 和反向代理上传限制；
- Redis/网关级分布式限流；
- refresh token、token 撤销和密钥轮换；
- 恶意文档沙箱、病毒扫描和内容安全审查；
- 密钥托管、审计日志、备份、HA 与灾难恢复。

这些能力未完成前，不应将项目描述为“生产级安全平台”。
