from fastapi import APIRouter, Depends, HTTPException, status, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session
from typing import List, Optional

from app.core.database import get_db
from app.core.security import (
    get_password_hash,
    verify_password,
    encrypt_private_key,
)
from app.models.user import User
from app.routers.auth import get_current_active_user, get_current_superuser
from app.core.templates import templates

router = APIRouter()


# 用户列表页面 - 仅超级管理员可访问
@router.get("/", response_class=HTMLResponse)
async def users_page(
    request: Request,
    current_user: User = Depends(get_current_superuser),
    db: Session = Depends(get_db),
):
    users = db.query(User).all()
    return templates.TemplateResponse(
        "users.html", {"request": request, "users": users, "current_user": current_user}
    )


# 创建用户页面 - 仅超级管理员可访问
@router.get("/create", response_class=HTMLResponse)
async def create_user_page(
    request: Request, current_user: User = Depends(get_current_superuser)
):
    return templates.TemplateResponse(
        "user_create.html", {"request": request, "current_user": current_user}
    )


# 创建用户处理 - 仅超级管理员可访问
@router.post("/create")
async def create_user(
    request: Request,
    username: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    is_superuser: bool = Form(False),
    ssh_private_key: Optional[str] = Form(None),
    current_user: User = Depends(get_current_superuser),
    db: Session = Depends(get_db),
):
    # 检查用户名是否已存在
    db_user = db.query(User).filter(User.username == username).first()
    if db_user:
        return templates.TemplateResponse(
            "user_create.html",
            {"request": request, "error": "用户名已存在", "current_user": current_user},
        )

    # 检查邮箱是否已存在
    db_email = db.query(User).filter(User.email == email).first()
    if db_email:
        return templates.TemplateResponse(
            "user_create.html",
            {"request": request, "error": "邮箱已存在", "current_user": current_user},
        )

    # 创建新用户
    hashed_password = get_password_hash(password)
    new_user = User(
        username=username,
        email=email,
        hashed_password=hashed_password,
        is_superuser=is_superuser,
        ssh_private_key=encrypt_private_key(ssh_private_key),
    )

    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    return RedirectResponse(url="/users", status_code=status.HTTP_302_FOUND)


# 编辑用户页面 - 仅超级管理员可访问
@router.get("/{user_id}/edit", response_class=HTMLResponse)
async def edit_user_page(
    request: Request,
    user_id: int,
    current_user: User = Depends(get_current_superuser),
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")

    return templates.TemplateResponse(
        "user_edit.html",
        {"request": request, "user": user, "current_user": current_user},
    )


# 更新用户处理 - 仅超级管理员可访问
@router.post("/{user_id}/edit")
async def update_user(
    request: Request,
    user_id: int,
    email: str = Form(...),
    password: Optional[str] = Form(None),
    is_active: bool = Form(True),
    is_superuser: bool = Form(False),
    ssh_private_key: Optional[str] = Form(None),
    current_user: User = Depends(get_current_superuser),
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")

    # 检查邮箱是否已被其他用户使用
    db_email = db.query(User).filter(User.email == email, User.id != user_id).first()
    if db_email:
        return templates.TemplateResponse(
            "user_edit.html",
            {
                "request": request,
                "user": user,
                "error": "邮箱已存在",
                "current_user": current_user,
            },
        )

    # 更新用户信息
    user.email = email
    user.is_active = is_active
    user.is_superuser = is_superuser
    user.ssh_private_key = encrypt_private_key(ssh_private_key)

    # 如果提供了新密码，则更新密码
    if password:
        user.hashed_password = get_password_hash(password)

    db.commit()
    db.refresh(user)

    return RedirectResponse(url="/users", status_code=status.HTTP_302_FOUND)


# 删除用户 - 仅超级管理员可访问
@router.get("/{user_id}/delete")
async def delete_user(
    user_id: int,
    current_user: User = Depends(get_current_superuser),
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")

    # 不允许删除自己
    if user.id == current_user.id:
        raise HTTPException(status_code=400, detail="不能删除当前登录的用户")

    db.delete(user)
    db.commit()

    return RedirectResponse(url="/users", status_code=status.HTTP_302_FOUND)


# 个人资料页面 - 已登录用户可访问
@router.get("/profile", response_class=HTMLResponse)
async def profile_page(
    request: Request, current_user: User = Depends(get_current_active_user)
):
    return templates.TemplateResponse(
        "profile.html", {"request": request, "current_user": current_user}
    )


# 更新个人资料 - 已登录用户可访问
@router.post("/profile")
async def update_profile(
    request: Request,
    email: str = Form(...),
    current_password: Optional[str] = Form(None),
    new_password: Optional[str] = Form(None),
    ssh_private_key: Optional[str] = Form(None),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    # 检查邮箱是否已被其他用户使用
    db_email = (
        db.query(User).filter(User.email == email, User.id != current_user.id).first()
    )
    if db_email:
        return templates.TemplateResponse(
            "profile.html",
            {"request": request, "error": "邮箱已存在", "current_user": current_user},
        )

    # 如果提供了当前密码和新密码，则验证并更新密码
    if current_password and new_password:
        if not verify_password(current_password, current_user.hashed_password):
            return templates.TemplateResponse(
                "profile.html",
                {
                    "request": request,
                    "error": "当前密码错误",
                    "current_user": current_user,
                },
            )
        current_user.hashed_password = get_password_hash(new_password)

    # 更新用户信息
    current_user.email = email
    current_user.ssh_private_key = encrypt_private_key(ssh_private_key)

    db.commit()
    db.refresh(current_user)

    return RedirectResponse(url="/users/profile", status_code=status.HTTP_302_FOUND)
