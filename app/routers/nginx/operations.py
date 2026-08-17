from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
import os
import tempfile
import logging
import datetime

logger = logging.getLogger(__name__)

from app.core.database import get_db
from app.core.security import decrypt_private_key
from app.models.nginx_config import NginxConfig
from app.models.environment import Environment
from app.models.user import User
from app.routers.auth import get_current_active_user
from app.services.ssh_utils import SSHUtils

router = APIRouter()


# 测试配置 - 所有已登录用户可访问
@router.post("/{config_id}/test")
async def test_config(
    config_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    config = db.query(NginxConfig).filter(NginxConfig.id == config_id).first()
    if not config:
        raise HTTPException(status_code=404, detail="配置不存在")

    env = db.query(Environment).filter(Environment.id == config.environment).first()
    if not env:
        raise HTTPException(status_code=400, detail="环境不存在")

    sftp = None
    temp_path = None
    try:
        ssh = SSHUtils.get_ssh_or_fail(
            hostname=env.server_ip,
            port=env.ssh_port,
            username="root",
            private_key_content=decrypt_private_key(current_user.ssh_private_key),
        )

        sftp = ssh.open_sftp()

        with tempfile.NamedTemporaryFile(mode="w", delete=False) as f:
            f.write(config.content)
            temp_path = f.name
        sftp.put(temp_path, config.file_path)

        exit_code, output, error_message = SSHUtils.execute_command(ssh, "nginx -t")
        if exit_code == 0:
            return JSONResponse(content={"success": True, "message": "配置测试通过"})
        else:
            return JSONResponse(
                content={"success": False, "message": f"配置测试失败: {error_message}"}
            )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"操作失败: {str(e)}")
    finally:
        if sftp:
            sftp.close()
        if temp_path and os.path.exists(temp_path):
            try:
                os.unlink(temp_path)
            except Exception:
                pass


# 删除配置 - 所有已登录用户可访问
@router.post("/{config_id}/delete")
async def delete_config(
    config_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    config = db.query(NginxConfig).filter(NginxConfig.id == config_id).first()
    if not config:
        raise HTTPException(status_code=404, detail="配置不存在")

    env = db.query(Environment).filter(Environment.id == config.environment).first()
    if not env:
        raise HTTPException(status_code=400, detail="环境不存在")

    sftp = None
    try:
        ssh = SSHUtils.get_ssh_or_fail(
            hostname=env.server_ip,
            port=env.ssh_port,
            username="root",
            private_key_content=decrypt_private_key(current_user.ssh_private_key),
        )

        sftp = ssh.open_sftp()

        file_exists = True
        try:
            sftp.stat(config.file_path)
        except FileNotFoundError:
            file_exists = False

        backup_path = None
        if file_exists:
            backup_dir = "/usr/local/src/nginx_config_backups"
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            config_name = os.path.basename(config.file_path)
            backup_filename = f"{config_name}.{timestamp}.bak"
            backup_path = os.path.join(backup_dir, backup_filename)

            exit_code, output, error = SSHUtils.execute_command(
                ssh, f"mkdir -p {backup_dir}"
            )
            if exit_code != 0:
                raise HTTPException(
                    status_code=500, detail=f"创建备份目录失败: {error}"
                )

            exit_code, output, error = SSHUtils.execute_command(
                ssh, f"cp {config.file_path} {backup_path}"
            )
            if exit_code != 0:
                raise HTTPException(
                    status_code=500, detail=f"创建备份失败: {error}"
                )

            sftp.remove(config.file_path)

        db.delete(config)
        db.commit()

        message = "配置已从数据库中删除"
        if file_exists and backup_path:
            message = f"配置已成功删除，备份已保存到服务器 {backup_path}"

        return JSONResponse(content={"success": True, "message": message})
    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"删除失败: {str(e)}")
    finally:
        if sftp:
            sftp.close()


# 重载前测试 - 所有已登录用户可访问
@router.post("/{config_id}/reload-test")
async def reload_test(
    config_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    config = db.query(NginxConfig).filter(NginxConfig.id == config_id).first()
    if not config:
        raise HTTPException(status_code=404, detail="配置不存在")

    env = db.query(Environment).filter(Environment.id == config.environment).first()
    if not env:
        raise HTTPException(status_code=400, detail="环境不存在")

    sftp = None
    temp_path = None
    try:
        ssh = SSHUtils.get_ssh_or_fail(
            hostname=env.server_ip,
            port=env.ssh_port,
            username="root",
            private_key_content=decrypt_private_key(current_user.ssh_private_key),
        )

        sftp = ssh.open_sftp()

        with tempfile.NamedTemporaryFile(mode="w", delete=False) as f:
            f.write(config.content)
            temp_path = f.name
        sftp.put(temp_path, config.file_path)

        exit_code, output, error_message = SSHUtils.execute_command(ssh, "nginx -t")
        if exit_code == 0:
            return JSONResponse(content={"success": True, "message": "配置测试通过"})
        else:
            return JSONResponse(
                content={"success": False, "message": error_message}
            )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"操作失败: {str(e)}")
    finally:
        if sftp:
            sftp.close()
        if temp_path and os.path.exists(temp_path):
            try:
                os.unlink(temp_path)
            except Exception:
                pass


# 执行重载 - 所有已登录用户可访问
@router.post("/{config_id}/reload-exec")
async def reload_exec(
    config_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    config = db.query(NginxConfig).filter(NginxConfig.id == config_id).first()
    if not config:
        raise HTTPException(status_code=404, detail="配置不存在")

    env = db.query(Environment).filter(Environment.id == config.environment).first()
    if not env:
        raise HTTPException(status_code=400, detail="环境不存在")

    try:
        ssh = SSHUtils.get_ssh_or_fail(
            hostname=env.server_ip,
            port=env.ssh_port,
            username="root",
            private_key_content=decrypt_private_key(current_user.ssh_private_key),
        )

        exit_code, output, error_message = SSHUtils.execute_command(ssh, "nginx -s reload")
        if exit_code == 0:
            config.updated_by = current_user.id
            db.commit()
            return JSONResponse(content={"success": True, "message": "Nginx 重载成功"})
        else:
            return JSONResponse(
                content={"success": False, "message": f"重载失败: {error_message}"},
                status_code=400,
            )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"操作失败: {str(e)}")
