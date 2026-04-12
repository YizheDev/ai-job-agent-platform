#!/usr/bin/env bash
# ============================================================
# AI求职智能管家 - 数据备份脚本
# 用法: bash deploy/backup.sh
# 建议配合 crontab 定期执行
# ============================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
BACKUP_ROOT="$PROJECT_DIR/backups"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="$BACKUP_ROOT/$TIMESTAMP"
CONTAINER_NAME="ai-job-agent"

mkdir -p "$BACKUP_DIR"

echo "[INFO] 开始备份 ($TIMESTAMP)..."

# 精确匹配容器名（排除 ai-job-agent-nginx 等子串匹配）
if docker ps --format '{{.Names}}' | grep -qx "$CONTAINER_NAME"; then
    docker cp "$CONTAINER_NAME:/app/data" "$BACKUP_DIR/data"
    echo "[INFO] 应用数据已备份"
else
    echo "[WARN] 容器 $CONTAINER_NAME 未运行，跳过数据备份"
fi

if [ -f "$PROJECT_DIR/.env" ]; then
    cp "$PROJECT_DIR/.env" "$BACKUP_DIR/.env.backup"
    echo "[INFO] 配置文件已备份"
fi

# 保留最近 30 份备份
if [ -d "$BACKUP_ROOT" ]; then
    cd "$BACKUP_ROOT"
    # 安全删除：只处理日期格式命名的目录
    ls -dt [0-9]*/ 2>/dev/null | tail -n +31 | xargs -r rm -rf 2>/dev/null || true
fi

echo "[INFO] 备份完成: $BACKUP_DIR"
echo "[INFO] 当前备份数: $(ls -d "$BACKUP_ROOT"/[0-9]*/ 2>/dev/null | wc -l)"
