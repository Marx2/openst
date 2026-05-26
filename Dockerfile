FROM python:3.12-slim AS builder
WORKDIR /build
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

FROM python:3.12-slim AS test
WORKDIR /app
COPY --from=builder /install /usr/local
COPY pytest.ini ./
COPY src/ ./src/
COPY tests/ ./tests/
CMD ["python", "-m", "pytest", "tests/", "-v"]

FROM python:3.12-slim AS runtime
WORKDIR /app
COPY --from=builder /install /usr/local
COPY src/ ./src/
EXPOSE 8080
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8080"]
