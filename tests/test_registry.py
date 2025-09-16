"""Tests for the instrumentation registry."""

from __future__ import annotations

import pytest

from opobserve.instrumentation.config import UnifiedTelemetryConfig
from opobserve.instrumentation.registry import (
    InstrumentationRegistry,
    MetricDefinition,
)
from opobserve.instrumentation.wrappers import annotate_wrapper


def sample_wrapper() -> None:
    pass


def test_register_module_stores_wrappers_and_metrics() -> None:
    registry = InstrumentationRegistry()
    config = UnifiedTelemetryConfig(service_name="svc")
    wrapper = annotate_wrapper("otel_span", "demo")
    metric = MetricDefinition(name="demo_total", description="Demo counter")

    registry.register_module("demo", config, wrappers=[wrapper], metrics=[metric])

    module = registry.get_module("demo")
    assert module.config is config
    assert module.wrappers == [wrapper]
    assert module.metrics == [metric]


def test_extend_helpers_append_data() -> None:
    registry = InstrumentationRegistry()
    config = UnifiedTelemetryConfig(service_name="svc")
    registry.register_module("demo", config)

    extra_wrapper = annotate_wrapper("otel_span", "extra")
    extra_metric = MetricDefinition(name="extra", description="Extra metric")

    registry.extend_wrappers("demo", [extra_wrapper])
    registry.extend_metrics("demo", [extra_metric])

    module = registry.get_module("demo")
    assert extra_wrapper in module.wrappers
    assert extra_metric in module.metrics


def test_extend_helpers_raise_for_unknown_module() -> None:
    registry = InstrumentationRegistry()

    with pytest.raises(KeyError):
        registry.extend_wrappers("unknown", [])

    with pytest.raises(KeyError):
        registry.extend_metrics("unknown", [])
