# Nginx 配置管理平台

[![Python](https://img.shields.io/badge/Python-3.8%2B-blue)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.104.1-green)](https://fastapi.tiangolo.com/)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](#)

一个现代化的多环境 Nginx 配置管理 Web 平台，基于 FastAPI 框架开发，为系统管理员和运维人员提供统一的 Nginx 配置管理解决方案。

## 🚀 项目概述

### 核心功能

- **多环境管理**：支持开发、测试、生产等多环境 Nginx 配置管理
- **可视化配置**：直观的 Web 界面进行配置文件浏览、编辑和管理
- **实时同步**：配置文件与远程 Nginx 服务器的双向同步
- **权限控制**：基于角色的用户权限管理，确保操作安全性
- **操作审计**：完整的操作日志记录，支持配置变更追踪
- **批量操作**：支持批量配置测试、重载和部署

### 技术亮点

- **高性能架构**：采用异步 I/O 和连接池技术，优化 SSH 操作性能 95%+
- **现代化 UI**：响应式设计，支持移动端访问
- **安全认证**：JWT 令牌认证，bcrypt 密码加密
- **数据库迁移**：Alembic 支持的版本化数据库管理

## 🛠️ 技术栈

### 后端技术

- **Web 框架**：FastAPI 0.104.1 - 现代化 Python 异步 Web 框架
- **数据库**：MySQL + SQLAlchemy ORM 2.0.22
- **认证**：JWT (JSON Web Token) + bcrypt 密码加密
- **SSH 连接**：Paramiko 3.3.1 - 支持连接池和批量操作
- **数据验证**：Pydantic 2.4.2 - 类型安全的数据验证
- **数据库迁移**：Alembic 1.12.0

### 前端技术

- **模板引擎**：Jinja2 - 服务端渲染
- **样式框架**：Bootstrap 5 - 响应式 UI 组件
- **JavaScript**：原生 JS + jQuery - 交互增强
- **代码编辑器**：CodeMirror - Nginx 配置语法高亮

### 运行环境

- **Web 服务器**：Uvicorn (开发) / Gunicorn + UvicornWorker (生产)
- **Python 版本**：3.8+
- **数据库**：MySQL 5.7+
- **操作系统**：Linux / Windows / macOS

## 📋 环境要求

### 系统要求

- **Python**: 3.8+ (推荐 3.9+)
- **数据库**: MySQL 5.7+ / MariaDB 10.3+
- **操作系统**: Linux / Windows / macOS
- **内存**: 至少 512MB
- **磁盘空间**: 至少 1GB

### 目标 Nginx 服务器要求

- **SSH 访问**: 支持 SSH 公钥认证
- **Nginx 版本**: 1.18+ (支持 `nginx -t`和 `nginx -s reload`命令)
- **文件权限**: Nginx 配置目录的读写权限

## 🛠️ 安装指南

### 快速开始

```bash
# 1. 克隆项目
git clone <repository-url>
cd nginx_manager

# 2. 创建虚拟环境
python3 -m venv venv
source venv/bin/activate  # Linux/Mac
# venv\Scripts\activate   # Windows

# 3. 安装依赖
pip install -r requirements.txt

# 4. 配置数据库
# 创建 .env 文件（参考下面的配置说明）

# 5. 初始化数据库
alembic upgrade head

# 6. 创建超级管理员
python -m app.init_superuser

# 7. 启动应用
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### 详细安装步骤

#### 1. 克隆代码库

```bash
git clone <repository-url>
cd nginx_manager
```

#### 2. 创建虚拟环境（强烈推荐）

```bash
python3 -m venv venv

# Linux/Mac 激活虚拟环境
source venv/bin/activate

# Windows 激活虚拟环境
venv\Scripts\activate
```

#### 3. 安装依赖

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

#### 4. 数据库配置

在项目根目录创建 `.env` 文件，配置数据库连接和应用设置：

```env
# 数据库配置
DATABASE_URL=mysql+pymysql://username:password@localhost:3306/nginx_manager

# JWT 安全配置
SECRET_KEY=your-super-secret-key-change-in-production
ACCESS_TOKEN_EXPIRE_MINUTES=1440
ALGORITHM=HS256

# 应用配置
DEBUG=true
APP_NAME=Nginx配置管理平台
APP_VERSION=1.0.0

# 服务器配置
HOST=0.0.0.0
PORT=8000
```

> **安全注意**：生产环境中请务必修改 `SECRET_KEY` 为强随机字符串

**数据库初始化**：

```bash
# 创建数据库（MySQL）
mysql -u root -p
CREATE DATABASE nginx_manager CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
GRANT ALL PRIVILEGES ON nginx_manager.* TO 'nginx_user'@'localhost' IDENTIFIED BY 'your_password';
FLUSH PRIVILEGES;
EXIT;

# 执行数据库迁移
alembic upgrade head
```

#### 5. 创建超级管理员

```bash
python -m app.init_superuser
```

按照提示输入用户名、邮箱和密码。超级管理员具有所有权限，包括：

- 用户管理
- 环境管理
- 所有配置访问权限

## 🚀 启动应用

### 开发环境

```bash
# 方式一：直接运行
python -m app.main

# 方式二：使用 uvicorn（推荐）
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# 指定配置文件
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload --env-file .env
```

### 生产环境

```bash
# 使用 Gunicorn + Uvicorn Worker（推荐）
gunicorn -w 4 -k uvicorn.workers.UvicornWorker app.main:app --bind 0.0.0.0:8000

# 后台运行
gunicorn -w 4 -k uvicorn.workers.UvicornWorker app.main:app \
  --bind 0.0.0.0:8000 \
  --daemon \
  --pid /var/run/nginx_manager.pid \
  --access-logfile /var/log/nginx_manager/access.log \
  --error-logfile /var/log/nginx_manager/error.log

# 使用 systemd 服务（推荐）
sudo systemctl enable nginx_manager
sudo systemctl start nginx_manager
```

**Systemd 服务配置示例** (`/etc/systemd/system/nginx_manager.service`):

```ini
[Unit]
Description=Nginx Manager Web Application
After=network.target mysql.service

[Service]
Type=notify
User=nginx_manager
Group=nginx_manager
WorkingDirectory=/opt/nginx_manager
ExecStart=/opt/nginx_manager/venv/bin/gunicorn -w 4 -k uvicorn.workers.UvicornWorker app.main:app --bind 0.0.0.0:8000
ExecReload=/bin/kill -s HUP $MAINPID
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
```

## 🌍 访问应用

启动应用后，在浏览器中访问：

```
http://localhost:8000
```

**首次登录流程**：

1. 系统会自动重定向到登录页面
2. 使用创建的超级管理员账户登录
3. 首次登录后请在“个人资料”中配置 SSH 私钥
4. 在“环境管理”中添加 Nginx 服务器环境

## 📚 使用指南

### 1. 环境管理

**添加环境**：

- 点击“环境管理” → “创建环境”
- 填写环境信息：
  - **环境名称**：如 `DEV`、`TEST`、`PROD`
  - **服务器 IP**：Nginx 服务器地址
  - **SSH 端口**：默认 22
  - **Nginx 配置路径**：如 `/etc/nginx`

**配置 SSH 访问**：

- 在目标服务器上配置 SSH 公钥认证
- 在用户资料中上传对应的私钥

### 2. 用户管理

**创建用户**：

- 超级管理员可以创建和管理用户
- 支持普通用户和管理员两种角色
- 每个用户可以设置独立的 SSH 私钥

**权限控制**：

- **超级管理员**：所有功能和环境访问权限
- **普通用户**：仅可访问非生产环境，无用户管理权限

### 3. 配置管理

**浏览配置**：

- 通过目录浏览器查看 Nginx 配置结构
- 支持多级目录导航
- 实时显示文件同步状态

**编辑配置**：

- 支持 Nginx 语法高亮
- 自动语法检查
- 实时保存和同步

**同步操作**：

- **上传同步**：将本地编辑的配置同步到远程服务器
- **下载同步**：从远程服务器获取最新配置
- **批量同步**：同步整个目录的所有配置

### 4. Nginx 操作

**配置测试**：

```bash
# 系统会执行
nginx -t
```

**服务重载**：

```bash
# 系统会执行
nginx -s reload
```

**批量操作**：

- 支持对多个配置文件批量测试
- 支持多环境同步部署

## 🔧 高级配置

### 性能优化

**SSH 连接池配置**：

```python
# app/services/ssh_pool.py
class SSHConnectionPool:
    def __init__(self, max_connections: int = 10, connection_timeout: int = 300):
        self.max_connections = max_connections        # 最大连接数
        self.connection_timeout = connection_timeout  # 连接超时时间（秒）
```

**数据库优化**：

```env
# .env 文件中添加
DATABASE_POOL_SIZE=10
DATABASE_MAX_OVERFLOW=20
DATABASE_POOL_TIMEOUT=30
```

### 安全配置

**SSL/HTTPS 配置**：

```bash
# 使用 SSL 证书
uvicorn app.main:app \
  --host 0.0.0.0 \
  --port 443 \
  --ssl-keyfile /path/to/private.key \
  --ssl-certfile /path/to/certificate.crt
```

**防火墙配置**：

```bash
# 开放必要端口
sudo ufw allow 8000/tcp    # HTTP 端口
sudo ufw allow 443/tcp     # HTTPS 端口
sudo ufw allow 22/tcp      # SSH 端口
```

### 监控和日志

**日志配置**：

```python
# app/core/config.py
import logging

# 配置日志级别
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/var/log/nginx_manager/app.log'),
        logging.StreamHandler()
    ]
)
```

**系统监控**：

- 使用 `htop` 或 `top` 监控系统资源
- 使用 `nginx -t` 定期检查配置文件语法
- 配置数据库连接监控

## 🔍 故障排除

### 常见问题

**1. SSH 连接失败**

```bash
# 检查 SSH 服务状态
sudo systemctl status ssh

# 检查 SSH 配置
sudo nano /etc/ssh/sshd_config
# 确保开启 PubkeyAuthentication yes

# 检查公钥权限
chmod 600 ~/.ssh/authorized_keys
chmod 700 ~/.ssh
```

**2. 数据库连接错误**

```bash
# 检查 MySQL 服务
sudo systemctl status mysql

# 测试数据库连接
mysql -u nginx_user -p -h localhost nginx_manager

# 检查用户权限
SHOW GRANTS FOR 'nginx_user'@'localhost';
```

**3. 权限错误**

```bash
# 检查文件权限
ls -la /etc/nginx/

# 修正文件所有者
sudo chown -R nginx_user:nginx_user /etc/nginx/
sudo chmod -R 644 /etc/nginx/
sudo chmod 755 /etc/nginx/
```

**4. 端口占用**

```bash
# 检查端口使用情况
sudo netstat -tlnp | grep 8000
sudo lsof -i :8000

# 终止占用进程
sudo kill -9 <PID>
```

### 日志检查

```bash
# 应用日志
tail -f /var/log/nginx_manager/app.log

# Nginx 日志
sudo tail -f /var/log/nginx/error.log
sudo tail -f /var/log/nginx/access.log

# 系统日志
sudo journalctl -u nginx_manager -f
```

## 🛠️ 开发指南

### 项目结构

```
nginx_manager/
├── app/
│   ├── core/          # 核心配置模块
│   ├── models/        # 数据库模型
│   ├── routers/       # API 路由
│   ├── services/      # 业务逻辑层
│   ├── static/        # 静态资源
│   ├── templates/     # HTML 模板
│   └── main.py        # 应用入口
├── alembic/           # 数据库迁移
├── requirements.txt   # Python 依赖
└── README.md         # 项目文档
```

### 数据库迁移

```bash
# 创建迁移文件
alembic revision --autogenerate -m "描述信息"

# 应用迁移
alembic upgrade head

# 回滚迁移
alembic downgrade -1

# 查看迁移历史
alembic history
```

### API 文档

应用启动后，可以访问自动生成的 API 文档：

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

### 测试

```bash
# 安装测试依赖
pip install pytest pytest-asyncio httpx

# 运行测试
pytest tests/ -v

# 生成测试覆盖率报告
pip install coverage
coverage run -m pytest
coverage report
coverage html
```

## 📝 更新日志

### v1.0.0 (2025-08-27)

- ✅ 初始版本发布
- ✅ 多环境 Nginx 配置管理
- ✅ SSH 连接池优化，性能提升 95%+
- ✅ 用户权限管理系统
- ✅ 可视化配置编辑器
- ✅ 实时配置同步
- ✅ 响应式用户界面

## 🤝 贡献指南

欢迎贡献代码、报告问题或提出新功能建议！

1. Fork 项目
2. 创建特性分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 开启 Pull Request

## 📜 许可证

本项目采用 MIT 许可证 - 详见 LICENSE 文件

## ℹ️ 联系方式

- **项目主页**: [GitHub Repository](#)
- **问题反馈**: [Issues](#)
- **技术文档**: [Wiki](#)

---

<div align="center">
  <p>感谢使用 Nginx 配置管理平台！</p>
  <p>如果这个项目对您有帮助，请给我们一个 ⭐ Star!</p>
</div>
