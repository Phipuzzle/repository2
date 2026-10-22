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
.\.venv\Scripts\python.exe -m scripts.verify_langfuse_trace
.\.venv\Scripts\python.exe -m scripts.verify_otel_chain
```
