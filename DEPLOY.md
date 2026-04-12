# AI求职智能管家 — 生产部署指南

## 目录

- [系统架构](#系统架构)
- [服务器要求](#服务器要求)
- [快速部署（5 步完成）](#快速部署5-步完成)
- [详细部署流程](#详细部署流程)
- [Docker 环境行为说明](#docker-环境行为说明)
- [HTTPS 配置](#https-配置)
- [运维操作](#运维操作)
- [数据备份与恢复](#数据备份与恢复)
- [常见问题](#常见问题)

---

## 系统架构

```
┌─────────────────────────────────────────────────────┐
│                   Docker 容器集群                      │
│                                                     │
│  ┌──────────────────────────────────────────────┐   │
│  │  ai-job-agent (应用容器)                       │   │
│  │                                              │   │
│  │  Gradio UI  ←→  LangGraph 工作流编排           │   │
│  │       ↕              ↕                        │   │
│  │  DrissionPage  /  Playwright (Chromium)       │   │
│  │  (BOSS直聘主方案)   (Docker无头备用方案)          │   │
│  │       ↕              ↕                        │   │
│  │  SQLite (data/job_agent.db)                   │   │
│  │  Cookie 加密存储 / 简历文件                      │   │
│  └──────────────────────────────────────────────┘   │
│       ↕ port 7860                                   │
│  ┌──────────────────────────────────────────────┐   │
│  │  ai-job-agent-nginx (反向代理)                  │   │
│  │  HTTP :80 / HTTPS :443 → app:7860             │   │
│  └──────────────────────────────────────────────┘   │
│       ↕ port 80/443                                 │
└─────────────────────────────────────────────────────┘
              ↕ 公网访问
```

### 核心技术栈

| 组件 | 技术 | 说明 |
|------|------|------|
| Web UI | Gradio 5.6+ | 8 个功能页面 + 用户登录 + 会话管理 |
| AI 编排 | LangGraph + LangChain | 简历解析→JD匹配→简历优化→风控→投递 |
| 浏览器自动化 | DrissionPage (主) + Playwright (备) | BOSS直聘自动搜索/沟通，含熔断降级 |
| LLM 推理 | OpenAI 兼容 API | 远程调用，支持 GPT-4 / DeepSeek 等 |
| 数据库 | SQLite (WAL 模式) | 简历、投递记录、JD 匹配、系统配置 |
| 安全 | Fernet 加密 | Cookie 加密存储，.env 原子写入 |
| 薪资解码 | fonttools | 解码 BOSS 直聘自定义 PUA 字体 |

### 功能模块

| 页面 | 功能 |
|------|------|
| 工作台 | 快捷操作入口 + 状态总览 |
| 简历管理 | PDF/DOCX 上传、AI 解析为结构化数据 |
| JD 匹配 | 简历与职位描述智能匹配评分 |
| 简历优化 | AI 针对目标 JD 优化简历 |
| BOSS 账号 | 连接 BOSS 直聘、登录状态管理、打招呼语/黑名单设置 |
| 自动投递 | 岗位搜索（城市/关键词/HR活跃度）、单个/批量沟通投递 |
| 投递记录 | 投递历史、状态跟踪、数据导出 |
| 系统设置 | 风控参数、LLM API 配置、数据清理、用户协议 |

---

## 服务器要求

| 资源 | 最低配置 | 推荐配置 | 说明 |
|------|---------|---------|------|
| **系统** | Ubuntu 20.04+ / Debian 11+ | Ubuntu 22.04 LTS | 需 64 位 Linux |
| **CPU** | 2 核 | 4 核 | Chromium 浏览器自动化较吃 CPU |
| **内存** | 4 GB | 8 GB | Chromium 单实例峰值约 1GB |
| **磁盘** | 20 GB SSD | 40 GB SSD | Docker 镜像约 2GB + 数据空间 |
| **带宽** | 5 Mbps | 10 Mbps | LLM API 调用 + BOSS 直聘爬取 |

> **云服务器参考价格**: 阿里云/腾讯云 4核8G SSD 约 200~300 元/月

---

## 快速部署（5 步完成）

```bash
# 1. 安装 Docker（已安装则跳过）
curl -fsSL https://get.docker.com | sh
sudo systemctl enable docker && sudo systemctl start docker
sudo usermod -aG docker $USER && newgrp docker

# 2. 克隆代码
git clone https://github.com/YizheDev/ai-job-agent-platform.git /opt/ai-job-agent
cd /opt/ai-job-agent
git checkout feature/AiJobAgent-V1

# 3. 修复脚本行尾（Windows 开发的项目必须执行）
sudo apt install -y dos2unix && find deploy/ -name "*.sh" -exec dos2unix {} \;

# 4. 配置环境变量（必填 LLM_API_KEY）
cp .env.example .env
nano .env

# 5. 一键部署
bash deploy/deploy.sh
```

部署完成后访问: `http://服务器公网IP`

---

## 详细部署流程

### 第一步: 准备服务器

#### 1.1 安装必备软件

```bash
# 更新系统
sudo apt update && sudo apt upgrade -y

# 安装基础工具
sudo apt install -y git curl dos2unix

# 安装 Docker
curl -fsSL https://get.docker.com | sh
sudo systemctl enable docker
sudo systemctl start docker

# 将当前用户加入 docker 组（免 sudo）
sudo usermod -aG docker $USER

# 重要: 必须重新登录 SSH 使 docker 组生效
exit
# 重新 SSH 登录后继续
```

#### 1.2 验证安装

```bash
docker --version          # Docker Engine 24.0+
docker compose version    # Docker Compose V2
```

#### 1.3 开放防火墙端口

```bash
# Ubuntu (ufw)
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw reload

# CentOS (firewalld)
sudo firewall-cmd --permanent --add-service=http
sudo firewall-cmd --permanent --add-service=https
sudo firewall-cmd --reload
```

### 第二步: 部署项目

#### 2.1 上传代码

**方式 A: Git 克隆（推荐）**

```bash
cd /opt
git clone https://github.com/YizheDev/ai-job-agent-platform.git ai-job-agent
cd ai-job-agent
git checkout feature/AiJobAgent-V1
```

**方式 B: 手动上传**

```bash
# 本地打包（排除运行时数据）
tar --exclude='data' --exclude='logs' --exclude='.git' \
    --exclude='__pycache__' --exclude='.env' --exclude='backups' \
    -czf ai-job-agent.tar.gz -C /path/to/project .

# 上传到服务器
scp ai-job-agent.tar.gz user@服务器IP:/opt/

# 服务器上解压
ssh user@服务器IP
mkdir -p /opt/ai-job-agent && cd /opt/ai-job-agent
tar -xzf /opt/ai-job-agent.tar.gz
rm /opt/ai-job-agent.tar.gz
```

#### 2.2 修复脚本行尾（关键步骤）

项目在 Windows 上开发，Shell 脚本可能包含 CRLF 行尾，在 Linux 上会导致执行失败：

```bash
cd /opt/ai-job-agent
sudo apt install -y dos2unix
find deploy/ -name "*.sh" -exec dos2unix {} \;
```

#### 2.3 配置环境变量

```bash
cp .env.example .env
nano .env
```

**必须修改**以下项:

```ini
# 填入你的大模型 API Key（必填，登录时会验证）
LLM_API_KEY=sk-xxxxxxxxxxxxxxxx

# 如使用国内模型（如 DeepSeek），修改以下两项
LLM_BASE_URL=https://api.deepseek.com/v1
LLM_MODEL=deepseek-chat
```

**可选配置**:

```ini
# 风控参数（可通过 UI 系统设置页动态修改）
MAX_DAILY_DELIVERY=20     # 单日最大投递量 (1-50)
DELIVERY_START_HOUR=9     # 投递开始时段 (0-23)
DELIVERY_END_HOUR=18      # 投递结束时段 (1-24)
MATCH_THRESHOLD=70        # 最低匹配分数阈值 (0-100)

# 服务端口（Docker 内部端口，Nginx 会代理到 80）
SERVER_PORT=7860
```

> 注意: 风控参数和 LLM API 配置也可在部署后通过 Web UI 的「系统设置」页面修改，修改会实时写入 `.env` 并热更新。

#### 2.4 构建并启动

```bash
# 一键部署（推荐）
bash deploy/deploy.sh

# 或者手动操作:
docker compose build      # 构建镜像（首次约 5-10 分钟）
docker compose up -d       # 后台启动
```

#### 2.5 验证部署

```bash
# 检查容器状态（等待 app 变为 healthy，约 30-60 秒）
docker compose ps

# 期望输出:
# NAME                 STATUS              PORTS
# ai-job-agent         Up xx seconds (healthy)   7860/tcp
# ai-job-agent-nginx   Up xx seconds       0.0.0.0:80->80/tcp

# 检查应用日志
docker compose logs app --tail 50

# 测试访问
curl -s -o /dev/null -w "%{http_code}" http://localhost
# 期望返回: 200
```

浏览器访问: `http://服务器公网IP`

---

## Docker 环境行为说明

部署到 Docker 后，系统行为与本地 Windows 开发环境有以下区别：

### 浏览器自动化模式

| 模式 | 本地 Windows | Docker 服务器 |
|------|-------------|--------------|
| **DrissionPage（Chrome 真实浏览器）** | 打开可视化窗口，手动扫码登录 | 自动切换为无头模式，通过 Cookie 持久化保持登录 |
| **Playwright（内置浏览器）** | 可视化/无头均可 | 强制无头模式 + `--no-sandbox` |
| **连接优先级** | DrissionPage 优先，失败降级 Playwright | 同左，DrissionPage 无头运行 |

### BOSS 直聘登录

Docker 环境中 BOSS 账号登录有两种方式：

1. **Cookie 持久化**（推荐）: 先在本地登录并导出 Cookie，将 `data/.cookies_boss_zhipin.enc` 文件复制到 Docker 卷中
2. **Docker 内登录**: DrissionPage 无头模式下访问 BOSS 直聘，可能需要处理验证码

### 数据持久化

| 数据 | 存储位置 | Docker Volume |
|------|---------|---------------|
| SQLite 数据库 | `data/job_agent.db` | `app-data` |
| 加密 Cookie | `data/.cookies_*.enc` | `app-data` |
| 加密密钥 | `data/.keyfile` | `app-data` |
| 上传的简历 | `data/resumes/` | `app-data` |
| 截图文件 | `data/screenshots/` | `app-data` |
| DrissionPage 浏览器配置 | `data/drission_profile/` | `app-data` |
| 应用日志 | `logs/app.log` | `app-logs` |
| 环境配置 | `.env` | 宿主机 bind mount |

### 配置热更新

通过 Web UI 修改的配置（LLM API Key、风控参数等）会实时写入 `.env` 文件并热更新，无需重启容器。`.env` 文件通过 bind mount 同步到宿主机。

---

## HTTPS 配置

### 方式 A: Let's Encrypt 免费证书（推荐）

前提：你需要一个已解析到服务器 IP 的域名。

```bash
# 1. 安装 certbot
sudo apt install -y certbot

# 2. 先停止 Nginx 容器释放 80 端口
cd /opt/ai-job-agent
docker compose stop nginx

# 3. 申请证书（替换 your-domain.com 为实际域名）
sudo certbot certonly --standalone -d your-domain.com

# 4. 复制证书到项目目录
mkdir -p deploy/nginx/ssl
sudo cp /etc/letsencrypt/live/your-domain.com/fullchain.pem deploy/nginx/ssl/
sudo cp /etc/letsencrypt/live/your-domain.com/privkey.pem deploy/nginx/ssl/
sudo chmod 600 deploy/nginx/ssl/privkey.pem
sudo chmod 644 deploy/nginx/ssl/fullchain.pem
```

```bash
# 5. 编辑 Nginx 配置启用 HTTPS
nano deploy/nginx/conf.d/app.conf

# 操作:
#   a. 取消 "HTTPS 配置" 段和 "HTTP → HTTPS 重定向" 段的注释
#   b. 将 your-domain.com 替换为实际域名
#   c. 注释掉底部 "HTTP 直连" 段
```

```bash
# 6. 重启 Nginx
docker compose up -d nginx
```

> 建议启用 HTTPS: 系统使用浏览器端存储 (BrowserState) 保持用户会话，HTTP 下传输不加密。

### 证书自动续期

```bash
crontab -e
```

添加以下内容（每月 1 号凌晨 3 点）：

```
0 3 1 * * cd /opt/ai-job-agent && docker compose stop nginx && certbot renew --quiet && cp /etc/letsencrypt/live/your-domain.com/fullchain.pem deploy/nginx/ssl/ && cp /etc/letsencrypt/live/your-domain.com/privkey.pem deploy/nginx/ssl/ && chmod 600 deploy/nginx/ssl/privkey.pem && docker compose start nginx
```

> 注意: `--standalone` 方式续期需要先停 Nginx 释放 80 端口，上述 cron 命令已包含此步骤。

---

## 运维操作

### 日常命令

```bash
cd /opt/ai-job-agent

# 查看所有服务状态
docker compose ps

# 查看应用实时日志
docker compose logs -f app

# 查看 Nginx 日志
docker compose logs -f nginx

# 重启应用（不重建镜像）
docker compose restart app

# 停止所有服务
docker compose down

# 停止并删除数据卷（⚠️ 所有数据会丢失，慎用）
docker compose down -v
```

### 更新部署

```bash
cd /opt/ai-job-agent

# 1. 备份数据
bash deploy/backup.sh

# 2. 拉取最新代码
git pull origin feature/AiJobAgent-V1

# 3. 修复可能的行尾问题
find deploy/ -name "*.sh" -exec dos2unix {} \; 2>/dev/null || true

# 4. 重新构建并启动
docker compose build --no-cache
docker compose up -d

# 5. 验证
docker compose ps
docker compose logs app --tail 20
```

### 资源监控

```bash
# 实时资源监控
docker stats ai-job-agent ai-job-agent-nginx

# 磁盘使用
docker system df
```

### 修改配置（无需重建镜像）

以下配置可通过两种方式修改，效果相同：

**方式 A: 命令行**

```bash
nano .env
docker compose restart app
```

**方式 B: Web UI**

在浏览器中进入「系统设置」页面 → 修改风控参数或 LLM API 配置 → 点击保存，自动生效。

---

## 数据备份与恢复

### 手动备份

```bash
cd /opt/ai-job-agent
bash deploy/backup.sh
```

### 定时自动备份（推荐）

```bash
mkdir -p /opt/ai-job-agent/backups
crontab -e
```

添加以下内容：

```
0 3 * * * cd /opt/ai-job-agent && bash deploy/backup.sh >> /opt/ai-job-agent/backups/backup.log 2>&1
```

### 数据恢复

```bash
cd /opt/ai-job-agent

# 1. 查看可用备份
ls backups/

# 2. 停止服务
docker compose down

# 3. 获取实际的 volume 名称
docker volume ls | grep app-data
# 输出类似: local  ai-job-agent_app-data

# 4. 恢复数据（替换 volume 名和日期）
# 必须 chown 为 1000:1000 (pwuser)，否则应用无写入权限
docker run --rm \
  -v ai-job-agent_app-data:/data \
  -v /opt/ai-job-agent/backups/20260412_030000/data:/backup:ro \
  alpine sh -c "rm -rf /data/* && cp -rf /backup/* /data/ && chown -R 1000:1000 /data"

# 5. 重启服务
docker compose up -d
```

> Volume 名称格式为 `{项目目录名}_{卷名}`。如项目目录是 `/opt/ai-job-agent`，则卷名为 `ai-job-agent_app-data`。可用 `docker volume ls` 确认。

---

## 常见问题

### Q1: 构建镜像很慢 / pip 安装超时

使用国内 pip 镜像源，编辑 `Dockerfile`，在 `pip install` 前添加：

```dockerfile
RUN pip config set global.index-url https://pypi.tuna.tsinghua.edu.cn/simple
```

Docker 拉取基础镜像慢，可配置 Docker 镜像加速器：

```bash
sudo mkdir -p /etc/docker
sudo tee /etc/docker/daemon.json <<-'EOF'
{
  "registry-mirrors": ["https://mirror.ccs.tencentyun.com"]
}
EOF
sudo systemctl daemon-reload
sudo systemctl restart docker
```

### Q2: 容器启动后页面打不开

```bash
# 1. 检查容器状态
docker compose ps

# 2. 查看错误日志
docker compose logs app --tail 100

# 3. 检查端口是否被占用
sudo ss -tlnp | grep ":80 "

# 4. 检查防火墙
sudo ufw status

# 5. 检查云服务器安全组是否放行 80/443 端口
```

### Q3: Chromium 崩溃 / OOM

`docker-compose.yml` 已配置 `shm_size: "1gb"` 和 `mem_limit: 4g`。如果仍然崩溃：

```yaml
# 编辑 docker-compose.yml，增大资源限制
mem_limit: 8g
shm_size: "2gb"
```

### Q4: BOSS 直聘登录问题

Docker 环境中 DrissionPage 以无头模式运行，BOSS 登录依赖 Cookie：

```bash
# 方案 1: 从本地导入 Cookie
# 先在本地 Windows 上登录成功，然后复制加密 Cookie 文件到服务器
scp data/.cookies_boss_zhipin.enc user@服务器IP:/opt/ai-job-agent/

# 将 Cookie 导入到 Docker 卷
docker cp /opt/ai-job-agent/.cookies_boss_zhipin.enc ai-job-agent:/app/data/

# 方案 2: 通过 UI 使用"内置浏览器(备用)"模式连接
# 该模式使用 Playwright 无头浏览器，可能需要处理验证码
```

### Q5: deploy.sh 报错 `\r: command not found`

脚本包含 Windows 行尾（CRLF），需要转换：

```bash
sudo apt install -y dos2unix
find deploy/ -name "*.sh" -exec dos2unix {} \;
```

### Q6: Nginx 启动失败，一直等待

如果应用容器未通过健康检查，Nginx 不会启动（`depends_on: service_healthy`）。先检查应用容器：

```bash
# 查看应用容器状态和日志
docker inspect --format='{{.State.Health.Status}}' ai-job-agent
docker compose logs app --tail 50

# 如需跳过健康检查先启动 Nginx 调试
docker compose up -d --no-deps nginx
```

### Q7: 端口 80 被占用

```bash
# 查看占用进程
sudo ss -tlnp | grep ":80 "

# 停止 Apache（常见冲突）
sudo systemctl stop apache2 && sudo systemctl disable apache2

# 或修改 docker-compose.yml 使用其他端口
# ports:
#   - "8080:80"
```

### Q8: 如何查看 SQLite 数据库

```bash
docker exec -it ai-job-agent bash
sqlite3 /app/data/job_agent.db
.tables
SELECT count(*) FROM delivery_record;
.quit
```

### Q9: 多用户使用注意事项

系统支持多用户登录（通过用户名区分），但有以下限制：

- **LLM API Key**: 所有用户共享同一个 API Key（存储在 `.env` 中）。每次登录或修改 API 设置会覆盖当前 Key。
- **数据隔离**: 简历、投递记录、JD 匹配记录通过 `user_name` 字段隔离。
- **BOSS 账号**: 所有用户共享同一个 BOSS 直聘登录会话。

---

## 部署文件结构

```
ai-job-agent-platform/
├── Dockerfile                # 应用镜像（Playwright + DrissionPage + Chromium）
├── docker-compose.yml        # 服务编排（App + Nginx）
├── .dockerignore             # 构建排除文件
├── .gitattributes            # 强制 .sh/.conf 使用 LF 行尾
├── .env.example              # 环境变量模板
├── .env                      # 实际配置（不入 Git，登录/设置时自动更新）
├── DEPLOY.md                 # 本文档
├── deploy/
│   ├── entrypoint.sh         # 容器启动入口（权限检查）
│   ├── deploy.sh             # 一键部署脚本
│   ├── backup.sh             # 数据备份脚本
│   └── nginx/
│       ├── nginx.conf        # Nginx 主配置
│       ├── conf.d/
│       │   └── app.conf      # 站点配置（HTTP/HTTPS）
│       └── ssl/              # SSL 证书目录
├── app/
│   ├── agents/               # LangGraph 智能体节点
│   ├── core/                 # 配置、日志、异常定义
│   ├── db/                   # SQLite 模型与 CRUD
│   ├── ui/                   # Gradio 界面（登录 + 8 个功能页）
│   ├── utils/                # 浏览器工具、爬虫、加密、文件处理
│   └── workflow/             # LangGraph 工作流编排
├── data/                     # 运行时数据（Docker Volume: app-data）
├── logs/                     # 日志目录（Docker Volume: app-logs）
├── backups/                  # 备份目录（宿主机本地）
└── main.py                   # 应用启动入口
```

### 环境变量清单

| 变量 | 必填 | 默认值 | 说明 | UI 可改 |
|------|------|--------|------|---------|
| `LLM_API_KEY` | 是 | - | 大模型 API Key | 是（登录/设置） |
| `LLM_BASE_URL` | 否 | `https://api.openai.com/v1` | API 地址 | 是 |
| `LLM_MODEL` | 否 | `gpt-4` | 模型名称 | 是 |
| `LLM_TEMPERATURE` | 否 | `0.7` | 采样温度 | 否 |
| `LLM_MAX_TOKENS` | 否 | `4096` | 最大 Token 数 | 否 |
| `MAX_DAILY_DELIVERY` | 否 | `20` | 单日最大投递量 | 是 |
| `MIN_DELAY_SECONDS` | 否 | `2` | 最小投递延时(秒) | 是 |
| `MAX_DELAY_SECONDS` | 否 | `4` | 最大投递延时(秒) | 是 |
| `DELIVERY_START_HOUR` | 否 | `9` | 投递开始时段 | 是 |
| `DELIVERY_END_HOUR` | 否 | `18` | 投递结束时段 | 是 |
| `MATCH_THRESHOLD` | 否 | `70` | 最低匹配分数 | 是 |
| `ENCRYPTION_KEY` | 否 | 自动生成 | AES 密钥(base64) | 否 |
| `COOKIE_EXPIRE_DAYS` | 否 | `7` | Cookie 过期天数 | 否 |
| `PLATFORM` | 否 | `boss` | 招聘平台 | 否 |
| `SERVER_PORT` | 否 | `7860` | Gradio 服务端口 | 否 |
| `DEBUG` | 否 | `false` | 调试模式 | 否 |
