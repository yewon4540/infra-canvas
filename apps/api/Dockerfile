ARG OPENTOFU_VERSION=1.12.1
FROM ghcr.io/opentofu/opentofu:${OPENTOFU_VERSION}-minimal AS opentofu

FROM python:3.13-slim
WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY --from=opentofu /usr/local/bin/tofu /usr/local/bin/tofu
RUN tofu version

COPY apps/api/pyproject.toml ./
RUN pip install --no-cache-dir -e .

COPY apps/api/ .
COPY infrastructure/ ./infrastructure/

EXPOSE 8000
# api: alembic 마이그레이션 후 uvicorn 시작
# worker: docker-compose.yml 의 command 로 override (dramatiq eolgae.workers)
CMD ["sh", "-c", "alembic upgrade head && uvicorn eolgae.main:app --host 0.0.0.0 --port 8000"]
