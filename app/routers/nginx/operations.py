from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
import os
import shlex
import tempfile
import logging
import datetime
from typing import Tuple

logger = logging.getLogger(__name__)

from app.core.database import get_db
from app.core.security import decrypt_private_key
from app.models.nginx_config import NginxConfig
from app.models.environment import Environment
from app.models.user import User
from app.routers.auth import get_current_active_user, ensure_env_access
from app.services.ssh_utils import SSHUtils

router = APIRouter()


def _upload_and_test(ssh, sftp, config) -> Tuple[int, str, str]:
    """上传配置内容到远端并执行 nginx -t。

    远端已存在的文件先备份到本地，nginx -t 失败时自动回滚，
    避免正式配置文件被未通过测试的内容覆盖后留在磁盘上。
    """
    backup_local = None
    temp_path = None
    try:
        remote_existed = False
        try:
            sftp.stat(config.file_path)
            remote_existed = True
        except FileNotFoundError:
            remote_existed = False

        if remote_existed:
            with tempfile.NamedTemporaryFile(delete=False) as bf:
                bf.close()
                backup_local = bf.name
            sftp.get(config.file_path, backup_local)

        with tempfile.NamedTemporaryFile(mode="w", delete=False) as f:
            f.write(config.content)
            temp_path = f.name
        sftp.put(temp_path, config.file_path)

        exit_code, output, error_message = SSHUtils.execute_command(ssh, "nginx -t")
        if exit_code != 0 and remote_existed and backup_local:
            try:
                sftp.put(backup_local, config.file_path)
            except Exception:
                logger.exception("测试失败后回滚远端配置失败: %s", config.file_path)
        return exit_code, output, error_message
    finally:
        for local in (temp_path, backup_local):
            if local and os.path.exists(local):
                try:
                    os.unlink(local)
                except Exception:
                    pass


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

    # 非超级管理员禁止操作PRD环境的配置
    ensure_env_access(env, current_user)

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

        # 上传+测试+失败自动回滚（防止nginx -t失败后正式配置文件留在损坏状态）
        exit_code, output, error_message = _upload_and_test(ssh, sftp, config)
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

    # 非超级管理员禁止操作PRD环境的配置
    ensure_env_access(env, current_user)

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
            # 远端为Linux路径，显式用/拼接（Windows宿主机上os.path.join会产生反斜杠）
            backup_path = f"{backup_dir}/{backup_filename}"

            exit_code, output, error = SSHUtils.execute_command(
                ssh, f"mkdir -p {shlex.quote(backup_dir)}"
            )
            if exit_code != 0:
                raise HTTPException(
                    status_code=500, detail=f"创建备份目录失败: {error}"
                )

            exit_code, output, error = SSHUtils.execute_command(
                ssh,
                f"cp {shlex.quote(config.file_path)} {shlex.quote(backup_path)}",
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

    # 非超级管理员禁止操作PRD环境的配置
    ensure_env_access(env, current_user)

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

        # 上传+测试+失败自动回滚（防止nginx -t失败后正式配置文件留在损坏状态）
        exit_code, output, error_message = _upload_and_test(ssh, sftp, config)
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

    # 非超级管理员禁止操作PRD环境的配置
    ensure_env_access(env, current_user)

    try:
        ssh = SSHUtils.get_ssh_or_fail(
            hostname=env.server_ip,
            port=env.ssh_port,
            username="root",
            private_key_content=decrypt_private_key(current_user.ssh_private_key),
        )
        # 重载前先做语法测试：测试失败直接取消重载，避免把带语法错误的配置推入运行中的Nginx
        test_code, test_output, test_error = SSHUtils.execute_command(ssh, "nginx -t")
        if test_code != 0:
            return JSONResponse(
                content={
                    "success": False,
                    "message": f"重载前语法测试失败，已取消重载: {test_error or test_output}",
                },
                status_code=400,
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
