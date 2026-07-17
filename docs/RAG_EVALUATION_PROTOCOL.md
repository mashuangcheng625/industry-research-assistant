# 半导体 RAG 评测协议

## 目的

评测集用于发现检索和回答链路的泛化缺陷，不用于证明产品已经达到业务准确率。
日常调参只能使用 development，regression 只用于防回退。test/hidden 公开文件
仅包问题，答案键由评测维护者私有保管。

## 80题结构

| 分层 | 数量 | 用途 | 是否允许日常查看答案 |
| --- | ---: | --- | --- |
| regression | 20 | 保证第一阶段能力不回退 | 是 |
| development | 20 | 开发、诊断与消融 | 是 |
| test | 20 | 阶段性泛化验证 | 否 |
| hidden | 20 | 阶段验收；不等于真正盲测 | 否 |

四个产业方向各20题，单文档事实、专业参数、综合分析、跨段落和无证据题各16题。

公开资产：

- `semiconductor_rag_eval_regression.json` 和 `semiconductor_rag_eval_development.json`：有标签；
- `semiconductor_rag_eval_test_questions.json` 和 `semiconductor_rag_eval_hidden_questions.json`：仅公开字段；
- `semiconductor_rag_eval_manifest.json`：数量、标签可见性和公开文件 SHA-256。

私有资产位于 Git 忽略的 `data/evaluation-private/`：80 题主集以及 test/hidden
答案键。检索实现、查询改写词表和公开 CI 不得读取该目录。

## 数据质量闸门

```bash
# 公开 CI：校验 40 题开发标签与 40 题无标签问题，同时阻断答案泄漏
make validate-eval

# 评测维护者本地：校验 Git 忽略的 80 题完整主集
make validate-eval-private
```

闸门检查ID、问题重复、领域与知识库映射、正负例契约、分层值、领域均衡，以及每个正例
术语组是否真实存在于人工指定的金标文档。Schema通过不代表题目语义一定正确，新增题仍需
人工抽样复核。

## 推荐执行顺序

1. 在原索引运行 regression 和 development，保存基线。
2. 只根据 development 失败原因修改通用能力。
3. regression 必须保持通过，然后冻结代码、配置和索引快照。
4. 由不参与调参的评测维护者运行 test/hidden，开发者只接收汇总结果与必要失败归因。
5. 报告必须同时给出正例召回、负例拒绝、金标来源命中和按题型/领域分组结果，不能只报总分。
6. 端到端答案评测必须把内容质量（`quality_passed`）和延迟 SLA（`latency_ok`）分开统计；
   `passed` 仍表示两者同时通过，禁止通过放宽延迟阈值掩盖性能波动。

## 禁止行为

- 不得删除失败题、把失败题改成更容易的问法或降低覆盖率来提高分数。
- 不得把 test/hidden 问题原文加入查询改写词表。
- 不得因替代文档也能回答，就悄悄移除人工金标来源；应先由领域人员审核是否允许多金标。
- 不得把测试集20/20描述为真实业务准确率100%。

## 历史结果与真盲测边界

2026-07-17 之前，仓库内曾存在包含 test/hidden 完整标签的聚合文件，旧生成脚本
也硬编码了这些标签。因此已有 test/hidden 分数只能称为“历史、受污染的阶段
验收”，不得称为盲测或泛化能力证明。

真正的 blind-v2 必须在代码冻结后由独立复核者新建，问题与答案在验收前都不对调参
操作者可见，并在独立环境执行。现有 hidden 即使更名或重新切分，也不会恢复盲测资格。
