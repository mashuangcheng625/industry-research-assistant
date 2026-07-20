#!/usr/bin/env bash

# 半导体产业研究助手本地服务管理。
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

COMPOSE=(docker compose)
if [[ -f "$SCRIPT_DIR/backend/.env" ]]; then
    # Compose interpolation normally only reads a root .env. Reuse the backend
    # runtime configuration without copying secrets into docker-compose.yml.
    COMPOSE+=(--env-file "$SCRIPT_DIR/backend/.env")
fi

info() { printf '[INFO] %s\n' "$1"; }
success() { printf '[OK] %s\n' "$1"; }
error() { printf '[ERROR] %s\n' "$1" >&2; }

check_docker() {
    if ! docker info >/dev/null 2>&1; then
        error "Docker 未运行，请先启动 Docker Desktop/Engine"
        exit 1
    fi
    "${COMPOSE[@]}" version >/dev/null
}

start_core() {
    check_docker
    info "启动 PostgreSQL、Redis、etcd、MinIO 和 Milvus，并等待健康检查"
    "${COMPOSE[@]}" up -d --wait --wait-timeout 240 postgres redis etcd minio milvus
    success "核心中间件已就绪"
}

start_app() {
    check_docker
    info "构建并启动完整应用；生成与 Embedding 统一读取百炼 DASHSCOPE_API_KEY"
    "${COMPOSE[@]}" --profile app up -d --build --wait --wait-timeout 600
    success "完整应用已就绪: http://localhost:5173，API: http://localhost:8000/docs"
}

start_observability() {
    check_docker
    info "启动 Prometheus 和 Grafana"
    "${COMPOSE[@]}" --profile observability up -d --wait --wait-timeout 180 prometheus grafana
    success "Prometheus: http://localhost:9090，Grafana: http://localhost:3000"
}

show_status() {
    "${COMPOSE[@]}" --profile app --profile search --profile observability ps
}

show_logs() {
    if [[ $# -gt 0 ]]; then
        "${COMPOSE[@]}" --profile app --profile search --profile observability logs -f --tail=100 "$@"
    else
        "${COMPOSE[@]}" --profile app --profile search --profile observability logs -f --tail=100
    fi
}

clean_data() {
    printf '该操作会删除 PostgreSQL、Redis、Milvus、MinIO 和 Prometheus 数据卷。输入 yes 继续: '
    read -r confirm
    if [[ "$confirm" != "yes" ]]; then
        info "已取消"
        return
    fi
    "${COMPOSE[@]}" --profile app --profile search --profile observability down --volumes
    success "数据卷已删除"
}

show_help() {
    cat <<'EOF'
用法: ./start-services.sh <command> [service]

  core          启动核心中间件并等待健康
  app           构建并启动中间件、后端和前端
  observability 启动可选 Prometheus 和 Grafana
  stop          停止所有 profile 的容器，保留数据卷
  status        查看所有 profile 状态
  logs [name]   跟踪全部或指定服务日志
  clean         二次确认后删除容器和数据卷
EOF
}

case "${1:-help}" in
    core) start_core ;;
    app) start_app ;;
    observability) start_observability ;;
    stop) "${COMPOSE[@]}" --profile app --profile search --profile observability down ;;
    status) show_status ;;
    logs) shift; show_logs "$@" ;;
    clean) clean_data ;;
    help|--help|-h) show_help ;;
    *) error "未知命令: $1"; show_help; exit 2 ;;
esac
