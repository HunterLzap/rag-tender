# Docker 部署指南

本文档面向 Linux 云服务器部署。目标是用 Docker 把前端、后端、LibreOffice、Python 依赖和运行方式固定下来，减少服务器环境差异。

## 1. 部署结构

```text
浏览器
  |
  | http://服务器IP 或域名
  v
frontend 容器：Nginx + React 静态文件
  |
  | /api/* 反向代理
  v
backend 容器：FastAPI + Python 依赖 + LibreOffice
  |
  | 挂载目录
  v
宿主机 ./data：SQLite 数据库、上传文件、RAG 工作区、输出文件
```

做什么：把前端和后端拆成两个容器，用 `docker-compose.yml` 统一启动。

为什么：前端是静态站点，适合由 Nginx 托管；后端是长运行 API 服务，适合独立容器。`./data` 挂载到宿主机后，即使重建镜像或删除容器，业务数据也不会丢。

## 2. 服务器安装 Docker

Ubuntu/Debian 常用安装方式：

```bash
sudo apt update
sudo apt install -y ca-certificates curl gnupg
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
sudo chmod a+r /etc/apt/keyrings/docker.gpg
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
  $(. /etc/os-release && echo "$VERSION_CODENAME") stable" \
  | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
sudo apt update
sudo apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
```

验证：

```bash
docker --version
docker compose version
```

做什么：安装 Docker Engine 和 Compose 插件。

为什么：Docker Engine 负责运行容器，Compose 负责按配置一次性启动前端、后端和网络。

## 3. 拉取私有仓库代码

推荐给服务器配置 Gitee SSH Key，然后拉代码：

```bash
ssh-keygen -t ed25519 -C "rag-tender-server"
cat ~/.ssh/id_ed25519.pub
```

把公钥添加到 Gitee 仓库或账号后：

```bash
mkdir -p /opt/apps
cd /opt/apps
git clone git@gitee.com:ryan406/rag-tender.git
cd rag-tender
```

做什么：把闭源项目代码拉到服务器。

为什么：服务器后续更新只需要 `git pull`，不需要手动传文件。

## 4. 创建环境变量文件

复制示例文件：

```bash
cp .env.example .env
```

生成 `RAG_TENDER_SECRET_KEY`：

```bash
docker run --rm python:3.13-slim sh -c "pip install cryptography==49.0.0 >/dev/null && python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'"
```

编辑 `.env`：

```bash
nano .env
```

至少确认：

```env
RAG_TENDER_SECRET_KEY=替换成你生成的值
LIBREOFFICE_PATH=/usr/bin/soffice
RAG_TENDER_CORS_ORIGINS=http://localhost,http://127.0.0.1
```

做什么：给后端提供加密主密钥和 Linux 下 LibreOffice 路径。

为什么：API Key 会加密后存入 SQLite。这个密钥如果丢失，旧数据库里的 API Key 就无法解密；如果复用旧数据库，必须复用同一个密钥。

## 5. 构建并启动

```bash
docker compose up -d --build
```

查看状态：

```bash
docker compose ps
```

查看日志：

```bash
docker compose logs -f backend
docker compose logs -f frontend
```

做什么：构建两个镜像并在后台启动服务。

为什么：`--build` 会根据 Dockerfile 安装依赖并打包前端；`-d` 让服务在后台运行，退出 SSH 后也继续工作。

## 6. 访问和验证

浏览器访问：

```text
http://服务器IP:8088/
```

后端健康检查：

```bash
curl http://127.0.0.1:8088/api/v1/health
```

API 文档：

```text
http://服务器IP:8088/docs
```

做什么：确认前端、Nginx 代理和后端 API 都正常。

为什么：首页能打开只说明前端正常；`/api/v1/health` 正常才说明前后端链路也通了。

## 7. 常用维护命令

停止服务：

```bash
docker compose down
```

重启服务：

```bash
docker compose restart
```

更新代码后重新部署：

```bash
git pull
docker compose up -d --build
```

查看后端实时日志：

```bash
docker compose logs -f backend
```

进入后端容器排查：

```bash
docker compose exec backend bash
```

做什么：日常更新、重启、排查问题。

为什么：Docker 部署后不直接在宿主机跑 Python 或 Node，排查应该围绕容器日志和容器内部环境。

## 8. 数据备份

业务数据在宿主机项目目录的 `data/`：

```bash
tar -czf rag-tender-data-$(date +%F).tar.gz data
```

做什么：备份 SQLite 数据库、上传文件、RAG 工作区和输出文件。

为什么：镜像和容器都可以重建，`data/` 才是需要长期保存的业务资产。

## 9. 域名和 HTTPS

当前 `docker-compose.yml` 默认把前端容器暴露到宿主机 `8088` 端口，避免和服务器已有的 Nginx、Apache、宝塔面板或其他网站占用的 `80/443` 冲突。

生产环境建议再加一层宿主机 Nginx 或 Caddy 做 HTTPS：

```text
公网 443 HTTPS
  -> 宿主机 Nginx/Caddy
  -> 127.0.0.1:8088
  -> frontend 容器
```

做什么：用域名和 TLS 证书保护访问。

为什么：标书、资质文件和模型 API Key 都属于敏感数据，不建议长期通过 HTTP 明文访问。

## 10. 常见问题

### 端口 80 被占用

默认已经不占用宿主机 `80`，而是使用 `.env` 中的：

```env
RAG_TENDER_HTTP_PORT=8088
```

如果 `8088` 也被占用，先查询端口：

```bash
ss -tulnp | grep -E ':80|:443|:8088|:18080|:30080'
```

然后把 `.env` 改成一个空闲端口，例如：

```env
RAG_TENDER_HTTP_PORT=18080
```

重新启动：

```bash
docker compose up -d
```

然后访问 `http://服务器IP:18080/`。

### 后端镜像构建很慢

这是正常的。后端依赖包含 OCR、RAG、Paddle、Torch、LibreOffice，首次构建会下载大量包。后续只要 `requirements.txt` 不变，Docker 会复用缓存。

### Office 转 PDF 失败

检查后端容器内 LibreOffice：

```bash
docker compose exec backend /usr/bin/soffice --version
```

如果能输出版本，说明 LibreOffice 已安装；继续看后端日志定位具体文件转换错误。
