# OhmStash API

OhmStash API 是用于管理电子元器件、仓储盒、库存位置、标签属性、AI 识别和联网搜索配置的 FastAPI 后端，并内置静态 Web UI。

## 主要功能

- 元器件、标签、自定义属性、库存位置和盒子模板管理。
- 盒子、子格、库存放置关系管理。
- 图片识别入库、条码/盒码解析和 WDFX 标签下载。
- 可配置的视觉模型供应商和联网搜索供应商。
- 登录、会话令牌、API Key、日志查看和数据库清理等系统管理能力。
- 内置前端入口：`/ui/`。

## 运行要求

- Python 3.12 或兼容版本。
- PostgreSQL。
- 推荐使用 Conda 管理独立环境。

## 本地开发运行

1. 创建并激活 Conda 环境：

   ```bash
   conda create -n ohmstash-api python=3.12
   conda activate ohmstash-api
   ```

2. 安装依赖：

   ```bash
   pip install -r requirements.txt
   ```

3. 准备 `.env`：

   ```bash
   cp .env.example .env
   ```

   至少需要设置数据库连接：

   ```env
   DATABASE_URL=postgresql://user:password@host:5432/dbname
   ```

4. 启动 HTTP 开发服务：

   ```bash
   uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
   ```

5. 打开 Web UI：

   ```text
   http://127.0.0.1:8000/ui/
   ```

如需在本地测试 HTTPS、摄像头等安全上下文能力，可以让 Uvicorn 使用应用启动入口和自签证书：

```env
HTTPS_ENABLED=true
HTTPS_PORT=8443
HTTPS_CERTIFICATE_SOURCE=self-signed
SSL_CERTFILE=
SSL_KEYFILE=
```

```bash
python -m app.run
```

此时访问：

```text
https://127.0.0.1:8443/ui/
```

首次启动时应用会自动创建数据库表并初始化管理员。账号由 `.env` 中的 `ADMIN_USERNAME` 控制；`ADMIN_INITIAL_PASSWORD` 只在数据库还没有管理员时使用，成功创建后会自动清空。忘记网页密码时，可临时填写 `ADMIN_PASSWORD_RESET` 并重启，应用会重置管理员密码并自动清空该字段。

## 配置项

应用通过环境变量或项目根目录 `.env` 读取配置。

| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `DATABASE_URL` | 无 | 完整 PostgreSQL 连接串。设置后优先使用该值。 |
| `POSTGRES_SERVER` | 无 | 未设置 `DATABASE_URL` 时用于拼接数据库连接。 |
| `POSTGRES_USER` | 无 | 未设置 `DATABASE_URL` 时用于拼接数据库连接。 |
| `POSTGRES_PASSWORD` | 无 | 未设置 `DATABASE_URL` 时用于拼接数据库连接。 |
| `POSTGRES_DB` | 无 | 未设置 `DATABASE_URL` 时用于拼接数据库连接。 |
| `PROJECT_NAME` | `OhmStash API` | FastAPI 应用名称。 |
| `API_V1_STR` | `/api/v1` | API v1 前缀。 |
| `LOG_LEVEL` | `INFO` | 默认日志等级。 |
| `LOG_FILE_PATH` | 空 | 日志文件路径；为空时使用默认日志文件。 |
| `ADMIN_USERNAME` | `admin` | 首次初始化管理员用户名。 |
| `ADMIN_INITIAL_PASSWORD` | `password` | 首次初始化管理员密码；创建成功后会自动清空配置文件中的值。 |
| `ADMIN_PASSWORD_RESET` | 空 | 忘记网页密码时填写的一次性重置密码；重置成功后会自动清空。 |
| `SERVER_HOST` | `0.0.0.0` | `python -m app.run` 使用的监听地址。 |
| `HTTP_PORT` | `8000` | HTTP 模式端口。 |
| `HTTPS_ENABLED` | `false` | 是否启用 HTTPS 访问配置。非 ACME 时由 `python -m app.run` 直接监听 HTTPS；ACME 时由 Caddy 对外处理 HTTPS。 |
| `HTTPS_PORT` | `8443` | 直接由应用提供 HTTPS 时的端口；Docker/Caddy ACME 部署中固定使用公网 443。 |
| `HTTPS_CERTIFICATE_SOURCE` | `self-signed` | HTTPS 证书来源：本地或 systemd 可用 `self-signed`、`path`、`upload`、`paste`；Docker 部署建议只用 `acme`。 |
| `SSL_CERTFILE` | 空 | HTTPS 证书文件路径。 |
| `SSL_KEYFILE` | 空 | HTTPS 私钥文件路径。 |
| `ACME_CHALLENGE_TYPE` | `http-01` | Caddy ACME 验证方式：`http-01` 或 `dns-01`。 |
| `ACME_DOMAIN` | 空 | Caddy ACME 使用的公网域名。 |
| `ACME_EMAIL` | 空 | ACME 账号邮箱。 |
| `ACME_CLOUDFLARE_API_TOKEN` | 空 | DNS-01 使用的 Cloudflare API Token。 |
| `CADDY_CONFIG_PATH` | `caddy/Caddyfile` | UI 保存 Caddy 配置文件的位置。 |
| `CADDY_BACKEND_HOST` | `127.0.0.1` | Caddy 反向代理到后端时使用的主机名。 |

`POSTGRES_*` 只在 `DATABASE_URL` 为空时使用。推荐直接配置 `DATABASE_URL`，部署脚本和 systemd 环境会更简单。

## HTTP / HTTPS 启动方式

### HTTP

使用项目内启动入口读取 `.env`：

```bash
python -m app.run
```

默认监听：

```text
http://0.0.0.0:8000
```

如需改端口：

```env
HTTP_PORT=8080
HTTPS_ENABLED=false
```

### HTTPS

应用可以直接由 Uvicorn 提供 HTTPS，不需要 Nginx 反向代理。

使用已有证书：

```env
HTTPS_ENABLED=true
HTTPS_PORT=8443
SSL_CERTFILE=/opt/ohmstash_api/certs/fullchain.pem
SSL_KEYFILE=/opt/ohmstash_api/certs/privkey.pem
```

没有证书时也可以启用 HTTPS：

```env
HTTPS_ENABLED=true
HTTPS_PORT=8443
SSL_CERTFILE=
SSL_KEYFILE=
```

此时应用会在 `certs/` 下自动生成自签证书。浏览器首次访问会提示证书不受信任，手动信任后即可使用摄像头等 HTTPS 才允许的能力。

## VPS 部署建议

生产部署不建议在 SSH 会话里直接长期运行 `uvicorn`。推荐做法是优先使用 Docker Compose 管理 API、PostgreSQL 和 Caddy；Docker 模式下公网只暴露 Caddy 的 80/443，API 的 8000 只在 Compose 内部网络中使用。如果不使用 Docker，也可以用 systemd 管理后端进程，公网直接访问应用监听的 HTTP 或 HTTPS 端口。

### Docker Compose 快速部署

项目已经包含 `Dockerfile`、`Dockerfile.caddy`、`docker-compose.yml` 和 `.env.docker.example`。GitHub Actions 会构建并发布 API/Caddy 镜像，Compose 默认从 GHCR 拉取镜像并启动三个容器：

- `ohmstash-api`：FastAPI 应用，内置 Web UI，只在 Compose 内部网络监听 8000。
- `ohmstash-db`：PostgreSQL 16，数据保存在 Docker volume 中。
- `ohmstash-caddy`：公网入口，监听 80/443，反向代理到 API，并可自动申请 ACME 证书。

首次部署：

```bash
git clone https://github.com/yuhanzhang521/ohmstash_api /opt/ohmstash_api
cd /opt/ohmstash_api
cp .env.docker.example .env.docker
nano .env.docker
docker compose pull
docker compose up -d
```

至少需要在 `.env.docker` 中修改：

```env
POSTGRES_PASSWORD=change-this-database-password
ADMIN_INITIAL_PASSWORD=change-this-admin-password
```

启动后访问：

```text
http://<your-vps-ip>/ui/
```

常用运维命令：

```bash
docker compose ps
docker compose logs -f api
docker compose restart api
docker compose pull
docker compose up -d
```

当前 Compose 不再把 API 的 `8000` 或 `8443` 发布到宿主机。API 容器内部保持 `HTTP_PORT=8000`，Caddy 通过 Docker 网络访问 `http://api:8000`。公网只发布 Caddy 的 `80:80`、`443:443` 和 `443:443/udp`。

首次登录后建议立刻在 Web UI 中修改管理员密码。UI 修改密码只更新数据库，不会写回 `.env.docker`。如果忘记密码，在 `.env.docker` 中临时填写 `ADMIN_PASSWORD_RESET=<new-password>` 后执行 `docker compose up -d`，应用会把新密码哈希保存到数据库并自动清空该字段。

默认 `HTTPS_ENABLED=false` 时，Caddy 会在 80 端口反向代理到 API。启用公网 HTTPS 时，进入「设置 -> 服务」，打开 HTTPS，并选择证书来源 `ACME`：

- `HTTP-01` 需要域名解析到当前服务器，并允许公网访问 80 和 443。
- `DNS-01` 需要填写 Cloudflare API Token，目前只支持 Cloudflare。
- API 后端仍保持内部 HTTP 8000，不直接对公网开放。

也可以直接在 `.env.docker` 中预置 HTTP-01：

```env
HTTPS_ENABLED=true
HTTPS_CERTIFICATE_SOURCE=acme
ACME_CHALLENGE_TYPE=http-01
ACME_DOMAIN=ohmstash.example.com
ACME_EMAIL=admin@example.com
HTTP_PORT=8000
HTTPS_PORT=443
```

DNS-01 示例：

```env
HTTPS_ENABLED=true
HTTPS_CERTIFICATE_SOURCE=acme
ACME_CHALLENGE_TYPE=dns-01
ACME_DOMAIN=ohmstash.example.com
ACME_EMAIL=admin@example.com
ACME_CLOUDFLARE_API_TOKEN=your-cloudflare-api-token
HTTP_PORT=8000
HTTPS_PORT=443
```

启用后访问：

```text
https://ohmstash.example.com/ui/
```

Docker Compose 部署中不建议让 API 容器自身提供公网 HTTPS。自签证书、证书文件路径、上传 PEM 和粘贴 PEM 更适合本地调试或非 Docker 的 systemd 部署。

Docker 部署中的持久化数据：

- PostgreSQL 数据：`ohmstash-postgres-data`。
- 应用日志：`ohmstash-logs`，容器内路径 `/app/logs/ohmstash.log`。
- Caddy ACME 证书和运行状态：`ohmstash-caddy-data`、`ohmstash-caddy-config`。
- Caddyfile：宿主机项目目录下的 `caddy/Caddyfile` 会挂载给 Caddy，并由 API 在保存 ACME 设置时更新。
- 服务配置：宿主机项目目录下的 `.env.docker` 会挂载为容器内 `/app/.env`，因此在 UI 中保存的服务端口和 ACME 配置会写回这个文件；一次性管理员初始密码或重置密码成功使用后也会被自动清空。

备份数据库：

```bash
docker compose exec db sh -c 'pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB"' > ohmstash-backup.sql
```

恢复数据库：

```bash
docker compose exec -T db sh -c 'psql -U "$POSTGRES_USER" "$POSTGRES_DB"' < ohmstash-backup.sql
```

### systemd 部署

首次部署时建议先在 `.env` 写入能让服务启动的最小配置：

```env
DATABASE_URL=postgresql://ohmstash:password@127.0.0.1:5432/ohmstash
SERVER_HOST=0.0.0.0
HTTP_PORT=8000
HTTPS_ENABLED=true
HTTPS_PORT=8443
ADMIN_USERNAME=admin
ADMIN_INITIAL_PASSWORD=change-this-password
ADMIN_PASSWORD_RESET=
LOG_LEVEL=INFO
```

启动后进入 `/ui/`，后续服务监听、HTTP/HTTPS 端口、证书路径、证书 PEM 粘贴/上传都可以在「设置 -> 服务」中修改。保存后页面会询问是否立即重启服务；也可以点击「重启服务」按钮手动重启。除非服务无法启动或系统崩溃，正常后续配置不需要再次登录 VPS 修改文件。

示例 systemd 服务：

```ini
[Unit]
Description=OhmStash API
After=network.target postgresql.service

[Service]
Type=simple
WorkingDirectory=/opt/ohmstash_api
Environment="PATH=/opt/miniconda3/envs/ohmstash-api/bin"
ExecStart=/opt/miniconda3/envs/ohmstash-api/bin/python -m app.run
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

常用命令：

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now ohmstash-api
sudo systemctl status ohmstash-api
journalctl -u ohmstash-api -f
```

## API 和页面入口

- Web UI：`/ui/`
- 登录页：`/ui/login.html`
- 健康检查：`/api/v1/system/health`
- 服务监听配置：`/api/v1/system/config`
- 服务重启：`/api/v1/system/restart`
- 日志配置：`/api/v1/system/logs/config`
- 最近日志：`/api/v1/system/logs`

OpenAPI、Swagger UI 和 ReDoc 当前在应用中关闭。

## 测试

```bash
pytest
```

如果测试环境使用独立数据库，请在运行测试前设置测试专用 `DATABASE_URL`，避免污染生产或本地真实数据。

