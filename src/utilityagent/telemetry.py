"""OpenTelemetry traces for every conversation. Spans carry decisions, tokens and cost, never message text.

Locally spans go to whatever exporter is passed in (tests use the in-memory one). In Azure, setting
APPLICATIONINSIGHTS_CONNECTION_STRING sends them to Application Insights through the Azure Monitor exporter."""

from __future__ import annotations

import os

from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, SimpleSpanProcessor, SpanExporter
from opentelemetry.trace import Tracer


def tracer(exporter: SpanExporter | None = None, service: str = "utility-agent") -> Tracer:
    provider = TracerProvider(resource=Resource.create({"service.name": service}))
    if exporter is not None:
        provider.add_span_processor(SimpleSpanProcessor(exporter))
    conn = os.environ.get("APPLICATIONINSIGHTS_CONNECTION_STRING")
    if conn:
        from azure.monitor.opentelemetry.exporter import AzureMonitorTraceExporter  # optional dependency: [azure]

        provider.add_span_processor(BatchSpanProcessor(AzureMonitorTraceExporter(connection_string=conn)))
    return provider.get_tracer("utilityagent")
