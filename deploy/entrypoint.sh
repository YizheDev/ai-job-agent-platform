#!/usr/bin/env bash
# ============================================================
# 容器启动入口：确保数据目录可写后启动应用
# ============================================================

set -e

# 测试数据目录写权限，如果不可写则尝试修复（需要以 root 启动时才有效）
for dir in /app/data /app/logs; do
    if [ ! -w "$dir" ]; then
        echo "[entrypoint] 目录 $dir 不可写，尝试修复权限..."
        # 如果当前是 root，直接修复
        if [ "$(id -u)" = "0" ]; then
            chown -R pwuser:pwuser "$dir"
        else
            echo "[entrypoint] 警告: 非 root 用户无法修复 $dir 权限，请手动执行:"
            echo "  docker exec -u root ai-job-agent chown -R pwuser:pwuser $dir"
        fi
    fi
done

exec python main.py
