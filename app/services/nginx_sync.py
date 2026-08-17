from typing import Dict, Optional, Any
import os
import logging
from sqlalchemy.orm import Session

from app.models.environment import Environment
from app.models.nginx_config import NginxConfig
from app.models.user import User
from app.core.security import decrypt_private_key
from app.services.ssh_utils import SSHUtils, read_sftp_file_multi_encoding

logger = logging.getLogger(__name__)


async def sync_nginx_configs(
    env_id: int,
    db: Session,
    current_user: User,
    path: Optional[str] = None,
) -> Dict[str, Any]:
    """
    同步Nginx配置文件的公共服务函数

    Args:
        env_id: 环境ID
        db: 数据库会话
        current_user: 当前用户
        path: 可选的子目录路径

    Returns:
        Dict[str, Any]: 包含同步结果的字典
    """
    # 获取环境信息
    env = db.query(Environment).filter(Environment.id == env_id).first()
    if not env:
        return {"success": False, "message": "环境不存在"}

    # 确定要同步的目录路径
    sync_path = os.path.join(env.nginx_path, path) if path else env.nginx_path

    ssh = None
    sftp = None
    try:
        connection, ssh = SSHUtils.get_ssh_connection(
            hostname=env.server_ip,
            port=env.ssh_port,
            username="root",
            private_key_content=(
                decrypt_private_key(current_user.ssh_private_key) if current_user.ssh_private_key else None
            ),
        )

        if ssh is None:
            return {"success": False, "message": "SSH连接失败"}

        exit_code, output, error = SSHUtils.execute_command(
            ssh_client=ssh, command=f"find -L {sync_path} -type f -name '*.conf'"
        )
        find_output = output.strip()

        # 检查是否有配置文件
        if not find_output:
            return {
                "success": False,
                "message": f"在路径 {sync_path} 下未找到任何Nginx配置文件",
            }

        config_files = find_output.split("\n")

        # 获取SFTP客户端
        sftp = SSHUtils.get_sftp_client(connection, ssh)
        synced_count = 0
        for file_path in config_files:
            if not file_path:  # 跳过空行
                continue

            try:
                content = read_sftp_file_multi_encoding(sftp, file_path)

                name = os.path.basename(file_path)

                # 检查配置是否已存在
                existing_config = (
                    db.query(NginxConfig)
                    .filter(
                        NginxConfig.environment == env.id,
                        NginxConfig.file_path == file_path,
                    )
                    .first()
                )

                if existing_config:
                    # 更新现有配置
                    existing_config.content = content
                    existing_config.server_ip = env.server_ip
                    existing_config.updated_by = current_user.id
                else:
                    # 创建新配置
                    new_config = NginxConfig(
                        name=name,
                        environment=env.id,
                        server_ip=env.server_ip,
                        file_path=file_path,
                        content=content,
                        created_by=current_user.id,
                        updated_by=current_user.id,
                    )
                    db.add(new_config)
                synced_count += 1
            except Exception as file_error:
                logger.exception("处理文件 %s 时出错", file_path)
                continue

        # 检查数据库中的配置文件是否在服务器上仍然存在
        # 获取当前环境下数据库中所有的配置文件记录
        db_configs = (
            db.query(NginxConfig).filter(NginxConfig.environment == env.id).all()
        )

        # 创建一个集合，包含所有在服务器上找到的配置文件路径
        server_config_paths = set(config_files)

        # 检查数据库中的每个配置，如果在服务器上不存在，则删除
        deleted_count = 0
        for config in db_configs:
            # 如果指定了子目录路径，只处理该子目录下的配置
            if path and not config.file_path.startswith(sync_path):
                continue

            if config.file_path not in server_config_paths:
                # 配置文件在服务器上已被删除，从数据库中删除
                db.delete(config)
                deleted_count += 1

        db.commit()

        # 构建返回消息
        message = f"成功同步 {synced_count} 个配置文件"
        if deleted_count > 0:
            message += f"，删除 {deleted_count} 个已不存在的配置文件"

        return {"success": True, "message": message}

    except Exception as e:
        # 回滚数据库事务
        db.rollback()
        return {"success": False, "message": f"同步失败: {str(e)}"}

    finally:
        # 不需要关闭SFTP和SSH连接，因为它们由连接池管理
        # 也不需要清理临时文件，因为连接池会处理
        pass


async def sync_single_nginx_config(
    env_id: int,
    file_path: str,
    db: Session,
    current_user: User,
) -> Dict[str, Any]:
    """
    同步单个Nginx配置文件的公共服务函数

    Args:
        env_id: 环境ID
        file_path: 文件路径
        db: 数据库会话
        current_user: 当前用户

    Returns:
        Dict[str, Any]: 包含同步结果的字典
    """
    # 获取环境信息
    env = db.query(Environment).filter(Environment.id == env_id).first()
    if not env:
        return {"success": False, "message": "环境不存在"}

    ssh = None
    sftp = None
    try:
        connection, ssh = SSHUtils.get_ssh_connection(
            hostname=env.server_ip,
            port=env.ssh_port,
            username="root",
            private_key_content=(
                decrypt_private_key(current_user.ssh_private_key) if current_user.ssh_private_key else None
            ),
        )

        if ssh is None:
            return {"success": False, "message": "SSH连接失败"}

        exit_code, output, error = SSHUtils.execute_command(
            ssh, f"test -f {file_path} && echo 'exists'"
        )
        file_exists = bool(output.strip())

        name = os.path.basename(file_path)
        existing_config = (
            db.query(NginxConfig)
            .filter(
                NginxConfig.environment == env.id,
                NginxConfig.file_path == file_path,
            )
            .first()
        )

        if not file_exists and existing_config:
            db.delete(existing_config)
            db.commit()
            return {
                "success": True,
                "message": f"文件 {file_path} 已从服务器删除，数据库记录已同步删除",
            }

        if not file_exists:
            return {"success": False, "message": f"文件 {file_path} 不存在"}

        sftp = SSHUtils.get_sftp_client(connection, ssh)

        content = read_sftp_file_multi_encoding(sftp, file_path)

        name = os.path.basename(file_path)

        # 检查配置是否已存在
        existing_config = (
            db.query(NginxConfig)
            .filter(
                NginxConfig.name == name,
                NginxConfig.environment == env.id,
                NginxConfig.file_path == file_path,
            )
            .first()
        )

        if existing_config:
            # 更新现有配置
            existing_config.content = content
            existing_config.updated_by = current_user.id
        else:
            # 创建新配置
            new_config = NginxConfig(
                name=name,
                environment=env.id,
                server_ip=env.server_ip,
                file_path=file_path,
                content=content,
                created_by=current_user.id,
                updated_by=current_user.id,
            )
            db.add(new_config)

        db.commit()
        return {"success": True, "message": f"成功同步配置文件 {name}"}

    except Exception as e:
        # 回滚数据库事务
        db.rollback()
        return {"success": False, "message": f"同步失败: {str(e)}"}

    finally:
        # 不需要关闭SFTP和SSH连接，因为它们由连接池管理
        # 也不需要清理临时文件，因为连接池会处理
        pass
