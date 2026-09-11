"""OpenTelemetry bootstrap for openst (D56).

Sets up the Prometheus metric pipeline, a no-op trace SDK (Tempo-ready), and a
``/metrics`` route serving Prometheus text format. The stable HTTP semantic
convention metric names (``http.server.request.duration``) are opted into so
they match the Node.js Hono services.
"""

import os

os.environ.setdefault("OTEL_SEMCONV_STABILITY_OPT_IN", "http")

from fastapi import FastAPI, Response
from opentelemetry import metrics as otel_metrics
from opentelemetry import trace as otel_trace
from opentelemetry.exporter.prometheus import PrometheusMetricReader
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.resources import SERVICE_NAME, SERVICE_VERSION, Resource
from opentelemetry.sdk.trace import TracerProvider
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest


def setup_otel(app: FastAPI, service_name: str) -> None:
    resource = Resource.create(
        {
            SERVICE_NAME: service_name,
            SERVICE_VERSION: os.environ.get("APP_VERSION", "0.0.0-dev"),
        }
    )

    reader = PrometheusMetricReader()
    metering = MeterProvider(resource=resource, metric_readers=[reader])
    otel_metrics.set_meter_provider(metering)

    otel_trace.set_tracer_provider(TracerProvider(resource=resource))

    FastAPIInstrumentor.instrument_app(app, meter_provider=metering)
    HTTPXClientInstrumentor().instrument()

    @app.get("/metrics", include_in_schema=False)
    def metrics() -> Response:
        return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)