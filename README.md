# Nginx 配置管理平台

[![Python](https://img.shields.io/badge/Python-3.8%2B-blue)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.104.1-green)](https://fastapi.tiangolo.com/)

一个基于 FastAPI 的多环境 Nginx 配置管理平台，提供用户认证、环境管理、目录浏览、配置同步、在线编辑、配置测试和 Nginx 重载能力。

## 项目现状

当前仓库中的实现重点是：

- 基于 `FastAPI + Jinja2` 的服务端渲染管理后台
- 基于 `JWT + HttpOnly Cookie` 的登录认证
- 用户、环境、Nginx 配置三类核心数据管理
- 通过 SSH 连接远程服务器，浏览和同步 `.conf` 文件
- 在线编辑配置，并在远程服务器执行 `nginx -t`、`nginx -s reload`
- 用户 SSH 私钥加密存储
- SSH 连接池复用、心跳检测和临时私钥文件清理

当前代码里没有现成的 `tests/` 目录，也没有提交好的 Alembic 迁移版本文件；数据库表主要依赖应用启动时的 `Base.metadata.create_all()` 创建。

## 核心能力

### 1. 多环境管理

- 超级管理员可创建、编辑、删除环境
- 环境信息包含名称、描述、服务器 IP、SSH 端口、Nginx 根路径、启用状态
- 普通用户可查看环境，但会被过滤掉名称中包含 `PRD` 的环境

### 2. 用户与权限

- 支持登录、登出、个人资料维护
- 超级管理员可管理用户
- 普通用户不能访问用户管理页面，且在界面层面会被过滤掉名称中包含 `PRD` 的环境和相关配置
- 用户可以在个人资料页维护 SSH 私钥

### 3. 配置浏览与编辑

- 仪表盘展示可用环境和最近更新的配置
- 可按环境浏览远程 Nginx 目录
- 目录页只展示目录和 `.conf` 文件
- 支持创建、查看、编辑、删除配置
- 编辑器使用 CodeMirror，提供 Nginx 语法高亮

### 4. 远程同步与操作

- 支持同步某个环境下指定目录的全部 `.conf` 文件
- 支持同步单个远程配置文件到数据库
- 新建配置时会上传到远程目标路径
- 编辑保存时主要更新数据库记录
- 执行测试或重载前测试时，会把当前配置内容上传到远程目标路径
- 支持对配置执行 `nginx -t`
- 支持先测试再执行 `nginx -s reload`
- 编辑保存或删除配置时，会在服务器上创建备份

## 技术栈

### 后端

- FastAPI
- SQLAlchemy
- Pydantic / pydantic-settings
- Alembic
- Paramiko
- python-jose
- passlib + bcrypt
- cryptography

### 前端

- Jinja2
- Bootstrap 5
- Font Awesome
- CodeMirror
- 原生 JavaScript

### 数据与连接

- MySQL / MariaDB
- SSH 私钥认证
- SSH 连接池复用

## 运行要求

### 管理平台本身

- Python 3.8+
- MySQL 5.7+ 或 MariaDB 10.3+
- Windows / Linux / macOS 可运行 Web 应用本体

### 被管理的 Nginx 服务器

这部分要求要比旧版 README 更明确：

- 需要可通过 SSH 访问
- 当前代码中的 SSH 用户名写死为 `root`
- 需要支持公钥认证
- 需要可执行以下命令：
  - `find`
  - `mkdir`
  - `cp`
  - `nginx -t`
  - `nginx -s reload`
- 目标路径需要允许 `root` 读取和写入 Nginx 配置文件

也就是说，远程服务器默认按 Linux/类 Unix 环境设计，不是面向 Windows Nginx 主机的实现。

## 目录结构

```text
nginx_manager/
├── app/
│   ├── core/
│   │   ├── config.py
│   │   ├── database.py
│   │   ├── middleware.py
│   │   ├── security.py
│   │   └── templates.py
│   ├── models/
│   │   ├── environment.py
│   │   ├── nginx_config.py
│   │   └── user.py
│   ├── routers/
│   │   ├── nginx/
│   │   │   ├── dashboard.py
│   │   │   ├── directory.py
│   │   │   ├── operations.py
│   │   │   └── sync.py
│   │   ├── api.py
│   │   ├── auth.py
│   │   ├── configs.py
│   │   ├── environments.py
│   │   └── users.py
│   ├── services/
│   │   ├── nginx_service.py
│   │   ├── nginx_sync.py
│   │   ├── ssh_pool.py
│   │   └── ssh_utils.py
│   ├── static/
│   ├── templates/
│   ├── init_superuser.py
│   └── main.py
├── alembic/
├── requirements.txt
└── README.md
```

## 环境变量

项目当前实际读取的环境变量如下，定义位置在 `app/core/config.py`：

```env
DATABASE_URL=mysql+pymysql://user:password@localhost:3306/nginx_manager
SECRET_KEY=your-secret-key-for-jwt-token-generation
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30

APP_NAME=Nginx配置管理平台
APP_VERSION=0.1.0
APP_DESCRIPTION=用于管理多环境Nginx配置的Web平台
DEBUG=true
```

说明：

- `SECRET_KEY` 同时用于 JWT 签名和 SSH 私钥加密密钥派生
- 生产环境务必替换默认 `SECRET_KEY`
- 当前代码未从 `.env` 读取 `HOST`、`PORT` 等运行参数，启动地址由 `uvicorn` 命令决定

## 安装与启动

### 1. 安装依赖

```bash
git clone <repository-url>
cd nginx_manager

python -m venv venv

# Windows
venv\Scripts\activate

# Linux / macOS
source venv/bin/activate

pip install -r requirements.txt
```

### 2. 创建数据库

先在 MySQL 中手动创建数据库，例如：

```sql
CREATE DATABASE nginx_manager CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

然后在项目根目录创建 `.env`，至少配置好：

```env
DATABASE_URL=mysql+pymysql://username:password@localhost:3306/nginx_manager
SECRET_KEY=please-change-this-in-production
```

### 3. 初始化数据表

当前仓库虽然包含 Alembic 脚手架，但**没有提交迁移版本文件**。  
按现有代码，最直接的初始化方式是让应用在启动时自动建表，或运行超级管理员初始化脚本时创建表：

```bash
python -m app.init_superuser
```

脚本会提示输入：

- 用户名
- 邮箱
- 密码

如果表不存在，脚本会先调用 `Base.metadata.create_all()`。

### 4. 启动应用

开发环境推荐：

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

也可以直接运行：

```bash
python -m app.main
```

启动后访问：

```text
http://localhost:8000
```

根路径会自动跳转到 `/auth/login`。

## 首次使用流程

1. 用超级管理员账户登录
2. 进入“个人资料”页面，保存 SSH 私钥
3. 进入“环境管理”创建目标服务器环境
4. 在仪表盘选择环境，进入目录浏览
5. 同步现有 `.conf` 文件，或直接新建配置
6. 编辑配置后，先执行测试或重载前测试，再执行重载

## 主要页面与路由

| 路径 | 说明 |
| --- | --- |
| `/` | 跳转到登录页 |
| `/auth/login` | 登录页 |
| `/dashboard` | 仪表盘 |
| `/users` | 用户管理，超级管理员可访问 |
| `/users/profile` | 个人资料页 |
| `/environments` | 环境管理 |
| `/configs` | 当前会重定向到仪表盘 |
| `/configs/browse/browse/{env_id}` | 远程目录浏览 |
| `/configs/browse/create/{env_id}` | 新建配置 |
| `/configs/browse/view/{config_id}` | 查看配置 |
| `/configs/browse/view/{config_id}/edit` | 编辑配置 |
| `/configs/sync/{env_id}` | 同步目录下配置 |
| `/configs/sync/file/{env_id}` | 同步单个文件 |
| `/configs/ops/{config_id}/test` | 测试配置 |
| `/configs/ops/{config_id}/reload-test` | 重载前测试 |
| `/configs/ops/{config_id}/reload-exec` | 执行重载 |
| `/docs` | Swagger UI |
| `/redoc` | ReDoc |

## 实现细节说明

### 认证方式

- 登录成功后，服务端将 JWT 写入名为 `access_token` 的 Cookie
- 路由鉴权主要从 Cookie 中读取令牌

### SSH 私钥存储

- 私钥不会明文存储
- 当前实现会先压缩，再使用 `AES-256-CBC` 加密
- 加密密钥由 `SECRET_KEY` 通过 `PBKDF2HMAC(SHA-256, 480000 次迭代)` 派生

### SSH 连接池

- 全局连接池位于 `app/services/ssh_pool.py`
- 默认最大连接数为 `10`
- 连接空闲超时时间为 `300` 秒
- 连接复用前会执行 `echo ok` 检测可用性
- 临时私钥文件会在连接关闭、应用关闭和进程退出时尽量清理

### 同步和编辑行为

- 同步目录时，远程执行 `find -L <path> -type f -name '*.conf'`
- 目录页只显示目录和 `.conf` 文件
- 新建配置时会上传远程文件并设置权限为 `644`
- 编辑保存时会更新数据库记录，但不会直接把新内容写回远程文件
- 执行“测试配置”或“重载前测试”时，会先把当前数据库中的配置内容上传到远程目标路径
- 如果远程文件已存在，保存前会先备份到 `/usr/local/src/nginx_config_backups`
- 删除配置时，如果远程文件存在，也会先做备份

## Alembic 说明

当前仓库状态下：

- 有 `alembic.ini`
- 有 `alembic/env.py`
- 没有已提交的 `alembic/versions/*` 迁移文件

所以这里不建议把 `alembic upgrade head` 写成“首次安装必走步骤”。  
如果后续要正式采用迁移流程，应先生成并提交版本文件，再在 README 中补上标准迁移命令。

## 开发说明

- 当前 `app/main.py` 在启动时会执行 `Base.metadata.create_all(bind=engine)`
- 日志输出到控制台和项目根目录下的 `app.log`
- 全局异常处理在 `app/core/middleware.py`
- 仓库当前没有自动化测试目录，关键改动建议手工验证：
  - 登录
  - 用户资料更新
  - 环境创建
  - 目录浏览
  - 配置同步
  - `nginx -t`
  - `nginx -s reload`

## 已知边界

- SSH 用户名当前写死为 `root`
- 普通用户是否可访问生产环境，是通过环境名是否包含 `PRD` 判断的
- 远程命令依赖 Linux/类 Unix 工具链
- 当前没有提交数据库迁移版本文件
- 当前没有自动化测试

## 许可证

本项目采用 MIT License。
