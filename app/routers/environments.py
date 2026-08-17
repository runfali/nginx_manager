from fastapi import APIRouter, Depends, HTTPException, status, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session
from typing import List, Optional

from app.core.database import get_db
from app.models.environment import Environment
from app.routers.auth import get_current_active_user, get_current_superuser
from app.models.user import User
from app.core.templates import templates

router = APIRouter()


# 环境列表页面 - 所有已登录用户可访问
@router.get("/", response_class=HTMLResponse)
async def environments_page(
    request: Request,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    # 获取所有环境
    environments = db.query(Environment).all()

    # 如果不是超级用户，过滤掉PRD环境
    if not current_user.is_superuser:
        environments = Environment.filter_prd(environments)

    return templates.TemplateResponse(
        "environments.html",
        {
            "request": request,
            "environments": environments,
            "current_user": current_user,
        },
    )


# 创建环境页面 - 仅超级管理员可访问
@router.get("/create", response_class=HTMLResponse)
async def create_environment_page(
    request: Request, current_user: User = Depends(get_current_superuser)
):
    return templates.TemplateResponse(
        "environment_create.html", {"request": request, "current_user": current_user}
    )


# 创建环境处理 - 仅超级管理员可访问
@router.post("/create")
async def create_environment(
    request: Request,
    name: str = Form(...),
    description: Optional[str] = Form(None),
    server_ip: str = Form(...),
    ssh_port: int = Form(22),
    nginx_path: str = Form("/etc/nginx"),
    is_active: bool = Form(True),
    current_user: User = Depends(get_current_superuser),
    db: Session = Depends(get_db),
):
    # 检查环境名称是否已存在
    db_env = db.query(Environment).filter(Environment.name == name).first()
    if db_env:
        return templates.TemplateResponse(
            "environment_create.html",
            {
                "request": request,
                "error": "环境名称已存在",
                "current_user": current_user,
            },
        )

    # 创建新环境
    new_env = Environment(
        name=name,
        description=description,
        server_ip=server_ip,
        ssh_port=ssh_port,
        nginx_path=nginx_path,
        is_active=is_active,
    )

    db.add(new_env)
    db.commit()
    db.refresh(new_env)

    return RedirectResponse(url="/environments", status_code=status.HTTP_302_FOUND)


# 编辑环境页面 - 仅超级管理员可访问
@router.get("/{env_id}/edit", response_class=HTMLResponse)
async def edit_environment_page(
    request: Request,
    env_id: int,
    current_user: User = Depends(get_current_superuser),
    db: Session = Depends(get_db),
):
    env = db.query(Environment).filter(Environment.id == env_id).first()
    if not env:
        raise HTTPException(status_code=404, detail="环境不存在")

    return templates.TemplateResponse(
        "environment_edit.html",
        {"request": request, "environment": env, "current_user": current_user},
    )


# 更新环境处理 - 仅超级管理员可访问
@router.post("/{env_id}/edit")
async def update_environment(
    request: Request,
    env_id: int,
    name: str = Form(...),
    description: Optional[str] = Form(None),
    server_ip: str = Form(...),
    ssh_port: int = Form(22),
    nginx_path: str = Form("/etc/nginx"),
    is_active: bool = Form(True),
    current_user: User = Depends(get_current_superuser),
    db: Session = Depends(get_db),
):
    env = db.query(Environment).filter(Environment.id == env_id).first()
    if not env:
        raise HTTPException(status_code=404, detail="环境不存在")

    # 检查环境名称是否已被其他环境使用
    db_env = (
        db.query(Environment)
        .filter(Environment.name == name, Environment.id != env_id)
        .first()
    )
    if db_env:
        return templates.TemplateResponse(
            "environment_edit.html",
            {
                "request": request,
                "environment": env,
                "error": "环境名称已存在",
                "current_user": current_user,
            },
        )

    # 更新环境信息
    env.name = name
    env.description = description
    env.server_ip = server_ip
    env.ssh_port = ssh_port
    env.nginx_path = nginx_path
    env.is_active = is_active

    db.commit()
    db.refresh(env)

    return RedirectResponse(url="/environments", status_code=status.HTTP_302_FOUND)


# 删除环境 - 仅超级管理员可访问
@router.get("/{env_id}/delete")
async def delete_environment(
    env_id: int,
    current_user: User = Depends(get_current_superuser),
    db: Session = Depends(get_db),
):
    env = db.query(Environment).filter(Environment.id == env_id).first()
    if not env:
        raise HTTPException(status_code=404, detail="环境不存在")

    db.delete(env)
    db.commit()

    return RedirectResponse(url="/environments", status_code=status.HTTP_302_FOUND)
