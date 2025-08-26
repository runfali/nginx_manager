from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.nginx_config import NginxConfig
from app.models.environment import Environment
from app.models.user import User
from app.routers.auth import get_current_active_user
from app.core.templates import templates

router = APIRouter()


# 仪表盘页面 - 所有已登录用户可访问
@router.get("/", response_class=HTMLResponse)
async def dashboard_page(
    request: Request,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    # 获取环境列表
    environments = db.query(Environment).filter(Environment.is_active == True).all()

    # 如果不是超级用户，过滤掉PRD环境
    if not current_user.is_superuser:
        environments = [env for env in environments if "PRD" not in env.name.upper()]

    # 获取最近更新的配置文件
    recent_configs = (
        db.query(NginxConfig).order_by(NginxConfig.updated_at.desc()).limit(5).all()
    )

    # 如果不是超级用户，过滤掉PRD环境的配置
    if not current_user.is_superuser:
        recent_configs = [
            config
            for config in recent_configs
            if "PRD" not in config.environment.upper()
        ]

    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "current_user": current_user,
            "environments": environments,
            "recent_configs": recent_configs,
        },
    )
