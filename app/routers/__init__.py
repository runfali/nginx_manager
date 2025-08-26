from fastapi import APIRouter
from app.routers import auth, users, environments, configs

router = APIRouter()

# 注册认证路由
router.include_router(auth.router, tags=["auth"])

# 注册用户管理路由
router.include_router(users.router, prefix="/users", tags=["users"])

# 注册环境管理路由
router.include_router(
    environments.router, prefix="/environments", tags=["environments"]
)

# 注册Nginx配置管理路由
router.include_router(configs.router, prefix="/configs", tags=["configs"])
