"""Utility to push representative OTLP traces, metrics, and logs over HTTP."""

from __future__ import annotations

import argparse
import json
import time
from typing import Any, Dict

import urllib.request
from urllib.error import URLError, HTTPError


def _now_unix_nano() -> int:
    return int(time.time() * 1e9)


def _build_trace_payload() -> Dict[str, Any]:
    now = _now_unix_nano()
    return {
        "resourceSpans": [
            {
                "resource": {
                    "attributes": [
                        {"key": "service.name", "value": {"stringValue": "opobserve-demo"}},
                        {"key": "telemetry.sdk.language", "value": {"stringValue": "python"}},
                    ]
                },
                "scopeSpans": [
                    {
                        "scope": {"name": "integration-test", "version": "1.0.0"},
                        "spans": [
                            {
                                "traceId": "0" * 32,
                                "spanId": "0" * 16,
                                "name": "integration-span",
                                "kind": 1,
                                "startTimeUnixNano": now,
                                "endTimeUnixNano": now + int(2e6),
                                "attributes": [
                                    {"key": "opobserve.test", "value": {"stringValue": "true"}},
                                    {"key": "deployment.environment", "value": {"stringValue": "local"}},
                                ],
                            }
                        ],
                    }
                ],
            }
        ]
    }


def _build_metric_payload() -> Dict[str, Any]:
    now = _now_unix_nano()
    return {
        "resourceMetrics": [
            {
                "resource": {
                    "attributes": [
                        {"key": "service.name", "value": {"stringValue": "opobserve-demo"}},
                    ]
                },
                "scopeMetrics": [
                    {
                        "scope": {"name": "integration-test", "version": "1.0.0"},
                        "metrics": [
                            {
                                "name": "integration_counter",
                                "sum": {
                                    "aggregationTemporality": 2,
                                    "isMonotonic": True,
                                    "dataPoints": [
                                        {
                                            "startTimeUnixNano": now - int(5e9),
                                            "timeUnixNano": now,
                                            "asDouble": 1.0,
                                        }
                                    ],
                                },
                            }
                        ],
                    }
                ],
            }
        ]
    }


def _build_log_payload() -> Dict[str, Any]:
    now = _now_unix_nano()
    return {
        "resourceLogs": [
            {
                "resource": {
                    "attributes": [
                        {"key": "service.name", "value": {"stringValue": "opobserve-demo"}},
                    ]
                },
                "scopeLogs": [
                    {
                        "scope": {"name": "integration-test", "version": "1.0.0"},
                        "logRecords": [
                            {
                                "timeUnixNano": now,
                                "severityNumber": 9,
                                "severityText": "Info",
                                "body": {"stringValue": "integration log line"},
                            }
                        ],
                    }
                ],
            }
        ]
    }


def _post_json(url: str, payload: Dict[str, Any]) -> None:
    data = json.dumps(payload).encode('utf-8')
    request = urllib.request.Request(url, data=data, headers={'Content-Type': 'application/json'})
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            if response.status not in (200, 202):
                raise RuntimeError(f'Unexpected status {response.status} from {url}')
    except HTTPError as exc:
        raise RuntimeError(f'HTTP error posting to {url}: {exc}') from exc
    except URLError as exc:
        raise RuntimeError(f'Network error posting to {url}: {exc}') from exc


def push_sample_payloads(endpoint: str = "http://localhost:4318") -> None:
    traces_url = f"{endpoint.rstrip('/')}/v1/traces"
    metrics_url = f"{endpoint.rstrip('/')}/v1/metrics"
    logs_url = f"{endpoint.rstrip('/')}/v1/logs"

    _post_json(traces_url, _build_trace_payload())
    _post_json(metrics_url, _build_metric_payload())
    _post_json(logs_url, _build_log_payload())


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--endpoint", default="http://localhost:4318", help="OTLP HTTP endpoint exposed by the collector")
    args = parser.parse_args()
    push_sample_payloads(endpoint=args.endpoint)
    print(f"Telemetry payloads delivered to {args.endpoint}")


if __name__ == "__main__":
    main()
