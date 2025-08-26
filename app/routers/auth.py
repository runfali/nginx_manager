from fastapi import APIRouter, Depends, HTTPException, status, Request, Form
from fastapi.security import OAuth2PasswordRequestForm, OAuth2PasswordBearer
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session
from datetime import timedelta
import os

from app.core.database import get_db
from app.core.security import verify_password, create_access_token
from app.models.user import User
from app.core.config import settings
from app.core.templates import templates

router = APIRouter()

# OAuth2密码Bearer
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/token")


# 获取当前用户
async def get_current_user(request: Request, db: Session = Depends(get_db)):
    from jose import JWTError, jwt

    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="无效的认证凭据",
        headers={"WWW-Authenticate": "Bearer"},
    )

    # 从cookie中获取token
    token = request.cookies.get("access_token")
    if not token:
        raise credentials_exception

    # 移除Bearer前缀
    if token.startswith("Bearer "):
        token = token[7:]

    try:
        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
        )
        username = payload.get("sub")  # 先不声明类型，使用自动推断
        if not isinstance(username, str):  # 检查是否为字符串类型
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    user = db.query(User).filter(User.username == username).first()
    if user is None:
        raise credentials_exception
    return user


# 获取当前活跃用户
async def get_current_active_user(current_user: User = Depends(get_current_user)):
    if not current_user.is_active:
        raise HTTPException(status_code=400, detail="用户已被禁用")
    return current_user


# 获取当前超级用户
async def get_current_superuser(current_user: User = Depends(get_current_active_user)):
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="权限不足，需要超级管理员权限"
        )
    return current_user


# 登录页面
@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    # 检查是否有URL参数自动登录
    username = request.query_params.get("username")
    password = request.query_params.get("password")

    # 如果提供了用户名和密码，尝试自动登录
    if username and password:
        db = next(get_db())
        user = db.query(User).filter(User.username == username).first()

        if user and verify_password(password, user.hashed_password):
            # 创建访问令牌
            access_token_expires = timedelta(
                minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
            )
            access_token = create_access_token(
                data={"sub": user.username}, expires_delta=access_token_expires
            )

            # 设置Cookie并重定向到仪表盘
            response = RedirectResponse(
                url="/dashboard", status_code=status.HTTP_302_FOUND
            )
            response.set_cookie(
                key="access_token", value=f"Bearer {access_token}", httponly=True
            )
            return response

    # 如果没有参数或验证失败，显示登录页面
    return templates.TemplateResponse("login.html", {"request": request})


# 登录处理
@router.post("/login")
async def login(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.username == username).first()
    if not user or not verify_password(password, user.hashed_password):
        return templates.TemplateResponse(
            "login.html", {"request": request, "error": "用户名或密码错误"}
        )

    # 创建访问令牌
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )

    # 设置Cookie并重定向到仪表盘
    response = RedirectResponse(url="/dashboard", status_code=status.HTTP_302_FOUND)
    response.set_cookie(
        key="access_token", value=f"Bearer {access_token}", httponly=True
    )
    return response


# 令牌获取接口（用于API认证）
@router.post("/token")
async def login_for_access_token(
    form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)
):
    user = db.query(User).filter(User.username == form_data.username).first()
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}


# 登出
@router.get("/logout")
async def logout():
    response = RedirectResponse(url="/auth/login", status_code=status.HTTP_302_FOUND)
    response.delete_cookie(key="access_token")
    return response
