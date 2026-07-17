# 结构化逐论断证据校验

## 1. 结论

结构化逐论断校验和可选的二次 LLM 语义裁判已经形成可运行、可审计、失败关闭的实验链路，
但当前不作为默认回答路径。

原因不是校验思想无效，而是当前 4B 本地模型对 JSON 结构、原文摘录和回答覆盖的遵循能力不足。
在同一份 20 题 regression 数据上，结构化路径把严格回答质量从 16/20 降到 12/20，
20 秒 SLA 从 20/20 降到 19/20。因此生产默认值为
`RAG_STRUCTURED_GROUNDING_ENABLED=false`，只有显式开启时才运行该实验路径。

## 2. 信任边界与数据流

```text
检索证据
   ↓
LLM 提出结构化 claim、citation_ids 和 evidence_quotes（不可信）
   ↓
服务端解析 JSON、检查 schema 与引用范围
   ↓
逐 claim 验证原文摘录、词法支持和技术标识符
   ↓
只保留通过验证的 claim
   ↓
服务端生成 [[n]] 引用并渲染答案
   ↓
SSE 返回答案、证据列表与 grounding audit
```

模型只是候选论断的提出者。引用编号、原文摘录和最终答案都不能因为由模型输出就被信任。
服务端在完整回答生成后再进行校验，因此牺牲首 token 流式延迟，以避免未经校验的内容先到达客户端。

## 3. 模型输出契约

```json
{
  "answer_status": "grounded",
  "claims": [
    {
      "text": "一条原子化事实论断，内部不含引用标记",
      "citation_ids": [1],
      "evidence_quotes": [
        {"citation_id": 1, "quote": "从对应证据逐字复制的原文"}
      ],
      "uncertainty": "certain"
    }
  ],
  "limitations": []
}
```

顶层状态只允许 `grounded` 或 `insufficient`；每条 claim 都必须有非空、范围内的引用编号。
论断文本不得自行携带 `[[n]]`。服务端对每条 claim 独立接受或拒绝，不因一条错误丢弃其他合格论断；
如果没有任何论断通过，则返回确定性拒答，而不是回退到未经校验的模型原文。

## 4. 跨语言证据

中文论断与英文证据可能没有可用的词面重叠，因此仅靠 token overlap 会产生大量误拒。
当前实现要求模型同时复制对应证据中的英文原句。服务端对空白归一化后做逐字子串校验，
验证通过的摘录可以证明该文字确实来自指定证据，并允许该引用通过来源校验。
但论断中的数值、全大写术语、带下划线标识符等仍必须真实存在于证据中；原文摘录不能绕过该检查。
如果一条论断仅依靠跨语言原文摘录通过，服务端会忽略模型给出的 `certain`，强制将其降为 `limited`。

必须区分两个概念：

- 原文摘录验证证明 provenance，即“这段话来自该切片”；
- 它不自动证明 entailment，即“该原文必然推出中文论断”。

默认审计对象会明确写入 `support_basis`、`provenance_only` 和
`semantic_entailment_verification=not_performed`，防止把来源校验误报成语义蕴含校验。

例如，“某国生产了全球约一半的氖气”并不自动等价于所有形式的“供应高度集中”结论。
显式开启 `RAG_SEMANTIC_ENTAILMENT_ENABLED=true` 时，系统把确定性初筛通过的 claim
和有界证据发给二次 LLM 裁判，要求每条严格返回 `entailed`、`not_entailed`
或 `uncertain`。只有 `entailed` 会被展示；缺项、重复、越界、非法标签和请求错误都失败关闭。

这仍是 LLM-as-judge，不是形式化证明。当裁判与生成使用同一模型时，它只是独立请求的二次检查，
不能声称为独立模型复核；证据中的 prompt injection、裁判偏差和跨语言错判仍需人工抽检。

## 5. 同集对照实验

四次实验使用相同的 regression 题目、检索链路、严格标签和 20 秒 SLA。

| 指标 | 自由文本严格基线 | 初始结构化 | 标识符防绕过 | 二次语义裁判 |
| --- | ---: | ---: | ---: | ---: |
| 严格质量通过 | 16/20 | 12/20 | 12/20 | 9/20 |
| SLA 通过 | 20/20 | 19/20 | 19/20 | 18/20 |
| 金标来源召回 | 16/16 | 16/16 | 16/16 | 16/16 |
| 金标来源被引用 | 15/16 | 12/16 | 11/16 | 7/16 |
| 逐概念引用支持达标 | 12/16 | 8/16 | 8/16 | 5/16 |
| 平均引用完整度 | 82.3% | 65.6% | 62.5% | 44.8% |
| 平均支持覆盖 | 77.1% | 55.7% | 54.2% | 36.5% |
| 无证据拒答 | 4/4 | 4/4 | 4/4 | 4/4 |
| 平均延迟 | 6.385 秒 | 8.545 秒 | 8.873 秒 | 12.709 秒 |
| P95 | 12.477 秒 | 14.599 秒 | 14.839 秒 | 22.676 秒 |
| 最大延迟 | 17.333 秒 | 23.911 秒 | 25.824 秒 | 34.944 秒 |

结构化实验共收到 47 条候选 claim，接受 35 条、拒绝 12 条，验证 36 段原文摘录。
拒绝原因包括 11 条 `insufficient_lexical_support` 和 1 条 `citation_out_of_range`。
主要失败表现是漏答问题要求、原文摘录并非逐字复制、引用越界，以及通过来源校验但未满足人工标签的语义覆盖。

增加“真实摘录不能授权证据中不存在的数值/技术标识符”防绕过规则后，再次收到 47 条候选，
接受 32 条、拒绝 15 条并验证 33 段摘录；拒绝原因为 14 条
`insufficient_lexical_support` 和 1 条 `citation_out_of_range`。两轮都重新调用生成模型，
因此接受数和延迟差异不能被当作单变量因果结论；防绕过能力由确定性反例单元测试单独证明。

二次语义裁判实验收到 43 条候选 claim，确定性初筛和语义裁判后最终保留 18 条、拒绝 25 条。
13 个用例进入二次裁判：11 个完成，2 个因裁判模型返回非法 verdict 而失败关闭，
后者连带拒绝 8 条初筛通过的 claim；其余 4 条被判定为 `uncertain`。
结果说明二次裁判能阻止语义不确定的输出，但当前 4B 本地模型的契约稳定性和召回不足，
不具备默认上线条件。该列也是独立重新生成，不是对同一批固定候选做的单变量消融。

报告：

- `reports/semiconductor_rag_answers_regression_claim_citation_2026-07-17.json`
- `reports/semiconductor_rag_answers_regression_structured_grounding_2026-07-17.json`
- `reports/semiconductor_rag_answers_regression_structured_grounding_provenance_guard_2026-07-17.json`
- `reports/semiconductor_rag_answers_regression_semantic_entailment_2026-07-17.json`

## 6. 复现实验

先在终端一启动实验服务：

```bash
make run-backend-structured
```

再在终端二运行严格回答评测：

```bash
make evaluate-answers-regression-structured
```

普通 `make evaluate-answers-regression` 仍评测默认自由文本路径。环境变量必须配置在后端服务进程，
只配置在评测客户端不会改变服务端行为。

语义裁判实验使用：

```bash
# 终端一
make run-backend-semantic

# 终端二
make evaluate-answers-regression-semantic
```

`RAG_ENTAILMENT_MODEL_MODE` 可以让裁判模型与生成模型分离；裁判方法、模型、
失败策略、逐条 verdict 和拒绝原因都写入 grounding audit。评测脚本同时汇总
裁判用例数、失败关闭数、语义接受/拒绝 claim 数和拒绝原因。

## 7. 默认启用门槛

只有同时满足以下条件，才重新评估默认开启：

1. 在冻结数据上严格质量不低于自由文本基线 16/20；
2. 20 秒 SLA 恢复到 20/20，且 P95 不高于 15 秒；
3. 金标来源引用与逐概念支持不低于自由文本基线；
4. JSON 合法率、原文摘录验证率和回答要求覆盖率达到预设门槛；
5. 对“摘录有效但语义不蕴含”的 NLI/人工分歧完成抽检；
6. 在未参与调参的 blind-v2 上复核，而不是只优化 regression。

当前适合的定位是安全研究功能和可观测性探针，而不是默认生产回答器。
