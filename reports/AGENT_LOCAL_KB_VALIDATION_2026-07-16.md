# Deep Research Agent 本地知识库验证

日期：2026-07-16

## 验证结果

- Docker 基础服务已恢复：PostgreSQL、Redis、etcd、MinIO 和 Milvus 健康。
- 使用 7 份已审核公开全文重建 4 个半导体知识库，共 3916 个真实语料切片。
- 四方向真实资料检索回归：4/4 通过。
- DeepScout 使用 `industry-qwen3:4b` 完成一次真实 Milvus 检索与事实提取。
- 生成的 3 条事实全部绑定到 `semiconductor_packaging_testing` 中的 NIST CHIPS 1400-2 文档，没有伪造引用。

## 真实 Agent 问题

> Chiplet 互连接口标准、互操作性和测试验证目前有哪些关键技术缺口？

Agent 提取的事实：

1. 需建立 Chiplet 接口的标准化定位与对齐规范以确保互操作性。
2. 缺乏针对 Chiplet 失效分析的早期非破坏性检测标准。
3. 需发展用于 Chiplet 系统功能测试的缺陷定位能力，以支持异构集成系统的修复。

引用：`local://kb/semiconductor_packaging_testing/1d27caa3b16ed6f1222e73bfcd0844ee`

## 本轮修复的问题

1. `kb_name` 未从 API 透传到 Agent 状态。
2. DeepScout 将本地检索集合硬编码为不存在的 `knowledge_base`。
3. Agent 没有复用项目的本地/云端模型路由。
4. 本地小模型使用 16000 token 输出上限，与实际上下文窗口不匹配。
5. 检索结果较多时，结构化 JSON 过长被截断。现已限制事实和附加字段数量。
6. 事实引用现在必须来自本次实际检索结果，非法 URL 不会被保留。

