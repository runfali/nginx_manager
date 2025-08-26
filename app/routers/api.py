from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from typing import Dict

from ..core.database import get_db
from ..models.environment import Environment
from ..services.nginx_sync import sync_nginx_configs
from ..routers.auth import get_current_active_user

router = APIRouter(prefix="/api", tags=["api"])


@router.post("/environments/{env_id}/sync", response_model=Dict[str, bool])
async def sync_configs(
    env_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    try:
        # 调用公共服务函数进行同步
        result = await sync_nginx_configs(env_id, db, current_user)

        # 如果同步失败，抛出异常
        if not result["success"]:
            status_code = 404 if "未找到" in result["message"] else 500
            raise HTTPException(status_code=status_code, detail=result["message"])

        return {"success": True}
    except HTTPException as http_ex:
        # 重新抛出HTTP异常
        raise http_ex
    except Exception as e:
        # 处理其他异常
        raise HTTPException(status_code=500, detail=f"同步配置失败: {str(e)}")
