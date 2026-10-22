# 评测结果

评测日期：2026-10-22

| 指标 | 结果 |
| --- | --- |
| SQL Execution Accuracy | 1.00 |
| Result Accuracy | 1.00 |
| Permission Accuracy | 1.00 |
| Chart Accuracy | 1.00 |
| SQL Semantic Accuracy | 1.00 |

三条黄金问题均完成真实 DeepSeek 调用、PostgreSQL 执行、授权改写和 ChartSpec 生成。评测详情由 `backend/evals/results.json` 生成，该文件为运行产物，不纳入版本控制。

观测验证：`python -m scripts.verify_langfuse_trace` 返回 OK，OpenTelemetry smoke trace 成功到达 Langfuse；`python -m scripts.verify_otel_chain` 运行真实 Agent 查询并确认 `agent.run` Trace 到达 Langfuse。
