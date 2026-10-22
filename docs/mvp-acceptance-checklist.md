# MVP 验收清单

## 功能

- [x] 自然语言查询 PostgreSQL，并实时返回 SQL、表格、图表和结论；
- [x] 桌面三栏工作区与移动端布局可用；
- [x] 查询取消、成本审批确认、补充条件、失败重试和反馈可用；
- [x] 空结果、权限失败、执行失败和 SSE 断线重连状态可用。

## 安全

- [x] SQL 通过 SQLGlot 只读校验与授权策略改写；
- [x] OIDC Bearer JWT 按 `iss` + `sub` 映射已登记用户；
- [x] 查询、事件、结果、反馈和审计日志按用户隔离；
- [x] 不向 Span 写入 SQL 正文、Prompt 正文或个人敏感信息。

## 可观测性

- [x] FastAPI、SQLAlchemy 与 Agent 节点接入 OpenTelemetry；
- [x] OTLP HTTP 导出到 Langfuse，trace 可回查；
- [x] 模型调用记录 Prompt 版本与 token 用量；
- [x] 数据库语句在 Span 中脱敏。

## 部署与启动

- [x] Docker Compose 启动 PostgreSQL + pgvector、Keycloak、Langfuse、后端与前端；
- [x] 数据库迁移、Demo 数据和开发 OIDC 用户自动初始化；
- [x] 前端生产构建在容器内完成。

## 评测

- [x] 简单、聚合、复杂三类黄金问题可重复执行；
- [x] 输出 SQL Execution、Result、Permission 与 Chart Accuracy；
- [x] 评测结果写入 `backend/evals/results.json`。
