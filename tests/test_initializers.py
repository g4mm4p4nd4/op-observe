"""Tests for the high-level instrumentation initialisers."""

from __future__ import annotations

from opobserve.instrumentation import (
    InstrumentationRegistry,
    MetricDefinition,
    UnifiedTelemetryConfig,
    init_observability_instrumentation,
    init_retrieval_instrumentation,
    init_security_instrumentation,
    init_telemetry_instrumentation,
)
from opobserve.instrumentation.wrappers import annotate_wrapper


def test_observability_initialisation_registers_defaults() -> None:
    config = UnifiedTelemetryConfig(service_name="svc")
    registry = init_observability_instrumentation(config)

    module = registry.get_module("observability")
    names = [metric.name for metric in module.metrics]
    assert "observability_requests_total" in names
    assert "observability_request_latency_seconds" in names
    assert len(module.wrappers) == 2


def test_reuse_registry_registers_all_modules() -> None:
    config = UnifiedTelemetryConfig(service_name="svc")
    registry = InstrumentationRegistry()

    init_observability_instrumentation(config, registry=registry)
    init_retrieval_instrumentation(config, registry=registry)
    init_security_instrumentation(config, registry=registry)
    init_telemetry_instrumentation(config, registry=registry)

    assert set(registry.modules) == {"observability", "retrieval", "security", "telemetry"}


def test_customisation_merges_without_duplicates() -> None:
    config = UnifiedTelemetryConfig(service_name="svc")
    registry = init_observability_instrumentation(config)

    module = registry.get_module("observability")
    duplicate_wrapper = module.wrappers[0]
    duplicate_metric_name = module.metrics[0].name

    custom_wrapper = annotate_wrapper("otel_span", "custom")
    custom_metric = MetricDefinition(name="custom_metric", description="custom")
    duplicate_metric = MetricDefinition(name=duplicate_metric_name, description="ignored")

    init_observability_instrumentation(
        config,
        registry=registry,
        wrappers=(duplicate_wrapper, custom_wrapper),
        metrics=(duplicate_metric, custom_metric),
    )

    module = registry.get_module("observability")
    assert module.wrappers.count(duplicate_wrapper) == 1
    assert custom_wrapper in module.wrappers

    names = [metric.name for metric in module.metrics]
    assert names.count(duplicate_metric_name) == 1
    assert "custom_metric" in names
