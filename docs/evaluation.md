# 评测与黄金问题集

## 黄金问题

评测集位于 `backend/evals/golden_questions.json`，共 30 条，覆盖简单、聚合、复杂、过滤、join、时间、空结果等类别。

| ID | 类别 | 问题 | 预期指标 | 预期图表 |
| --- | --- | --- | --- | --- |
| simple-monthly-east-sales | 简单 | 查询今年华东区域各月的销售额和订单数 | 月销售额、订单数 | line：month → sales |
| aggregate-region-sales-ranking | 聚合 | 统计各区域的订单数和总销售额，按销售额从高到低排列 | 区域、订单数、总销售额 | bar：region → sales |
| complex-region-category-mix | 复杂 | 对比今年华东和华南各商品类别的销售额 | 区域、商品类别、销售额 | bar：region → sales |

其余问题覆盖月度订单数、季度过滤、退款订单、平均订单金额、环比增长、累计销售额、窗口排名和空结果等场景。每条问题均可通过 `--self-check` 先验证 golden SQL。

每条黄金问题都记录了问题、预期 SQL 语义、可执行的 golden SQL、结果说明和预期图表。

## 准确率指标

- SQL Execution Accuracy：Agent 生成的 SQL 是只读查询且执行成功；
- Result Accuracy：执行结果与 golden SQL 结果集合一致（忽略列顺序和数值格式）；
- Permission Accuracy：生成的 SQL 通过授权策略改写，不越权访问资源；
- Chart Accuracy：ChartSpec 的类型、X/Y 字段与预期一致；
- SQL Semantic Accuracy：生成的 SQL 包含预期的关键 SQL 语义。

## 执行评测

在 `backend` 目录，确保 `AGENT_ENABLED=true` 且已配置 `DEEPSEEK_API_KEY`：

```powershell
.\.venv\Scripts\python.exe -m evals.run_evaluation
```

评测结果写入 `backend/evals/results.json`，并输出各项准确率摘要。

只校验 golden SQL：

```powershell
.\.venv\Scripts\python.exe -m evals.run_evaluation --self-check
```

最近一次实测结果见 `docs/evaluation-results.md`。

## 观测验证

```powershell
cd backend
.\.venv\Scripts\python.exe -m scripts.verify_langfuse_trace
.\.venv\Scripts\python.exe -m scripts.verify_otel_chain
```

第一个脚本发送一个 OpenTelemetry trace 到 Langfuse 并确认到达；第二个脚本确认真实 `agent.run` 查询链路 Trace 存在于 Langfuse。Langfuse UI 打开 http://localhost:3001 ，可查看 Trace、模型调用、token 用量和 Prompt 版本。
