# 评测结果

评测日期：2026-10-22

## 30 条黄金问题：哈希基线 vs 本地 embedding

| 指标 | 哈希基线 | 本地 embedding |
| --- | --- | --- |
| SQL Execution Accuracy | 0.8333 | 0.8667 |
| Result Accuracy | 0.8333 | 0.8333 |
| Permission Accuracy | 0.8333 | 0.8667 |
| Chart Accuracy | 0.8000 | 0.7333 |
| SQL Semantic Accuracy | 0.8167 | 0.8222 |

本地 embedding 在 SQL Execution、Permission 和 SQL Semantic 三项有小幅提升，Result 持平；Chart 项因模型输出随机性略有波动。该差异基于单轮 30 条样本，后续可在更多问题和多次运行上求平均以降低方差。

评测详情由 `backend/evals/results.json` 生成，该文件为运行产物，不纳入版本控制。

观测验证：`python -m scripts.verify_langfuse_trace` 返回 OK，OpenTelemetry smoke trace 成功到达 Langfuse；`python -m scripts.verify_otel_chain` 运行真实 Agent 查询并确认 `agent.run` Trace 到达 Langfuse。
