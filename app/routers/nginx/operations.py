from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
import os
import paramiko
import tempfile
import datetime

from app.core.database import get_db
from app.models.nginx_config import NginxConfig
from app.models.environment import Environment
from app.models.user import User
from app.routers.auth import get_current_active_user

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

    # 获取环境信息
    env = db.query(Environment).filter(Environment.name == config.environment).first()
    if not env:
        return JSONResponse(
            content={"success": False, "message": "环境不存在"}, status_code=400
        )

    temp_path = None  # 初始化变量
    ssh = None  # 初始化变量
    config_temp_path = None  # 初始化变量

    try:
        # 不再强制要求用户设置SSH私钥，将使用默认私钥路径或用户私钥

        # 第二步：使用连接池时不需要创建私钥临时文件
        # with tempfile.NamedTemporaryFile(mode="w", delete=False) as temp_file:
        #     temp_file.write(current_user.ssh_private_key)
        #     temp_path = temp_file.name

        # 第三步：使用SSH连接池获取连接
        from app.services.ssh_utils import SSHUtils

        connection, ssh = SSHUtils.get_ssh_connection(
            hostname=env.server_ip,
            port=env.ssh_port,
            username="root",
            private_key_content=current_user.ssh_private_key,
        )

        # 执行nginx -t测试配置
        if ssh is None:
            return JSONResponse(
                content={"success": False, "message": "SSH连接失败"},
                status_code=500,
            )

        # 使用SSHUtils.execute_command替代直接调用exec_command
        try:
            exit_code, output, error_message = SSHUtils.execute_command(ssh, "nginx -t")

            if exit_code == 0:
                return JSONResponse(
                    content={"success": True, "message": "配置测试通过"}
                )
            else:
                return JSONResponse(
                    content={
                        "success": False,
                        "message": f"配置测试失败: {error_message}",
                    }
                )
        except Exception as e:
            return JSONResponse(
                content={"success": False, "message": f"执行命令失败: {str(e)}"},
                status_code=500,
            )

    except Exception as e:
        return JSONResponse(
            content={"success": False, "message": f"操作失败: {str(e)}"}
        )

    finally:
        # 清理临时文件
        if config_temp_path is not None and os.path.exists(config_temp_path):
            try:
                os.unlink(config_temp_path)
            except Exception as e:
                print(f"清理临时文件失败: {str(e)}")

        # 不需要关闭SSH连接，由连接池管理


# 删除配置 - 所有已登录用户可访问
@router.post("/{config_id}/delete")
async def delete_config(
    config_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    # 获取配置信息
    config = db.query(NginxConfig).filter(NginxConfig.id == config_id).first()
    if not config:
        raise HTTPException(status_code=404, detail="配置不存在")

    # 获取环境信息
    env = db.query(Environment).filter(Environment.name == config.environment).first()
    if not env:
        return JSONResponse(
            content={"success": False, "message": "环境不存在"}, status_code=400
        )

    ssh = None
    sftp = None
    backup_path = None  # 初始化backup_path变量

    try:
        # 使用SSH连接池获取连接
        from app.services.ssh_utils import SSHUtils

        connection, ssh = SSHUtils.get_ssh_connection(
            hostname=env.server_ip,
            port=env.ssh_port,
            username="root",
            private_key_content=current_user.ssh_private_key,
        )

        # 检查SSH连接是否成功
        if ssh is None:
            return JSONResponse(
                content={"success": False, "message": "SSH连接失败"},
                status_code=500,
            )

        # 创建SFTP客户端
        sftp = ssh.open_sftp()

        # 检查文件是否存在
        try:
            sftp.stat(config.file_path)
            file_exists = True
        except FileNotFoundError:
            file_exists = False

        if file_exists:
            # 创建备份目录
            backup_dir = "/usr/local/src/nginx_config_backups"
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            config_name = os.path.basename(config.file_path)
            backup_filename = f"{config_name}.{timestamp}.bak"
            backup_path = os.path.join(backup_dir, backup_filename)

            # 确保备份目录存在
            try:
                exit_code, output, error = SSHUtils.execute_command(
                    ssh, f"mkdir -p {backup_dir}"
                )
                if exit_code != 0:
                    return JSONResponse(
                        content={
                            "success": False,
                            "message": f"创建备份目录失败: {error}",
                        },
                        status_code=500,
                    )

                # 创建备份
                exit_code, output, error = SSHUtils.execute_command(
                    ssh, f"cp {config.file_path} {backup_path}"
                )
                if exit_code != 0:
                    return JSONResponse(
                        content={"success": False, "message": f"创建备份失败: {error}"},
                        status_code=500,
                    )
            except Exception as e:
                return JSONResponse(
                    content={"success": False, "message": f"执行命令失败: {str(e)}"},
                    status_code=500,
                )

            # 删除原文件
            sftp.remove(config.file_path)

        # 从数据库中删除配置
        db.delete(config)
        db.commit()

        message = "配置已从数据库中删除"
        if file_exists and backup_path:
            message = f"配置已成功删除，备份已保存到服务器 {backup_path}"

        return JSONResponse(
            content={
                "success": True,
                "message": message,
            }
        )

    except Exception as e:
        # 回滚数据库事务
        db.rollback()
        return JSONResponse(
            content={"success": False, "message": f"删除失败: {str(e)}"},
            status_code=500,
        )

    finally:
        # 关闭SFTP连接
        if sftp:
            sftp.close()


# 重载配置 - 所有已登录用户可访问
@router.post("/{config_id}/reload")
async def reload_config(
    config_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    config = db.query(NginxConfig).filter(NginxConfig.id == config_id).first()
    if not config:
        raise HTTPException(status_code=404, detail="配置不存在")

    # 获取环境信息
    env = db.query(Environment).filter(Environment.name == config.environment).first()
    if not env:
        return JSONResponse(
            content={"success": False, "message": "环境不存在"}, status_code=400
        )

    temp_path = None  # 初始化变量
    config_temp_path = None  # 初始化变量
    ssh = None  # 初始化变量
    sftp = None  # 初始化变量

    try:
        # 不再强制要求用户设置SSH私钥，将使用默认私钥路径或用户私钥

        # 2. 使用连接池时不需要创建私钥临时文件
        # with tempfile.NamedTemporaryFile(mode="w", delete=False) as temp_file:
        #     temp_file.write(current_user.ssh_private_key)
        #     temp_path = temp_file.name

        # 3. 使用SSH连接池获取连接
        from app.services.ssh_utils import SSHUtils

        connection, ssh = SSHUtils.get_ssh_connection(
            hostname=env.server_ip,
            port=env.ssh_port,
            username="root",
            private_key_content=current_user.ssh_private_key,
        )

        # 4. 创建配置文件临时文件
        with tempfile.NamedTemporaryFile(mode="w", delete=False) as config_temp_file:
            config_temp_file.write(config.content)
            config_temp_path = config_temp_file.name

        # 检查SSH连接是否成功
        if ssh is None:
            return JSONResponse(
                content={"success": False, "message": "SSH连接失败"},
                status_code=500,
            )

        # 创建SFTP客户端
        sftp = ssh.open_sftp()

        # 上传配置文件
        sftp.put(config_temp_path, config.file_path)

        # 设置文件权限
        sftp.chmod(config.file_path, 0o644)

        # 测试配置
        if ssh is None:
            return JSONResponse(
                content={"success": False, "message": "SSH连接失败"},
                status_code=500,
            )

        try:
            # 测试配置
            test_exit_code, test_output, test_error = SSHUtils.execute_command(
                ssh, "nginx -t"
            )

            if test_exit_code != 0:
                return JSONResponse(
                    content={
                        "success": False,
                        "message": f"配置测试失败: {test_error}",
                    },
                    status_code=400,
                )

            # 执行nginx -s reload重载配置
            reload_exit_code, reload_output, reload_error = SSHUtils.execute_command(
                ssh, "nginx -s reload"
            )

            if reload_exit_code == 0:
                # 更新配置的更新时间
                config.updated_by = current_user.id
                db.commit()
                return JSONResponse(
                    content={"success": True, "message": "配置已成功重载"}
                )
            else:
                return JSONResponse(
                    content={
                        "success": False,
                        "message": f"配置重载失败: {reload_error}",
                    },
                    status_code=400,
                )
        except Exception as e:
            return JSONResponse(
                content={"success": False, "message": f"执行命令失败: {str(e)}"},
                status_code=500,
            )

    except Exception as e:
        return JSONResponse(
            content={"success": False, "message": f"操作失败: {str(e)}"},
            status_code=500,
        )

    finally:
        # 使用连接池时不需要清理私钥临时文件
        # if temp_path and os.path.exists(temp_path):
        #     os.unlink(temp_path)
        if config_temp_path and os.path.exists(config_temp_path):
            os.unlink(config_temp_path)

        # 关闭SFTP连接
        if sftp:
            sftp.close()

        # 不需要关闭SSH连接，由连接池管理
        # if ssh:
        #     ssh.close()
