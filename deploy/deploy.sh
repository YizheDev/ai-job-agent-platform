#!/usr/bin/env bash
# ============================================================
# AI求职智能管家 - 一键部署脚本
# 用法: bash deploy/deploy.sh
# ============================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_DIR"

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

info()  { echo -e "${GREEN}[INFO]${NC} $1"; }
warn()  { echo -e "${YELLOW}[WARN]${NC} $1"; }
error() { echo -e "${RED}[ERROR]${NC} $1"; exit 1; }

# ===== 0. 修复 Windows CRLF 行尾 =====
if command -v dos2unix &> /dev/null; then
    find deploy/ -name "*.sh" -exec dos2unix -q {} \; 2>/dev/null || true
fi

# ===== 1. 环境检查 =====
info "检查系统环境..."

if ! command -v docker &> /dev/null; then
    error "未安装 Docker，请先安装: https://docs.docker.com/engine/install/"
fi

if ! docker compose version &> /dev/null; then
    error "未安装 Docker Compose V2，请升级 Docker"
fi

info "Docker 版本: $(docker --version)"
info "Compose 版本: $(docker compose version --short)"

# ===== 2. 配置文件检查 =====
if [ ! -f ".env" ]; then
    warn ".env 文件不存在，正在从模板创建..."
    cp .env.example .env
    echo ""
    error "请编辑 .env 文件填写实际配置 (尤其是 LLM_API_KEY)，然后重新运行此脚本"
fi

if grep -q "your_api_key_here" .env 2>/dev/null; then
    error ".env 中 LLM_API_KEY 尚未配置，请填写实际 API Key 后重新运行"
fi

if grep -q "^LLM_API_KEY=$" .env 2>/dev/null; then
    error ".env 中 LLM_API_KEY 为空，请填写实际 API Key 后重新运行"
fi

# ===== 3. 端口检查 =====
if ss -tlnp 2>/dev/null | grep -q ":80 " || netstat -tlnp 2>/dev/null | grep -q ":80 "; then
    warn "端口 80 已被占用，Nginx 可能启动失败"
    warn "请先释放端口 80 或修改 docker-compose.yml 中的端口映射"
fi

# ===== 4. SSL 证书检查 =====
if [ -f "deploy/nginx/ssl/fullchain.pem" ] && [ -f "deploy/nginx/ssl/privkey.pem" ]; then
    info "检测到 SSL 证书文件"
    warn "注意: 需手动编辑 deploy/nginx/conf.d/app.conf 启用 HTTPS 配置段"
else
    info "未检测到 SSL 证书，将以 HTTP 模式运行"
fi

# ===== 5. 构建并启动 =====
info "开始构建镜像 (首次约需 5-10 分钟)..."
if ! docker compose build; then
    error "镜像构建失败，请检查上方错误信息"
fi

info "启动服务..."
docker compose up -d

# ===== 6. 等待健康检查 =====
info "等待服务启动 (最长等待 90 秒)..."
MAX_WAIT=90
WAITED=0
HEALTHY=false
while [ $WAITED -lt $MAX_WAIT ]; do
    STATUS=$(docker inspect --format='{{.State.Health.Status}}' ai-job-agent 2>/dev/null || echo "unknown")
    if [ "$STATUS" = "healthy" ]; then
        HEALTHY=true
        break
    elif [ "$STATUS" = "unhealthy" ]; then
        warn "容器报告不健康状态"
        break
    fi
    sleep 5
    WAITED=$((WAITED + 5))
    echo -n "."
done
echo ""

# ===== 7. 输出状态 =====
echo ""
echo "============================================================"
docker compose ps
echo "============================================================"
echo ""

if [ "$HEALTHY" = true ]; then
    info "部署成功! 服务已就绪"
else
    warn "服务可能仍在启动中，请稍后检查"
    warn "查看日志: docker compose logs -f app"
fi

# 获取服务器 IP
SERVER_IP=$(hostname -I 2>/dev/null | awk '{print $1}' || echo "服务器IP")
echo ""
info "访问地址: http://${SERVER_IP}:80"
info "查看日志: docker compose logs -f app"
info "停止服务: docker compose down"
info "重启服务: docker compose restart"
echo "============================================================"
