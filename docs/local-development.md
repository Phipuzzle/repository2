# 本地开发手册

## 前置条件

- Docker Desktop；
- Node.js 20+ 与 npm；
- Python 3.11+（推荐使用 `uv`）。

## 一键启动

```powershell
cd infra
Copy-Item .env.example .env -ErrorAction SilentlyContinue
docker compose up -d --build
```

启动后：

```text
前端: http://localhost:3000
API:  http://localhost:8000
OpenAPI: http://localhost:8000/docs
Keycloak: http://localhost:8080
Langfuse: http://localhost:3001
PostgreSQL: localhost:5432
```

本地开发账号：`developer` / `ida-dev-password`（仅限 localhost）。

## 后端本地运行

```powershell
cd backend
Copy-Item .env.example .env
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe scripts\seed_demo_data.py
.\.venv\Scripts\python.exe scripts\provision_dev_oidc_user.py
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000
```

若要重建 Demo 数据：

```powershell
.\.venv\Scripts\python.exe scripts\reset_demo_data.py
```

## 前端本地运行

```powershell
cd frontend
Copy-Item .env.example .env.local
npm install
npm run dev
```

## 质量检查

```powershell
cd backend
.\.venv\Scripts\python.exe -m ruff check app tests
.\.venv\Scripts\python.exe -m pytest -q

cd ..\frontend
npm run lint
npm test
npm run build
npm run e2e
```

## 评测与观测

```powershell
cd backend
.\.venv\Scripts\python.exe -m evals.run_evaluation
.\.venv\Scripts\python.exe -m scripts.import_feedback_candidates
.\.venv\Scripts\python.exe -m scripts.verify_langfuse_trace
.\.venv\Scripts\python.exe -m scripts.verify_otel_chain
.\.venv\Scripts\python.exe -m scripts.verify_slo
```

SLO 阈值通过 `SLO_AGENT_P95_SECONDS`、`SLO_AGENT_ERROR_RATE`、`SLO_DEEPSEEK_P95_SECONDS`、`SLO_DEEPSEEK_ERROR_RATE` 配置，超阈值时脚本以非零码退出。

设置 `ALERT_WEBHOOK_URL` 后，SLO 告警会以 JSON POST 到该地址；报告写入 `backend/evals/slo-report.json`。

## 语义检索

默认使用确定性的哈希 embedding，可在不下载模型的情况下运行。若要启用本地多语言模型：

```powershell
cd backend
pip install -e ".[embeddings]"
$env:EMBEDDING_PROVIDER = "local"
modelscope download --model BAAI/bge-small-zh-v1.5 --local_dir .models\bge-small-zh-v1.5
$env:EMBEDDING_MODEL_ID = ".models\bge-small-zh-v1.5"
$env:EMBEDDING_DIMENSION = "512"
.\.venv\Scripts\python.exe -m scripts.reindex_metadata
```

模型从 ModelScope 下载到 `backend/.models/bge-small-zh-v1.5`，该目录已加入 `.gitignore`。如需其他模型，可调整 `EMBEDDING_MODEL_ID` 与 `EMBEDDING_DIMENSION`。
