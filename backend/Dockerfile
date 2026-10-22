ARG PYTHON_IMAGE=docker.m.daocloud.io/library/python:3.12-slim
FROM ${PYTHON_IMAGE}

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY pyproject.toml alembic.ini ./
COPY app ./app
COPY scripts ./scripts

RUN pip install --no-cache-dir -i https://pypi.tuna.tsinghua.edu.cn/simple .

EXPOSE 8000

CMD ["sh", "-c", "python -m alembic upgrade head && python scripts/seed_demo_data.py && python scripts/provision_dev_oidc_user.py && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
