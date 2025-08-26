from typing import Dict, Optional, Any
import os
import paramiko
import tempfile
from sqlalchemy.orm import Session

from app.models.environment import Environment
from app.models.nginx_config import NginxConfig
from app.models.user import User
from app.services.ssh_utils import SSHUtils


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
        # 使用SSH连接池获取连接
        # 如果用户设置了私钥，使用用户私钥；否则使用默认私钥路径
        connection, ssh = SSHUtils.get_ssh_connection(
            hostname=env.server_ip,
            port=env.ssh_port,
            username="root",
            private_key_content=(
                current_user.ssh_private_key if current_user.ssh_private_key else None
            ),
        )

        # 获取指定目录下的Nginx配置文件列表（包括软链接目录）
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
                # 读取远程文件内容，尝试多种编码方式
                content = None
                encodings = ["utf-8", "gbk", "gb2312", "latin1"]

                # 先尝试不同的编码
                for encoding in encodings:
                    try:
                        with sftp.open(file_path, "r") as f:
                            content = f.read().decode(encoding)
                        break  # 如果成功解码，跳出循环
                    except UnicodeDecodeError:
                        continue

                # 如果所有编码都失败，使用二进制模式读取并使用latin1编码（不会失败）
                if content is None:
                    with sftp.open(file_path, "rb") as f:
                        binary_content = f.read()
                        content = binary_content.decode(
                            "latin1"
                        )  # latin1可以处理任何字节

                name = os.path.basename(file_path)

                # 检查配置是否已存在
                existing_config = (
                    db.query(NginxConfig)
                    .filter(
                        NginxConfig.environment == env.name,
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
                        environment=env.name,
                        server_ip=env.server_ip,
                        file_path=file_path,
                        content=content,
                        created_by=current_user.id,
                        updated_by=current_user.id,
                    )
                    db.add(new_config)
                synced_count += 1
            except Exception as file_error:
                # 记录单个文件处理错误但继续处理其他文件
                print(f"处理文件 {file_path} 时出错: {str(file_error)}")
                continue

        # 检查数据库中的配置文件是否在服务器上仍然存在
        # 获取当前环境下数据库中所有的配置文件记录
        db_configs = (
            db.query(NginxConfig).filter(NginxConfig.environment == env.name).all()
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
        # 使用SSH连接池获取连接
        # 如果用户设置了私钥，使用用户私钥；否则使用默认私钥路径
        connection, ssh = SSHUtils.get_ssh_connection(
            hostname=env.server_ip,
            port=env.ssh_port,
            username="root",
            private_key_content=(
                current_user.ssh_private_key if current_user.ssh_private_key else None
            ),
        )

        # 检查文件是否存在
        if ssh is None:
            return {"success": False, "message": "SSH连接失败"}

        if ssh is None:
            return {"success": False, "message": "SSH连接失败"}

        stdin, stdout, stderr = ssh.exec_command(
            f"test -f {file_path} && echo 'exists'"
        )
        file_exists = bool(stdout.read().decode().strip())

        # 检查文件是否存在于数据库中
        name = os.path.basename(file_path)
        existing_config = (
            db.query(NginxConfig)
            .filter(
                NginxConfig.environment == env.name,
                NginxConfig.file_path == file_path,
            )
            .first()
        )

        # 如果文件在服务器上不存在但在数据库中存在，则删除数据库记录
        if not file_exists and existing_config:
            db.delete(existing_config)
            db.commit()
            return {
                "success": True,
                "message": f"文件 {file_path} 已从服务器删除，数据库记录已同步删除",
            }

        # 如果文件在服务器上不存在且数据库中也不存在，返回不存在消息
        if not file_exists:
            return {"success": False, "message": f"文件 {file_path} 不存在"}

        # 读取文件内容
        if ssh is None:
            return {"success": False, "message": "SSH连接失败"}

        if ssh is None:
            return {"success": False, "message": "SSH连接失败"}

        sftp = ssh.open_sftp()
        try:
            # 读取远程文件内容，尝试多种编码方式
            content = None
            encodings = ["utf-8", "gbk", "gb2312", "latin1"]

            # 先尝试不同的编码
            for encoding in encodings:
                try:
                    with sftp.open(file_path, "r") as f:
                        content = f.read().decode(encoding)
                    break  # 如果成功解码，跳出循环
                except UnicodeDecodeError:
                    continue

            # 如果所有编码都失败，使用二进制模式读取并使用latin1编码（不会失败）
            if content is None:
                with sftp.open(file_path, "rb") as f:
                    binary_content = f.read()
                    content = binary_content.decode("latin1")  # latin1可以处理任何字节

            name = os.path.basename(file_path)

            # 检查配置是否已存在
            existing_config = (
                db.query(NginxConfig)
                .filter(
                    NginxConfig.name == name,
                    NginxConfig.environment == env.name,
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
                    environment=env.name,
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
            return {"success": False, "message": f"读取文件失败: {str(e)}"}

    except Exception as e:
        # 回滚数据库事务
        db.rollback()
        return {"success": False, "message": f"同步失败: {str(e)}"}

    finally:
        # 不需要关闭SFTP和SSH连接，因为它们由连接池管理
        # 也不需要清理临时文件，因为连接池会处理
        pass
