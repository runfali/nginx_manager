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
- **版本历史与回滚**：每次保存自动留存快照，可查看任意两版差异并一键回滚（保留当前 + 最近 7 个历史）

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
- **Nginx 版本**: 1.18+ (支持`nginx -t`和`nginx -s reload`命令)
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

# 5. 创建初始迁移并初始化数据库
alembic revision --autogenerate -m "init"
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

# JWT 安全配置（SECRET_KEY 必配）
# 生成强随机密钥：python -c "import secrets; print(secrets.token_hex(32))"
# 未配置或仍为示例占位值时应用会每次启动随机生成，重启后所有登录会话失效
SECRET_KEY=<用上面的命令生成，切勿使用任何示例值>
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

> **安全注意**：生产环境务必在 `.env` 中配置固定的强随机 `SECRET_KEY`（运行时随机生成仅供兜底——重启会让所有会话失效），并将 `DEBUG=false`。数据库请使用最小权限专用账号；凭据只放 `.env`（已被 .gitignore 忽略），严禁提交进仓库或硬编码在代码里。可参考仓库根目录的 `.env.example` 模板。

**数据库初始化**：

```bash
# 创建数据库（MySQL）
mysql -u root -p
CREATE DATABASE nginx_manager CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
GRANT ALL PRIVILEGES ON nginx_manager.* TO 'nginx_user'@'localhost' IDENTIFIED BY 'your_password';
FLUSH PRIVILEGES;
EXIT;

# 创建初始迁移并应用
alembic revision --autogenerate -m "init"
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
- 在用户 Profile 页面中上传对应的私钥（AES-256-CBC 加密存储）

### 2. 用户管理

**创建用户**：

- 超级管理员可以创建和管理用户
- 支持普通用户和管理员两种角色
- 每个用户可以设置独立的 SSH 私钥

**权限控制**：

- **超级管理员**：所有功能和环境访问权限
- **普通用户**：仅可访问非生产环境，无用户管理权限；可访问自己的 Profile 页面配置 SSH 私钥

### 3. 配置管理

路由拆分为四个模块：

| 路径 | 功能 | 说明 |
|------|------|------|
| `/configs` | 配置列表 | 重定向到仪表盘 |
| `/configs/browse` | 浏览编辑 | 目录导航、文件编辑 |
| `/configs/sync` | 配置同步 | 上传/下载同步 |
| `/configs/ops` | 配置操作 | 测试、重载、删除 |

#### 版本历史与回滚

配置文件详情页下方提供「历史版本」卡片，记录每次内容变更：

- **自动留档**：新建、编辑保存、目录同步写入、回滚本身都会生成一条版本快照（内容无变化时不留档）
- **保留策略**：保留当前内容 + 最近 7 个历史版本（共 8 条），版本号在裁剪后继续递增，不复用
- **查看变更**：`查看变更` 进入差异页，unified diff 展示红删绿增，可在「对比上一版本 / 对比当前版本」之间切换
- **一键回滚**：采用 revert 语义——把旧版本内容写回当前配置并追加一条 `回滚` 版本，历史记录不会被删除，因此回滚操作本身也可追溯
- **重要**：回滚只更新数据库中的配置内容，**不会自动上传到服务器、也不会自动重载 nginx**；如需生效请再点「重载配置」（该操作会先执行 `nginx -t` 语法测试）

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

连接池内置心跳检测——每次复用时执行 `echo ok` 验证连接有效性，失效连接自动回收重建。应用 Shutdown 时调用 `close_all()` 关闭所有连接并清理临时私钥文件；`atexit` 注册兜底清理，防止进程异常退出时残留临时文件。

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

**SSH 私钥加密**：

用户的 SSH 私钥在数据库中采用 AES-256-CBC 加密存储（先经过 zlib 压缩，再使用 PKCS7 填充后加密），密钥由 `SECRET_KEY` 通过 PBKDF2HMAC（SHA-256, 480000 次迭代）派生，杜绝明文存储风险。

**登录暴力破解防护**：

同一来源 IP 对同一用户名的登录尝试（`/auth/login` 与 `/auth/token` 共用计数），在 15 分钟窗口内失败满 10 次后会被暂时拒绝（429），成功登录即清零。该限流为进程内存实现，应用重启后清零；Gunicorn 多 Worker 部署时各 Worker 独立计数（等效阈值随 Worker 数放大）。

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

日志在 `app/main.py` 入口处统一初始化，输出到 `app.log` 文件和控制台：

```python
# app/main.py
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler("app.log"), logging.StreamHandler()],
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
│   ├── core/           # 核心配置模块
│   │   ├── config.py
│   │   ├── database.py
│   │   ├── middleware.py
│   │   ├── security.py
│   │   └── templates.py
│   ├── models/         # 数据库模型
│   ├── routers/        # API 路由
│   │   ├── nginx/      # Nginx 操作子路由
│   │   │   ├── dashboard.py    # 仪表盘
│   │   │   ├── directory.py    # 目录浏览 (/configs/browse)
│   │   │   ├── sync.py         # 配置同步 (/configs/sync)
│   │   │   └── operations.py   # 配置操作 (/configs/ops)
│   │   ├── auth.py
│   │   ├── configs.py
│   │   ├── environments.py
│   │   ├── users.py
│   │   └── api.py
│   ├── services/       # 业务逻辑层
│   │   ├── nginx_sync.py       # 配置同步服务
│   │   ├── config_versions.py  # 配置版本快照与差异
│   │   ├── ssh_pool.py         # SSH 连接池
│   │   └── ssh_utils.py        # SSH 工具类
│   ├── static/         # 静态资源
│   ├── templates/      # HTML 模板
│   ├── init_superuser.py
│   └── main.py         # 应用入口（含日志初始化）
├── alembic/            # 数据库迁移
├── .gitignore
├── requirements.txt    # Python 依赖
└── README.md           # 项目文档
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

> **注意**：`tests/` 目录尚不存在，测试模块规划中。

```bash
# 安装测试依赖
pip install pytest pytest-asyncio httpx

# 运行测试（预留）
pytest tests/ -v

# 生成测试覆盖率报告
pip install coverage
coverage run -m pytest
coverage report
coverage html
```

## 📝 更新日志

### v1.3.0 (2026-11-25)

- 🕘 新增配置版本历史与一键回滚（新建/编辑/同步/回滚四个捕获点，保留当前 + 7 个历史）
- 🔍 新增版本差异页（unified diff 红删绿增，支持对比上一版本 / 对比当前版本）
- ⚠️ 回滚仅回滚配置内容，不自动上传与重载，页面明确提示需手动重载

### v1.2.0 (2026-11-XX)

- 🔒 安全审计加固：SECRET_KEY 空值/占位值自动生成随机密钥并告警；登录拒绝禁用账户
- 🛡️ PRD 环境仅超级管理员可访问（服务端强制 403）；删除等敏感操作改为 POST 表单
- 🚦 新增登录暴力破解限流（15 分钟窗口 10 次失败锁定，成功清零）
- 🔄 恢复 URL 直链快速登录（/auth/login?username=xxx&password=xxx，内网快捷入口；已并入限流、禁用账户检查与会话管理加固）
- 🐛 修复全新数据库初始化漏建表问题（create_all 移至全部模型导入后执行）
- ✅ Nginx 重载前自动执行 `nginx -t` 语法测试，测试失败取消重载
- 🧹 清理死代码：移除未被引用的 nginx_service.py 与 ssh_utils.py 冗余方法
- 🗄️ `users.ssh_private_key` 列改为 TEXT（存量库执行：`ALTER TABLE users MODIFY ssh_private_key TEXT;`）
- 🔐 备份命令注入修复、上传路径校验、alembic 凭据出仓（连接串走 `.env`）；新增 `.env.example`

### v1.1.0 (2025-07-XX)

- 🔒 SSH 私钥改为 AES-256-CBC 加密存储（zlib 压缩），不再明文保存
- 🔧 连接池新增心跳检测，自动回收失效连接
- 🧹 新增 atexit 临时文件清理 + Shutdown 完整清理
- 🛣️ /configs 路由拆分为 /configs/browse（浏览编辑）、/configs/sync（同步）、/configs/ops（操作）、/configs（配置列表）
- 📦 新增 app/services/nginx_service.py 部署服务模块
- 🚫 新增 .gitignore（.env、__pycache__、app.log 等）
- 📖 日志配置统一迁移到 main.py 入口
- 🧪 tests/ 目录规划中，尚未实现

### v1.0.0 (2025-01-XX)

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
