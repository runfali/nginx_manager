from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from typing import Optional

from app.core.database import get_db
from app.models.environment import Environment
from app.models.user import User
from app.routers.auth import get_current_active_user
from app.services.nginx_sync import sync_nginx_configs, sync_single_nginx_config

router = APIRouter()


# 同步指定目录下的配置文件 - 所有已登录用户可访问
@router.post("/{env_id}")
async def sync_configs(
    env_id: int,
    path: Optional[str] = None,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    # 调用公共服务函数进行同步
    result = await sync_nginx_configs(env_id, db, current_user, path)

    # 根据结果返回响应
    status_code = 200
    if not result["success"]:
        if "未找到" in result["message"]:
            status_code = 404
        elif "请先在个人资料中设置SSH私钥" in result["message"]:
            status_code = 400
        else:
            status_code = 500

    return JSONResponse(content=result, status_code=status_code)


# 同步单个配置文件 - 所有已登录用户可访问
@router.post("/file/{env_id}")
async def sync_single_file(
    env_id: int,
    file_path: str,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    # 调用公共服务函数进行单文件同步
    result = await sync_single_nginx_config(env_id, file_path, db, current_user)

    # 根据结果返回响应
    status_code = 200
    if not result["success"]:
        if "不存在" in result["message"]:
            status_code = 404
        elif "请先在个人资料中设置SSH私钥" in result["message"]:
            status_code = 400
        else:
            status_code = 500

    return JSONResponse(content=result, status_code=status_code)
