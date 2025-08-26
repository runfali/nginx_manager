# Nginx配置管理平台

一个用于管理多环境Nginx配置的Web平台，基于FastAPI框架开发。

## 功能特点

- 多环境Nginx配置管理
- 用户权限管理
- Nginx配置同步
- 配置文件浏览与编辑
- 操作审计日志

## 环境要求

- Python 3.8+
- MySQL数据库
- Nginx服务器

## 安装步骤

### 1. 克隆代码库

```bash
git clone <repository-url>
cd nginx_manager
```

### 2. 创建虚拟环境（推荐）

```bash
python -m venv venv

# Windows激活虚拟环境
venv\Scripts\activate

# Linux/Mac激活虚拟环境
source venv/bin/activate
```

### 3. 安装依赖

```bash
pip install -r requirements.txt
```

### 4. 配置数据库

在项目根目录创建`.env`文件，配置数据库连接信息：

```
DATABASE_URL=mysql+pymysql://username:password@host/database_name
SECRET_KEY=your-secret-key-for-jwt-token-generation
ACCESS_TOKEN_EXPIRE_MINUTES=30
DEBUG=true
```

默认配置位于`app/core/config.py`文件中，可根据需要修改。

### 5. 初始化数据库

使用Alembic进行数据库迁移：

```bash
alembic upgrade head
```

## 创建超级管理员用户

运行以下命令创建超级管理员账户：

```bash
python -m app.init_superuser
```

按照提示输入用户名、邮箱和密码。

## 启动应用

### 开发环境

```bash
python -m app.main
```

或者使用uvicorn直接启动：

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### 生产环境

在生产环境中，建议使用Gunicorn作为WSGI服务器：

```bash
gunicorn -w 4 -k uvicorn.workers.UvicornWorker app.main:app --bind 0.0.0.0:8000
```

## 访问应用

启动应用后，在浏览器中访问：

```
http://localhost:8000
```

默认会重定向到登录页面，使用之前创建的超级管理员账户登录。

## 基本使用

1. **环境管理**：添加和配置不同的Nginx服务器环境
2. **用户管理**：创建和管理用户账户及权限
3. **配置管理**：浏览、编辑和同步Nginx配置文件
4. **操作管理**：执行Nginx相关操作（如测试配置、重载服务等）

## 注意事项

- 确保目标Nginx服务器允许SSH连接
- 确保数据库连接信息正确
- 生产环境中应修改默认的SECRET_KEY