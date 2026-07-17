#!/usr/bin/env bash

# 半导体产业研究助手本地服务管理。
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

info() { printf '[INFO] %s\n' "$1"; }
success() { printf '[OK] %s\n' "$1"; }
error() { printf '[ERROR] %s\n' "$1" >&2; }

check_docker() {
    if ! docker info >/dev/null 2>&1; then
        error "Docker 未运行，请先启动 Docker Desktop/Engine"
        exit 1
    fi
    docker compose version >/dev/null
}

start_core() {
    check_docker
    info "启动 PostgreSQL、Redis、etcd、MinIO 和 Milvus，并等待健康检查"
    docker compose up -d --wait --wait-timeout 240 postgres redis etcd minio milvus
    success "核心中间件已就绪"
}

start_app() {
    check_docker
    info "构建并启动完整应用；需要宿主机 Ollama 已提供 industry-qwen3:4b 和 bge-m3"
    docker compose --profile app up -d --build --wait --wait-timeout 600
    success "完整应用已就绪: http://localhost:5173，API: http://localhost:8000/docs"
}

start_observability() {
    check_docker
    info "启动 Prometheus"
    docker compose --profile observability up -d --wait --wait-timeout 120 prometheus
    success "Prometheus 已就绪: http://localhost:9090"
}

show_status() {
    docker compose --profile app --profile search --profile observability ps
}

show_logs() {
    if [[ $# -gt 0 ]]; then
        docker compose --profile app --profile search --profile observability logs -f --tail=100 "$@"
    else
        docker compose --profile app --profile search --profile observability logs -f --tail=100
    fi
}

clean_data() {
    printf '该操作会删除 PostgreSQL、Redis、Milvus、MinIO 和 Prometheus 数据卷。输入 yes 继续: '
    read -r confirm
    if [[ "$confirm" != "yes" ]]; then
        info "已取消"
        return
    fi
    docker compose --profile app --profile search --profile observability down --volumes
    success "数据卷已删除"
}

show_help() {
    cat <<'EOF'
用法: ./start-services.sh <command> [service]

  core          启动核心中间件并等待健康
  app           构建并启动中间件、后端和前端
  observability 启动可选 Prometheus
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
    stop) docker compose --profile app --profile search --profile observability down ;;
    status) show_status ;;
    logs) shift; show_logs "$@" ;;
    clean) clean_data ;;
    help|--help|-h) show_help ;;
    *) error "未知命令: $1"; show_help; exit 2 ;;
esac
