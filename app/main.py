from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.staticfiles import StaticFiles
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
import os
from pathlib import Path

from app.core.config import settings
from app.core.database import engine, Base, get_db
from app.models import user, environment
from app.core.middleware import ErrorHandlerMiddleware

# 创建FastAPI应用实例
app = FastAPI(
    title=settings.APP_NAME,
    description=settings.APP_DESCRIPTION,
    version=settings.APP_VERSION,
    debug=settings.DEBUG,
)

# 添加错误处理中间件
app.add_middleware(ErrorHandlerMiddleware)

# 创建数据库表
Base.metadata.create_all(bind=engine)

# 设置静态文件目录
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# 导入路由
from app.routers import auth, users, environments, configs, api
from app.routers.nginx import dashboard, directory, sync, operations

# 注册路由
app.include_router(auth.router, prefix="/auth", tags=["认证"])
app.include_router(users.router, prefix="/users", tags=["用户管理"])
app.include_router(environments.router, prefix="/environments", tags=["环境管理"])
app.include_router(dashboard.router, prefix="/dashboard", tags=["仪表盘"])
app.include_router(directory.router, prefix="/configs", tags=["目录浏览"])
app.include_router(sync.router, prefix="/configs", tags=["配置同步"])
app.include_router(operations.router, prefix="/configs", tags=["操作管理"])
# 确保具体路径的路由在参数路径的路由之前注册
app.include_router(configs.router, prefix="/configs", tags=["配置管理"])
app.include_router(api.router)


@app.on_event("startup")
async def startup_event():
    # 应用启动时的初始化操作
    pass


@app.on_event("shutdown")
async def shutdown_event():
    # 应用关闭时清理资源
    engine.dispose()


# 根路由重定向到登录页面
@app.get("/")
async def root():
    from fastapi.responses import RedirectResponse

    return RedirectResponse(url="/auth/login")


# 启动应用
if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
