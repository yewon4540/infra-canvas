ARG OPENTOFU_VERSION=1.12.1
FROM ghcr.io/opentofu/opentofu:${OPENTOFU_VERSION}-minimal AS opentofu

FROM python:3.13-slim AS api
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
COPY apps/api/pyproject.toml ./
COPY apps/api/eolgae ./eolgae
RUN pip install --no-cache-dir .
COPY apps/api/alembic.ini ./
COPY apps/api/alembic ./alembic
COPY infrastructure/ ./infrastructure/
EXPOSE 8000
CMD ["sh", "-c", "alembic upgrade head && uvicorn eolgae.main:app --host 0.0.0.0 --port 8000"]

FROM api AS test
COPY apps/api/tests ./tests
RUN pip install --no-cache-dir pytest

FROM api AS executor
COPY --from=opentofu /usr/local/bin/tofu /usr/local/bin/tofu
RUN tofu version
CMD ["dramatiq", "eolgae.workers", "--processes", "1", "--threads", "4"]
