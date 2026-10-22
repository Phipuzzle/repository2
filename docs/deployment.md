# 部署与工程化

## 环境

- `development`：本地 Compose，默认账号与配置见 `docs/local-development.md`。
- `production`：复制 `infra/.env.production.example` 为 `infra/.env`，替换所有密钥、数据库密码和 OIDC 配置。

## 镜像与健康检查

国内网络需先给 Docker Desktop 配置 registry-mirrors，例如：

```json
{
  "registry-mirrors": [
    "https://docker.mirrors.ustc.edu.cn",
    "https://hub-mirror.c.163.com",
    "https://mirror.baidubce.com"
  ]
}
```

Dockerfile 已内置清华 PyPI 镜像和 npmmirror，用于容器内依赖安装。
基础镜像默认使用 `registry.cn-hangzhou.aliyuncs.com`，可通过 `--build-arg PYTHON_IMAGE=...` 和 `--build-arg NODE_IMAGE=...` 覆盖。

```powershell
cd infra
docker compose build backend frontend
docker compose up -d --build
docker compose ps
```

后端健康检查：http://localhost:8000/health

## 数据库迁移

```powershell
cd backend
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe -m alembic current
```

回滚一个版本：

```powershell
.\.venv\Scripts\python.exe -m alembic downgrade -1
```

每次发布前在独立环境执行一次升级与回滚演练。

## CI

- `.github/workflows/ci.yml`：前端 lint/test/build，后端 ruff/pytest。
- `.github/workflows/evaluation.yml`：评测与 SLO 门禁。
