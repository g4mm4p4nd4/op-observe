#!/usr/bin/env bash
# OP-Observe bootstrap installer
set -euo pipefail

PROGRAM_NAME="op-observe-bootstrap"
VERSION="0.1.0"

usage() {
  cat <<'USAGE'
Usage: bootstrap.sh [--prefix DIR] [--force]

Options:
  --prefix DIR   Install stack into DIR (default: ./opobserve-stack)
  --force        Re-install binaries even if they already exist
  -h, --help     Show this help message

Environment variables:
  OP_OBSERVE_SKIP_DOWNLOADS=1  Skip remote downloads and create stub binaries.
  OP_OBSERVE_PREFIX             Alternative way to set installation prefix.
USAGE
}

log() {
  printf '%s\n' "[${PROGRAM_NAME}] $*"
}

warn() {
  printf '%s\n' "[${PROGRAM_NAME}][WARN] $*" >&2
}

error() {
  printf '%s\n' "[${PROGRAM_NAME}][ERROR] $*" >&2
  exit 1
}

json_escape() {
  # Minimal JSON string escaper (handles backslash, quotes, newline, tab)
  local input="$1"
  input=${input//\\/\\\\}
  input=${input//\"/\\\"}
  input=${input//$'\n'/\\n}
  input=${input//$'\t'/\\t}
  printf '%s' "$input"
}

find_downloader() {
  if command -v curl >/dev/null 2>&1; then
    printf 'curl'
    return 0
  fi
  if command -v wget >/dev/null 2>&1; then
    printf 'wget'
    return 0
  fi
  printf ''
  return 1
}

try_download() {
  # try_download URL DEST
  local url="$1"
  local dest="$2"
  if [ "${OP_OBSERVE_SKIP_DOWNLOADS:-}" = "1" ]; then
    return 1
  fi
  local downloader
  downloader=$(find_downloader) || return 1
  if [ "$downloader" = "curl" ]; then
    if curl -fsSL "$url" -o "$dest"; then
      return 0
    fi
  else
    if wget -qO "$dest" "$url"; then
      return 0
    fi
  fi
  return 1
}

create_stub_binary() {
  # create_stub_binary NAME DEST MESSAGE
  local name="$1"
  local dest="$2"
  local message="$3"
  cat >"$dest" <<'EOF'
#!/usr/bin/env bash
cat <<'MSG'
${message}
MSG
exit 1
EOF
  chmod +x "$dest"
}

install_osv_scanner() {
  local name="osv-scanner"
  local version="1.7.3"
  local binary_path="${BIN_DIR}/${name}"
  if [ -f "$binary_path" ] && [ "$FORCE" -eq 0 ]; then
    log "${name} already installed"
    add_manifest "$name" "binary" "present" "path" "$binary_path"
    return
  fi
  local os="${PLATFORM_OS}"
  local arch="${PLATFORM_ARCH}"
  local archive="${TMPDIR}/${name}.tar.gz"
  local url="https://github.com/google/osv-scanner/releases/download/v${version}/${name}_${version}_${os}_${arch}.tar.gz"
  if try_download "$url" "$archive"; then
    log "Downloaded ${name} ${version}"
    tar -xf "$archive" -C "$TMPDIR"
    local extracted="$TMPDIR/${name}"
    if [ ! -f "$extracted" ]; then
      extracted=$(find "$TMPDIR" -maxdepth 2 -type f -name "$name" | head -n 1)
    fi
    if [ -f "$extracted" ]; then
      mv "$extracted" "$binary_path"
      chmod +x "$binary_path"
      log "Installed ${name} to ${binary_path}"
      add_manifest "$name" "binary" "installed" "path" "$binary_path"
      return
    fi
  fi
  warn "Falling back to stub ${name} binary"
  create_stub_binary "$name" "$binary_path" "${name} stub created. Enable downloads to install the real binary."
  add_manifest "$name" "binary" "stubbed" "path" "$binary_path"
}

install_radar_cli() {
  local name="agentic-radar"
  local binary_path="${BIN_DIR}/${name}"
  if [ -f "$binary_path" ] && [ "$FORCE" -eq 0 ]; then
    log "${name} CLI already present"
    add_manifest "radar" "cli" "present" "path" "$binary_path"
    return
  fi
  cat >"$binary_path" <<'EOF'
#!/usr/bin/env bash
SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
STACK_ROOT=$(cd "${SCRIPT_DIR}/.." && pwd)
COMPOSE_FILE="${STACK_ROOT}/docker-compose.yml"
if command -v docker >/dev/null 2>&1; then
  if command -v docker-compose >/dev/null 2>&1; then
    docker-compose -f "${COMPOSE_FILE}" run --rm radar "$@"
    exit $?
  elif docker compose version >/dev/null 2>&1; then
    docker compose -f "${COMPOSE_FILE}" run --rm radar "$@"
    exit $?
  fi
fi
cat <<'MSG'
agentic-radar CLI stub. Docker (with compose) is required to run the Radar container.
MSG
exit 1
EOF
  chmod +x "$binary_path"
  add_manifest "radar" "cli" "stubbed" "path" "$binary_path"
}

install_pip_audit() {
  local name="pip-audit"
  local binary_path="${BIN_DIR}/${name}"
  if [ -f "$binary_path" ] && [ "$FORCE" -eq 0 ]; then
    log "pip-audit already installed"
    add_manifest "$name" "python-tool" "present" "path" "$binary_path"
    return
  fi
  local venv_dir="${PREFIX}/.venv"
  mkdir -p "$venv_dir"
  local failed=0
  if [ "${OP_OBSERVE_SKIP_DOWNLOADS:-}" != "1" ] && command -v python3 >/dev/null 2>&1; then
    if python3 -m venv "$venv_dir" >/dev/null 2>&1; then
      # shellcheck disable=SC1090
      . "${venv_dir}/bin/activate"
      if pip install --quiet pip-audit >/dev/null 2>&1; then
        cat >"$binary_path" <<EOF
#!/usr/bin/env bash
VENV_DIR="${venv_dir}"
# shellcheck disable=SC1090
. "${venv_dir}/bin/activate"
"${venv_dir}/bin/pip-audit" "$@"
EOF
        chmod +x "$binary_path"
        deactivate >/dev/null 2>&1 || true
        add_manifest "$name" "python-tool" "installed" "path" "$binary_path"
        return
      else
        failed=1
      fi
    else
      failed=1
    fi
  else
    failed=1
  fi
  if [ "$failed" -eq 1 ]; then
    warn "Unable to install pip-audit via pip; creating stub wrapper"
    create_stub_binary "$name" "$binary_path" "pip-audit stub created. Enable downloads to install into virtualenv."
    add_manifest "$name" "python-tool" "stubbed" "path" "$binary_path"
  fi
}

write_radar_config() {
  local path="${CONFIG_DIR}/radar/config.yaml"
  if [ ! -f "$path" ]; then
    cat >"$path" <<'EOF'
telemetry:
  otlp_endpoint: http://otel-collector:4317
  service_name: op-observe-radar
scan:
  source_paths:
    - ./apps
  output:
    html: /evidence/radar-report.html
    json: /evidence/radar-report.json
  policies:
    owasp_mapping: enabled
EOF
  fi
}

write_otel_config() {
  local dir="${CONFIG_DIR}/opentelemetry"
  mkdir -p "$dir"
  cat >"${dir}/collector.yaml" <<'EOF'
receivers:
  otlp:
    protocols:
      grpc:
      http:
processors:
  batch:
exporters:
  clickhouse:
    endpoint: tcp://clickhouse:9000/
    database: otel
    ttl: 72h
    logs_table_name: otel_logs
    traces_table_name: otel_traces
    metrics_table_name: otel_metrics
  logging:
    loglevel: info
service:
  pipelines:
    traces:
      receivers: [otlp]
      processors: [batch]
      exporters: [clickhouse, logging]
    metrics:
      receivers: [otlp]
      processors: [batch]
      exporters: [clickhouse, logging]
    logs:
      receivers: [otlp]
      processors: [batch]
      exporters: [clickhouse, logging]
EOF
  cat >"${dir}/README.md" <<'EOF'
# OpenLLMetry Collector Configuration

This OpenTelemetry collector configuration enables the OpenLLMetry pipelines.
All services should export OTLP traces/metrics/logs to `otel-collector:4317`.
The collector forwards data to ClickHouse while retaining a logging exporter
for local debugging.
EOF
}

write_clickhouse_config() {
  local dir="${CONFIG_DIR}/clickhouse"
  mkdir -p "$dir"
  cat >"${dir}/config.xml" <<'EOF'
<clickhouse>
  <logger>
    <level>warning</level>
  </logger>
  <opentelemetry>
    <expose_metrics>true</expose_metrics>
  </opentelemetry>
</clickhouse>
EOF
}

write_grafana_config() {
  local gdir="${CONFIG_DIR}/grafana"
  mkdir -p "$gdir/provisioning/dashboards"
  mkdir -p "$gdir/dashboards"
  cat >"$gdir/grafana.env" <<'EOF'
GF_SECURITY_ADMIN_USER=admin
GF_SECURITY_ADMIN_PASSWORD=admin
EOF
  cat >"$gdir/provisioning/dashboards/opobserve.yaml" <<'EOF'
apiVersion: 1
providers:
  - name: 'opobserve-dashboards'
    orgId: 1
    folder: 'OP-Observe'
    type: file
    disableDeletion: false
    updateIntervalSeconds: 30
    options:
      path: /var/lib/grafana/dashboards
EOF
  cat >"$gdir/dashboards/opobserve.json" <<'EOF'
{
  "annotations": {
    "list": []
  },
  "title": "OP-Observe Overview",
  "uid": "opobserve-overview",
  "version": 1,
  "panels": [
    {
      "type": "timeseries",
      "title": "Guardrail Verdicts",
      "targets": [
        {
          "expr": "sum(rate(radar_guardrail_failures_total[5m])) by (severity)",
          "refId": "A"
        }
      ]
    },
    {
      "type": "stat",
      "title": "LLM Critic Score",
      "targets": [
        {
          "expr": "avg(openllmetry_critic_score)",
          "refId": "B"
        }
      ]
    }
  ]
}
EOF
}

write_vault_config() {
  local dir="${CONFIG_DIR}/vault"
  mkdir -p "$dir"
  cat >"$dir/config.hcl" <<'EOF'
ui = true
default_lease_ttl = "168h"
max_lease_ttl = "720h"
listener "tcp" {
  address = "0.0.0.0:8200"
  tls_disable = 1
}
storage "file" {
  path = "/vault/data"
}
EOF
}

write_keycloak_config() {
  local dir="${CONFIG_DIR}/keycloak"
  mkdir -p "$dir"
  cat >"$dir/realm-export.json" <<'EOF'
{
  "realm": "opobserve",
  "enabled": true,
  "users": [
    {
      "username": "admin",
      "enabled": true,
      "emailVerified": true,
      "credentials": [
        {
          "type": "password",
          "value": "ChangeMe!",
          "temporary": false
        }
      ]
    }
  ],
  "clients": [
    {
      "clientId": "opobserve-ui",
      "directAccessGrantsEnabled": true,
      "publicClient": true,
      "redirectUris": [
        "*"
      ]
    }
  ]
}
EOF
}

write_docker_compose() {
  local path="${PREFIX}/docker-compose.yml"
  cat >"$path" <<'EOF'
version: "3.9"
services:
  radar:
    image: ghcr.io/op-observe/agentic-radar:latest
    restart: unless-stopped
    volumes:
      - ./config/radar:/app/config:ro
      - ./evidence:/evidence
    environment:
      RADAR_CONFIG=/app/config/config.yaml
      RADAR_OTLP_ENDPOINT=http://otel-collector:4317
    depends_on:
      - otel-collector
  otel-collector:
    image: otel/opentelemetry-collector-contrib:0.97.0
    command: ["--config=/etc/otelcol/config.yaml"]
    volumes:
      - ./config/opentelemetry/collector.yaml:/etc/otelcol/config.yaml:ro
    depends_on:
      - clickhouse
  phoenix:
    image: arizephoenix/phoenix:latest
    restart: unless-stopped
    ports:
      - "6006:6006"
    environment:
      PHOENIX_SQL_DATABASE__URI=sqlite:////phoenix/data/phoenix.sqlite
    volumes:
      - ./data/phoenix:/phoenix/data
  clickhouse:
    image: clickhouse/clickhouse-server:23.8
    restart: unless-stopped
    ports:
      - "8123:8123"
      - "9000:9000"
    volumes:
      - ./data/clickhouse:/var/lib/clickhouse
      - ./config/clickhouse/config.xml:/etc/clickhouse-server/config.d/opobserve.xml:ro
  grafana:
    image: grafana/grafana:10.4.2
    restart: unless-stopped
    ports:
      - "3000:3000"
    env_file:
      - ./config/grafana/grafana.env
    volumes:
      - ./config/grafana/provisioning:/etc/grafana/provisioning:ro
      - ./config/grafana/dashboards:/var/lib/grafana/dashboards:ro
    depends_on:
      - clickhouse
      - otel-collector
  qdrant:
    image: qdrant/qdrant:v1.8.4
    restart: unless-stopped
    ports:
      - "6333:6333"
    volumes:
      - ./data/qdrant:/qdrant/storage
  vllm:
    image: vllm/vllm-openai:latest
    restart: unless-stopped
    ports:
      - "8000:8000"
    environment:
      MODEL_NAME=facebook/opt-125m
    volumes:
      - ./data/vllm:/root/.cache/huggingface
  vault:
    image: hashicorp/vault:1.15
    restart: unless-stopped
    cap_add:
      - IPC_LOCK
    environment:
      VAULT_DEV_ROOT_TOKEN_ID=root
      VAULT_DEV_LISTEN_ADDRESS=0.0.0.0:8200
    ports:
      - "8200:8200"
    volumes:
      - ./config/vault:/vault/config:ro
      - ./data/vault:/vault/data
  keycloak:
    image: quay.io/keycloak/keycloak:24.0
    command:
      - start-dev
      - --import-realm
    restart: unless-stopped
    environment:
      KEYCLOAK_ADMIN=admin
      KEYCLOAK_ADMIN_PASSWORD=admin
    volumes:
      - ./config/keycloak:/opt/keycloak/data/import:ro
    ports:
      - "8080:8080"
EOF
}

ensure_directories() {
  mkdir -p "$BIN_DIR" "$CONFIG_DIR" "$PREFIX/data" "$PREFIX/evidence"
  mkdir -p "$CONFIG_DIR/radar"
}

add_manifest() {
  local component="$1"
  local type="$2"
  local status="$3"
  local extra_key="$4"
  local extra_value="$5"
  local escaped_value
  escaped_value=$(json_escape "$extra_value")
  local entry
  entry=$(printf '"%s":{"type":"%s","status":"%s","%s":"%s"}' "$component" "$type" "$status" "$extra_key" "$escaped_value")
  if [ -z "$MANIFEST_COMPONENTS" ]; then
    MANIFEST_COMPONENTS="$entry"
  else
    MANIFEST_COMPONENTS="$MANIFEST_COMPONENTS,$entry"
  fi
}

write_manifest() {
  local path="${PREFIX}/install-manifest.json"
  local escaped_prefix
  escaped_prefix=$(json_escape "$PREFIX")
  local escaped_platform
  escaped_platform=$(json_escape "${PLATFORM_OS}-${PLATFORM_ARCH}")
  cat >"$path" <<EOF
{
  "name": "${PROGRAM_NAME}",
  "version": "${VERSION}",
  "install_root": "${escaped_prefix}",
  "platform": "${escaped_platform}",
  "generated_at": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "components": {${MANIFEST_COMPONENTS}}
}
EOF
}

check_prerequisites() {
  if ! command -v bash >/dev/null 2>&1; then
    error "bash is required to run this installer"
  fi
  if ! command -v uname >/dev/null 2>&1; then
    error "uname command missing"
  fi
}

parse_platform() {
  local os
  os=$(uname -s)
  case "$os" in
    Linux) PLATFORM_OS="linux" ;;
    Darwin) PLATFORM_OS="darwin" ;;
    *) warn "Unsupported OS $os, defaulting to linux"; PLATFORM_OS="linux" ;;
  esac
  local arch
  arch=$(uname -m)
  case "$arch" in
    x86_64|amd64) PLATFORM_ARCH="amd64" ;;
    arm64|aarch64) PLATFORM_ARCH="arm64" ;;
    *) warn "Unsupported architecture $arch, defaulting to amd64"; PLATFORM_ARCH="amd64" ;;
  esac
}

print_summary() {
  log "Bootstrap complete. Files created under ${PREFIX}."
  log "Next steps:"
  log "  1. Review docker-compose.yml and adjust exposed ports as needed."
  log "  2. Run 'docker compose up -d' (or docker-compose) from ${PREFIX}."
  log "  3. Access Grafana on http://localhost:3000 (admin/admin)."
}

main() {
  PREFIX="${OP_OBSERVE_PREFIX:-${PWD}/opobserve-stack}"
  FORCE=0
  MANIFEST_COMPONENTS=""
  TMPDIR=$(mktemp -d)
  trap 'rm -rf "$TMPDIR"' EXIT

  while [ $# -gt 0 ]; do
    case "$1" in
      --prefix)
        if [ $# -lt 2 ]; then
          error "--prefix requires a directory argument"
        fi
        PREFIX="$2"
        shift 2
        ;;
      --force)
        FORCE=1
        shift
        ;;
      -h|--help)
        usage
        exit 0
        ;;
      *)
        error "Unknown option: $1"
        ;;
    esac
  done

  BIN_DIR="${PREFIX}/bin"
  CONFIG_DIR="${PREFIX}/config"

  check_prerequisites
  parse_platform
  ensure_directories

  write_radar_config
  write_otel_config
  write_clickhouse_config
  write_grafana_config
  write_vault_config
  write_keycloak_config
  write_docker_compose

  install_radar_cli
  install_osv_scanner
  install_pip_audit

  add_manifest "openllmetry" "config" "configured" "path" "${CONFIG_DIR}/opentelemetry/collector.yaml"
  add_manifest "phoenix" "container" "configured" "service" "phoenix"
  add_manifest "clickhouse-exporter" "container" "configured" "service" "otel-collector"
  add_manifest "grafana" "container" "configured" "service" "grafana"
  add_manifest "qdrant" "container" "configured" "service" "qdrant"
  add_manifest "vllm" "container" "configured" "service" "vllm"
  add_manifest "vault" "container" "configured" "service" "vault"
  add_manifest "keycloak" "container" "configured" "service" "keycloak"

  write_manifest
  print_summary
}

main "$@"
