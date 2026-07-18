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

## 尚未覆盖的生产能力

- TLS 终止、WAF 和反向代理上传限制；
- Redis/网关级分布式限流；
- refresh token、token 撤销和密钥轮换；
- 恶意文档沙箱、病毒扫描和内容安全审查；
- 密钥托管、审计日志、备份、HA 与灾难恢复。

这些能力未完成前，不应将项目描述为“生产级安全平台”。
