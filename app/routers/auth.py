from fastapi import APIRouter, Depends, HTTPException, status, Request, Form
from fastapi.security import OAuth2PasswordRequestForm, OAuth2PasswordBearer
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session
from datetime import timedelta
import os
import time
from typing import Dict, List

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
async def login_page(request: Request, db: Session = Depends(get_db)):
    # URL直链快速登录（内网硬性需求：/auth/login?username=xxx&password=xxx）。
    # 已知取舍：密码会进入访问日志/浏览器历史，仅限内网快捷入口使用；
    # 会话由 Depends(get_db) 正常管理，登录走与POST一致的完整校验（禁用账户、限流、samesite）。
    username = request.query_params.get("username")
    password = request.query_params.get("password")

    if username and password:
        client_ip = request.client.host if request.client else "unknown"
        rate_key = f"{client_ip}:{username}"
        if _login_locked(rate_key):
            return templates.TemplateResponse(
                "login.html",
                {"request": request, "error": "登录尝试过于频繁，请15分钟后再试"},
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            )

        user = db.query(User).filter(User.username == username).first()
        if user and verify_password(password, user.hashed_password):
            if not user.is_active:
                return templates.TemplateResponse(
                    "login.html", {"request": request, "error": "用户已被禁用"}
                )
            # 登录成功，清除该账号的失败计数
            _clear_login_failures(rate_key)
            access_token_expires = timedelta(
                minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
            )
            access_token = create_access_token(
                data={"sub": user.username}, expires_delta=access_token_expires
            )
            response = RedirectResponse(
                url="/dashboard", status_code=status.HTTP_302_FOUND
            )
            response.set_cookie(
                key="access_token",
                value=f"Bearer {access_token}",
                httponly=True,
                samesite="lax",
            )
            return response

        # 直链校验失败：记录失败计数后回到登录页（不回显密码）
        _record_login_failure(rate_key)

    return templates.TemplateResponse("login.html", {"request": request})


# 登录处理
@router.post("/login")
async def login(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
):
    # 登录暴力破解防护：同IP+用户名在15分钟窗口内失败满10次后暂时拒绝
    client_ip = request.client.host if request.client else "unknown"
    rate_key = f"{client_ip}:{username}"
    if _login_locked(rate_key):
        return templates.TemplateResponse(
            "login.html",
            {
                "request": request,
                "error": "登录尝试过于频繁，请15分钟后再试",
            },
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        )

    user = db.query(User).filter(User.username == username).first()
    if not user or not verify_password(password, user.hashed_password):
        _record_login_failure(rate_key)
        return templates.TemplateResponse(
            "login.html", {"request": request, "error": "用户名或密码错误"}
        )

    if not user.is_active:
        return templates.TemplateResponse(
            "login.html", {"request": request, "error": "用户已被禁用"}
        )

    # 登录成功，清除该账号的失败计数
    _clear_login_failures(rate_key)

    # 创建访问令牌
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )

    # 设置Cookie并重定向到仪表盘
    response = RedirectResponse(url="/dashboard", status_code=status.HTTP_302_FOUND)
    response.set_cookie(
        key="access_token", value=f"Bearer {access_token}", httponly=True, samesite="lax"
    )
    return response


# 令牌获取接口（用于API认证）
@router.post("/token")
async def login_for_access_token(
    request: Request,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    # 登录暴力破解防护（与 /login 共用同一套计数逻辑）
    client_ip = request.client.host if request.client else "unknown"
    rate_key = f"{client_ip}:{form_data.username}"
    if _login_locked(rate_key):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="登录尝试过于频繁，请15分钟后再试",
        )

    user = db.query(User).filter(User.username == form_data.username).first()
    if not user or not verify_password(form_data.password, user.hashed_password):
        _record_login_failure(rate_key)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="用户已被禁用"
        )

    _clear_login_failures(rate_key)

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


# ---------------------------------------------------------------------------
# 登录暴力破解防护（进程内存实现，重启即清零；仅用于缓解爆破，多Worker部署时各进程独立计数）
# ---------------------------------------------------------------------------
_LOGIN_WINDOW_SECONDS = 15 * 60
_LOGIN_MAX_FAILURES = 10
_login_failures: Dict[str, List[float]] = {}


def _login_locked(key: str) -> bool:
    """窗口内失败次数是否已达阈值；顺带清理过期记录。"""
    now = time.time()
    attempts = [t for t in _login_failures.get(key, []) if now - t < _LOGIN_WINDOW_SECONDS]
    if attempts:
        _login_failures[key] = attempts
    else:
        _login_failures.pop(key, None)
    # 防止长期运行后字典无限膨胀：条目过多时丢弃最旧的一半
    if len(_login_failures) > 10000:
        for k in list(_login_failures.keys())[: len(_login_failures) // 2]:
            _login_failures.pop(k, None)
    return len(attempts) >= _LOGIN_MAX_FAILURES


def _record_login_failure(key: str) -> None:
    now = time.time()
    attempts = [t for t in _login_failures.get(key, []) if now - t < _LOGIN_WINDOW_SECONDS]
    attempts.append(now)
    _login_failures[key] = attempts


def _clear_login_failures(key: str) -> None:
    _login_failures.pop(key, None)


# PRD环境访问控制：非超级管理员禁止访问/操作PRD环境。
# 供各业务路由在拿到Environment后统一调用，避免只过滤列表页、直连ID绕过的漏洞。
def ensure_env_access(env, current_user) -> None:
    if env is None:
        return
    if not current_user.is_superuser and "PRD" in env.name.upper():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="权限不足，PRD环境仅超级管理员可操作",
        )
