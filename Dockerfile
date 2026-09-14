FROM python:3.12-slim AS builder
WORKDIR /build
COPY requirements.txt .
COPY plugins/ ./plugins/
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

FROM python:3.12-slim AS test
WORKDIR /app
COPY --from=builder /install /usr/local
# the editable-install finder points at the source tree's absolute build path
COPY plugins/ /build/plugins/
# plugin tests live here; run them via `pytest plugins/` (isolated from tests/ to
# avoid a "tests" package-name collision) 
COPY plugins/ /app/plugins/
COPY pytest.ini ./
COPY src/ ./src/
COPY tests/ ./tests/
CMD ["python", "-m", "pytest", "tests/", "-v"]

FROM python:3.12-slim AS runtime
WORKDIR /app
# APP_VERSION is passed by CI (release tag); falls back to 0.0.0-dev at runtime
ARG APP_VERSION=""
ENV APP_VERSION=${APP_VERSION}
COPY --from=builder /install /usr/local
# the editable-install finder points at the source tree's absolute build path
COPY plugins/ /build/plugins/
COPY src/ ./src/
EXPOSE 8080
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8080"]
