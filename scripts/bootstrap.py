"""Bootstrap installer for OP-Observe and dependencies.

This script generates a Docker Compose deployment that bundles the
observability, security, and model-serving stack required by OP-Observe.
It can be invoked in a single command and is configurable via
environment variables.
"""
from __future__ import annotations

import argparse
import json
import os
import shlex
import shutil
import subprocess
from pathlib import Path
from textwrap import dedent
from typing import Dict, Iterable, List


DEFAULTS: Dict[str, str] = {
    "OPOBS_PROJECT_NAME": "opobserve",
    "OPOBS_NETWORK_NAME": "opobserve-net",
    "OPOBS_CONFIG_DIR": "./deploy",
    "OPOBS_DATA_DIR": "data",
    "OPOBS_LOGS_DIR": "logs",
    "OPOBS_COMPOSE_FILE": "docker-compose.yaml",
    "OPOBS_ENV_FILE": ".opobserve.env",
    "QDRANT_VERSION": "v1.7.4",
    "QDRANT_PORT": "6333",
    "VLLM_VERSION": "latest",
    "VLLM_PORT": "8000",
    "PHOENIX_VERSION": "latest",
    "PHOENIX_PORT": "6006",
    "PROMETHEUS_VERSION": "v2.52.0",
    "PROMETHEUS_PORT": "9090",
    "GRAFANA_VERSION": "10.4.2",
    "GRAFANA_PORT": "3000",
    "LOKI_VERSION": "2.9.3",
    "LOKI_PORT": "3100",
    "VAULT_VERSION": "1.15.5",
    "VAULT_PORT": "8200",
    "KEYCLOAK_VERSION": "24.0.3",
    "KEYCLOAK_PORT": "8080",
    "POSTGRES_VERSION": "16",
    "POSTGRES_PORT": "5432",
    "CLICKHOUSE_VERSION": "23.12",
    "CLICKHOUSE_PORT": "9000",
    "CLICKHOUSE_EXPORTER_VERSION": "0.0.3",
    "CLICKHOUSE_EXPORTER_PORT": "9116",
    "OTEL_COLLECTOR_VERSION": "0.97.0",
    "OTEL_COLLECTOR_PORT": "4317",
    "MINIO_VERSION": "latest",
    "MINIO_PORT": "9000",
    "NATS_VERSION": "2.10.9",
    "NATS_PORT": "4222",
    "AGENTIC_RADAR_VERSION": "latest",
    "TRULENS_VERSION": "latest",
    "OPENLLMETRY_IMAGE": "openllmetry/opentelemetry-collector",
}


def parse_args(argv: Iterable[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Bootstrap OP-Observe stack")
    parser.add_argument(
        "--config-dir",
        default=None,
        help="Directory where configuration and compose files will be written",
    )
    parser.add_argument(
        "--project-name",
        default=None,
        help="Docker Compose project name (defaults to OPOBS_PROJECT_NAME)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Generate configuration without starting services",
    )
    parser.add_argument(
        "--skip-start",
        action="store_true",
        help="Alias for --dry-run (deprecated)",
    )
    return parser.parse_args(argv)


def resolve_configuration(args: argparse.Namespace) -> Dict[str, str]:
    env: Dict[str, str] = {}
    for key, value in DEFAULTS.items():
        env[key] = os.getenv(key, value)

    if args.config_dir:
        env["OPOBS_CONFIG_DIR"] = args.config_dir
    if args.project_name:
        env["OPOBS_PROJECT_NAME"] = args.project_name

    config_path = Path(env["OPOBS_CONFIG_DIR"]).expanduser().resolve()
    env["OPOBS_CONFIG_DIR"] = str(config_path)
    env["OPOBS_DATA_DIR"] = str((config_path / env["OPOBS_DATA_DIR"]).resolve())
    env["OPOBS_LOGS_DIR"] = str((config_path / env["OPOBS_LOGS_DIR"]).resolve())

    return env


def ensure_directories(env: Dict[str, str]) -> None:
    Path(env["OPOBS_CONFIG_DIR"]).mkdir(parents=True, exist_ok=True)
    Path(env["OPOBS_DATA_DIR"]).mkdir(parents=True, exist_ok=True)
    Path(env["OPOBS_LOGS_DIR"]).mkdir(parents=True, exist_ok=True)


def ensure_support_files(env: Dict[str, str]) -> None:
    config_dir = Path(env["OPOBS_CONFIG_DIR"])

    otel_config = config_dir / "otel-collector.yaml"
    if not otel_config.exists():
        otel_config.write_text(
            dedent(
                """
                receivers:
                  otlp:
                    protocols:
                      grpc:
                      http:
                processors:
                  batch: {}
                exporters:
                  logging:
                    loglevel: info
                  prometheus:
                    endpoint: 0.0.0.0:8889
                service:
                  pipelines:
                    traces:
                      receivers: [otlp]
                      processors: [batch]
                      exporters: [logging]
                    metrics:
                      receivers: [otlp]
                      processors: [batch]
                      exporters: [prometheus]
                    logs:
                      receivers: [otlp]
                      processors: [batch]
                      exporters: [logging]
                """
            ).strip()
            + "\n",
        )

    prometheus_config = config_dir / "prometheus.yml"
    if not prometheus_config.exists():
        prometheus_config.write_text(
            dedent(
                """
                global:
                  scrape_interval: 15s
                scrape_configs:
                  - job_name: prometheus
                    static_configs:
                      - targets: ['prometheus:9090']
                  - job_name: opobserve-stack
                    static_configs:
                      - targets:
                          - 'clickhouse-exporter:9116'
                          - 'otel-collector:8889'
                """
            ).strip()
            + "\n",
        )

    loki_config = config_dir / "loki-config.yaml"
    if not loki_config.exists():
        loki_config.write_text(
            dedent(
                """
                auth_enabled: false
                server:
                  http_listen_port: 3100
                ingester:
                  lifecycler:
                    address: 127.0.0.1
                    ring:
                      kvstore:
                        store: inmemory
                      replication_factor: 1
                  chunk_idle_period: 5m
                  max_chunk_age: 1h
                  chunk_target_size: 1536000
                schema_config:
                  configs:
                    - from: 2020-10-24
                      store: boltdb
                      object_store: filesystem
                      schema: v11
                      index:
                        prefix: index_
                        period: 24h
                storage_config:
                  boltdb:
                    directory: /loki/index
                  filesystem:
                    directory: /loki/chunks
                limits_config:
                  enforce_metric_name: false
                  reject_old_samples: true
                  reject_old_samples_max_age: 168h
                chunk_store_config:
                  max_look_back_period: 0s
                table_manager:
                  retention_deletes_enabled: true
                  retention_period: 24h
                ruler:
                  storage:
                    type: local
                    local:
                      directory: /tmp/rules
                  rule_path: /tmp/rules
                  ring:
                    kvstore:
                      store: inmemory
                  alertmanager_url: http://alertmanager:9093
                """
            ).strip()
            + "\n",
        )


def parse_compose_command() -> List[str]:
    compose_cmd = os.getenv("OPOBS_COMPOSE_CMD", "docker compose")
    return shlex.split(compose_cmd)


def ensure_dependencies(compose_cmd: List[str]) -> None:
    docker_path = shutil.which("docker")
    if not docker_path:
        raise RuntimeError("docker executable not found in PATH")

    first = compose_cmd[0]
    if first != "docker" and shutil.which(first) is None:
        raise RuntimeError(f"Compose command '{first}' not found in PATH")


def build_service(name: str, image: str, ports: List[str] | None = None, **extra: Dict) -> Dict:
    service: Dict = {"image": image, "restart": "unless-stopped"}
    if ports:
        service["ports"] = ports
    for key, value in extra.items():
        service[key] = value
    return service


def build_compose_config(env: Dict[str, str]) -> Dict:
    data_dir = env["OPOBS_DATA_DIR"]
    logs_dir = env["OPOBS_LOGS_DIR"]
    network_name = env["OPOBS_NETWORK_NAME"]

    services: Dict[str, Dict] = {}

    services["qdrant"] = build_service(
        "qdrant",
        f"qdrant/qdrant:{env['QDRANT_VERSION']}",
        ports=[f"{env['QDRANT_PORT']}:6333"],
        volumes=[f"{data_dir}/qdrant:/qdrant/storage"],
    )

    services["vllm"] = build_service(
        "vllm",
        f"vllm/vllm-openai:{env['VLLM_VERSION']}",
        ports=[f"{env['VLLM_PORT']}:8000"],
        environment={
            "VLLM_MODEL": os.getenv("VLLM_MODEL", "meta-llama/Llama-2-7b-chat-hf"),
            "VLLM_WORKER_CONCURRENCY": os.getenv("VLLM_WORKER_CONCURRENCY", "2"),
        },
        volumes=[f"{data_dir}/vllm:/data"],
    )

    services["otel-collector"] = build_service(
        "otel-collector",
        f"{env['OPENLLMETRY_IMAGE']}:{env['OTEL_COLLECTOR_VERSION']}",
        ports=[f"{env['OTEL_COLLECTOR_PORT']}:4317"],
        volumes=[f"{env['OPOBS_CONFIG_DIR']}/otel-collector.yaml:/etc/otel/config.yaml"],
        command=["--config", "/etc/otel/config.yaml"],
    )

    services["phoenix"] = build_service(
        "phoenix",
        f"arizeai/phoenix:{env['PHOENIX_VERSION']}",
        ports=[f"{env['PHOENIX_PORT']}:6006"],
        environment={
            "PHOENIX_DATABASE__URL": "postgresql://phoenix:phoenix@phoenix-db:5432/phoenix",
        },
        depends_on=["phoenix-db"],
    )

    services["phoenix-db"] = build_service(
        "phoenix-db",
        f"postgres:{env['POSTGRES_VERSION']}",
        environment={
            "POSTGRES_DB": "phoenix",
            "POSTGRES_USER": "phoenix",
            "POSTGRES_PASSWORD": "phoenix",
        },
        volumes=[f"{data_dir}/postgres:/var/lib/postgresql/data"],
    )

    services["prometheus"] = build_service(
        "prometheus",
        f"prom/prometheus:{env['PROMETHEUS_VERSION']}",
        ports=[f"{env['PROMETHEUS_PORT']}:9090"],
        volumes=[
            f"{env['OPOBS_CONFIG_DIR']}/prometheus.yml:/etc/prometheus/prometheus.yml",
            f"{data_dir}/prometheus:/prometheus",
        ],
    )

    services["grafana"] = build_service(
        "grafana",
        f"grafana/grafana:{env['GRAFANA_VERSION']}",
        ports=[f"{env['GRAFANA_PORT']}:3000"],
        volumes=[f"{data_dir}/grafana:/var/lib/grafana"],
    )

    services["loki"] = build_service(
        "loki",
        f"grafana/loki:{env['LOKI_VERSION']}",
        ports=[f"{env['LOKI_PORT']}:3100"],
        command=["-config.file=/etc/loki/local-config.yaml"],
        volumes=[f"{env['OPOBS_CONFIG_DIR']}/loki-config.yaml:/etc/loki/local-config.yaml"],
    )

    services["vault"] = build_service(
        "vault",
        f"hashicorp/vault:{env['VAULT_VERSION']}",
        ports=[f"{env['VAULT_PORT']}:8200"],
        cap_add=["IPC_LOCK"],
        environment={
            "VAULT_DEV_ROOT_TOKEN_ID": os.getenv("VAULT_DEV_ROOT_TOKEN_ID", "root"),
            "VAULT_DEV_LISTEN_ADDRESS": "0.0.0.0:8200",
        },
    )

    services["keycloak"] = build_service(
        "keycloak",
        f"quay.io/keycloak/keycloak:{env['KEYCLOAK_VERSION']}",
        ports=[f"{env['KEYCLOAK_PORT']}:8080"],
        environment={
            "KEYCLOAK_ADMIN": os.getenv("KEYCLOAK_ADMIN", "admin"),
            "KEYCLOAK_ADMIN_PASSWORD": os.getenv("KEYCLOAK_ADMIN_PASSWORD", "admin"),
        },
        command=["start-dev"],
    )

    services["clickhouse"] = build_service(
        "clickhouse",
        f"clickhouse/clickhouse-server:{env['CLICKHOUSE_VERSION']}",
        ports=[f"{env['CLICKHOUSE_PORT']}:9000"],
        volumes=[f"{data_dir}/clickhouse:/var/lib/clickhouse"],
    )

    services["clickhouse-exporter"] = build_service(
        "clickhouse-exporter",
        f"bitnami/clickhouse-exporter:{env['CLICKHOUSE_EXPORTER_VERSION']}",
        ports=[f"{env['CLICKHOUSE_EXPORTER_PORT']}:9116"],
        environment={
            "CLICKHOUSE_URL": "tcp://clickhouse:9000",
        },
        depends_on=["clickhouse"],
    )

    services["minio"] = build_service(
        "minio",
        f"minio/minio:{env['MINIO_VERSION']}",
        ports=[f"{env['MINIO_PORT']}:9000"],
        command=["server", "/data"],
        environment={
            "MINIO_ROOT_USER": os.getenv("MINIO_ROOT_USER", "minio"),
            "MINIO_ROOT_PASSWORD": os.getenv("MINIO_ROOT_PASSWORD", "minio123"),
        },
        volumes=[f"{data_dir}/minio:/data"],
    )

    services["nats"] = build_service(
        "nats",
        f"nats:{env['NATS_VERSION']}",
        ports=[f"{env['NATS_PORT']}:4222"],
    )

    services["agentic-radar"] = build_service(
        "agentic-radar",
        f"ghcr.io/opobserve/agentic-radar:{env['AGENTIC_RADAR_VERSION']}",
        environment={
            "RADAR_OUTPUT_DIR": "/evidence",
        },
        volumes=[f"{data_dir}/radar:/evidence"],
    )

    services["trulens-evaluator"] = build_service(
        "trulens-evaluator",
        f"ghcr.io/opobserve/trulens-runner:{env['TRULENS_VERSION']}",
        environment={
            "TRULENS_STORAGE": "postgresql://phoenix:phoenix@phoenix-db:5432/phoenix",
        },
        depends_on=["phoenix", "phoenix-db"],
    )

    volumes = {
        "qdrant-data": {"driver": "local"},
    }

    networks = {network_name: {"driver": "bridge"}}

    for service in services.values():
        service.setdefault("networks", [network_name])

    return {
        "version": "3.9",
        "services": services,
        "volumes": volumes,
        "networks": networks,
    }


def write_compose_file(env: Dict[str, str], compose_config: Dict) -> Path:
    compose_path = Path(env["OPOBS_CONFIG_DIR"]) / env["OPOBS_COMPOSE_FILE"]
    compose_path.write_text(json.dumps(compose_config, indent=2))
    return compose_path


def write_env_file(env: Dict[str, str]) -> Path:
    env_path = Path(env["OPOBS_CONFIG_DIR"]) / env["OPOBS_ENV_FILE"]
    lines = [f"{key}={value}" for key, value in sorted(env.items())]
    env_path.write_text("\n".join(lines) + "\n")
    return env_path


def launch_stack(compose_cmd: List[str], project: str, compose_file: Path, env: Dict[str, str]) -> None:
    cmd = compose_cmd + ["-p", project, "-f", str(compose_file), "up", "-d"]
    subprocess.run(cmd, check=True, env={**os.environ, **env})


def main(argv: Iterable[str] | None = None) -> int:
    args = parse_args(argv)
    if args.skip_start:
        args.dry_run = True

    env = resolve_configuration(args)
    ensure_directories(env)
    ensure_support_files(env)

    compose_cmd = parse_compose_command()
    ensure_dependencies(compose_cmd)

    compose_config = build_compose_config(env)
    compose_file = write_compose_file(env, compose_config)
    write_env_file(env)

    if not args.dry_run:
        launch_stack(
            compose_cmd,
            env["OPOBS_PROJECT_NAME"],
            compose_file,
            env,
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
