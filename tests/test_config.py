"""Tests for the telemetry configuration primitives."""

from __future__ import annotations

from opobserve.instrumentation.config import UnifiedTelemetryConfig


def test_resource_attributes_include_service_and_environment() -> None:
    config = UnifiedTelemetryConfig(
        service_name="secure-rag",
        environment="staging",
        resource_attributes={"team": "sre"},
    )

    attrs = config.resource_attributes_for("observability")
    assert attrs["service.name"] == "secure-rag"
    assert attrs["deployment.environment"] == "staging"
    assert attrs["opobserve.module"] == "observability"
    assert attrs["team"] == "sre"


def test_sampling_ratio_is_clamped() -> None:
    config = UnifiedTelemetryConfig(service_name="svc", sampling_ratio=42.0)
    assert config.sampling_ratio == 1.0

    config = UnifiedTelemetryConfig(service_name="svc", sampling_ratio=-1.0)
    assert config.sampling_ratio == 0.0


def test_merge_resource_attributes_returns_new_instance() -> None:
    config = UnifiedTelemetryConfig(service_name="svc", resource_attributes={"a": 1})
    updated = config.merge_resource_attributes({"b": 2, "a": 3})

    assert config.resource_attributes["a"] == 1
    assert updated.resource_attributes["a"] == 3
    assert updated.resource_attributes["b"] == 2
    assert updated is not config


def test_into_dict_produces_copy() -> None:
    config = UnifiedTelemetryConfig(service_name="svc", environment="qa")
    data = config.into_dict()
    data["service_name"] = "mutated"

    assert config.service_name == "svc"
    assert data["environment"] == "qa"
