from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from sqlalchemy.orm import Session
from typing import List, Optional

from app.core.database import get_db
from app.models.nginx_config import NginxConfig
from app.models.environment import Environment
from app.models.user import User
from app.routers.auth import get_current_active_user
from app.core.templates import templates
from app.routers.nginx.operations import test_config as nginx_test_config

router = APIRouter()
configs_router = APIRouter()


# 配置列表页面 - 所有已登录用户可访问
@router.get("/", response_class=HTMLResponse)
async def configs_page(
    request: Request,
    environment: Optional[str] = None,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    # 重定向到仪表盘页面
    return RedirectResponse(url="/dashboard", status_code=status.HTTP_302_FOUND)


# 注册配置管理路由
router.include_router(configs_router, prefix="/configs", tags=["configs"])
