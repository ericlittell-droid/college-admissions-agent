"""Distributed Tracing with OpenTelemetry.

Integrates OpenTelemetry distributed tracing to link spans across coordinator
planning, subagent delegation, tool executions, and Google Cloud Trace.
"""

from contextlib import contextmanager
from typing import Any, Generator
from config.settings import settings


class AgentTracer:
    """Wrapper managing distributed OpenTelemetry spans."""

    def __init__(self, service_name: str = "college-admissions-agent"):
        self.service_name = service_name
        self._tracer = None
        self._init_tracer()

    def _init_tracer(self) -> None:
        """Initializes OpenTelemetry tracer if enabled in settings."""
        if not settings.enable_opentelemetry:
            return

        try:
            from opentelemetry import trace  # type: ignore
            from opentelemetry.sdk.trace import TracerProvider  # type: ignore
            from opentelemetry.sdk.resources import Resource  # type: ignore

            provider = TracerProvider(resource=Resource.create({"service.name": self.service_name}))
            trace.set_tracer_provider(provider)
            self._tracer = trace.get_tracer(self.service_name)
        except Exception:
            # Fallback gracefully if opentelemetry package is not installed in the local environment
            self._tracer = None

    @contextmanager
    def start_span(
        self, span_name: str, attributes: dict[str, Any] | None = None
    ) -> Generator[Any, None, None]:
        """Context manager creating a distributed trace span."""
        if self._tracer:
            with self._tracer.start_as_current_span(span_name) as span:
                if attributes:
                    for k, v in attributes.items():
                        span.set_attribute(k, str(v))
                yield span
        else:
            # Lightweight mock span yielding a dummy object for hermetic local testing
            class NoopSpan:
                def set_attribute(self, k: str, v: Any):
                    pass

            yield NoopSpan()


global_tracer = AgentTracer()
