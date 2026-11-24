from typing import Optional, Tuple, Dict, Any
import posixpath
import shlex
import paramiko
import tempfile
import os
from fastapi import HTTPException
from app.services.ssh_pool import connection_pool, SSHConnection


def validate_relative_path(base: str, rel: str) -> str:
    """校验相对路径并拼接到 base 下（远端为Linux，统一使用posixpath）。
    禁止绝对路径与 .. 穿越，返回规范化后的绝对路径。"""
    base = (base or "").strip().replace("\\", "/")
    rel = (rel or "").strip().replace("\\", "/")
    if not base.startswith("/"):
        raise ValueError("环境Nginx路径必须为绝对路径")
    if rel.startswith("/") or rel.startswith("~"):
        raise ValueError("路径必须为相对路径")
    parts = [p for p in rel.split("/") if p not in ("", ".")]
    if ".." in parts:
        raise ValueError("路径中不允许包含 ..")
    if not parts:
        return posixpath.normpath(base)
    return posixpath.normpath(posixpath.join(base, *parts))


def validate_file_under_base(base: str, file_path: str) -> str:
    """校验远端文件路径必须是位于 base 目录内的绝对路径，禁止 .. 穿越与越界写入。"""
    base = (base or "").strip().replace("\\", "/")
    p = (file_path or "").strip().replace("\\", "/")
    if not base.startswith("/"):
        raise ValueError("环境Nginx路径必须为绝对路径")
    if not p.startswith("/"):
        raise ValueError("文件路径必须为绝对路径")
    norm = posixpath.normpath(p)
    base_norm = posixpath.normpath(base).rstrip("/")
    if norm == base_norm or not norm.startswith(base_norm + "/"):
        raise ValueError(f"文件路径必须位于 {base_norm} 目录内")
    return norm


def read_sftp_file_multi_encoding(sftp: paramiko.SFTPClient, file_path: str) -> str:
    encodings = ["utf-8", "gbk", "gb2312", "latin1"]
    for encoding in encodings:
        try:
            with sftp.open(file_path, "r") as f:
                return f.read().decode(encoding)
        except UnicodeDecodeError:
            continue
    with sftp.open(file_path, "rb") as f:
        return f.read().decode("latin1")


class SSHUtils:
    """
    SSH工具类，提供基于连接池的SSH操作
    用于替代直接使用paramiko的场景，提高SSH操作速度
    """

    @staticmethod
    def get_ssh_connection(
        hostname: str,
        port: int,
        username: str,
        private_key_content: Optional[str] = None,
        private_key_path: Optional[str] = None,
    ) -> Tuple[SSHConnection, Optional[paramiko.SSHClient]]:
        """
        从连接池获取SSH连接

        Args:
            hostname: 主机名
            port: 端口
            username: 用户名
            private_key_content: 私钥内容，可选
            private_key_path: 私钥文件路径，可选

        Returns:
            Tuple[SSHConnection, paramiko.SSHClient]: 连接对象和SSH客户端
        """
        # 从连接池获取连接
        connection = connection_pool.get_connection(
            hostname=hostname,
            port=port,
            username=username,
            private_key_content=private_key_content,
            private_key_path=private_key_path,
        )

        return connection, connection.ssh_client

    @staticmethod
    def get_ssh_or_fail(
        hostname: str,
        port: int,
        username: str,
        private_key_content: Optional[str] = None,
        private_key_path: Optional[str] = None,
    ) -> paramiko.SSHClient:
        try:
            connection = connection_pool.get_connection(
                hostname=hostname,
                port=port,
                username=username,
                private_key_content=private_key_content,
                private_key_path=private_key_path,
            )
        except ValueError as e:
            # 未配置私钥等业务性错误返回400，便于前端提示
            raise HTTPException(status_code=400, detail=str(e))
        if connection.ssh_client is None:
            raise HTTPException(status_code=500, detail="SSH连接失败")
        return connection.ssh_client

    @staticmethod
    def execute_command(
        ssh_client: paramiko.SSHClient, command: str, timeout: int = 30
    ) -> Tuple[int, str, str]:
        """
        执行SSH命令并返回退出码、标准输出和标准错误

        Args:
            ssh_client: SSH客户端
            command: 要执行的命令
            timeout: 命令执行超时时间（秒）

        Returns:
            Tuple[int, str, str]: 退出码、标准输出和标准错误
        """
        # 初始化并明确类型注解
        stdin: Optional[paramiko.ChannelFile] = None
        stdout: Optional[paramiko.ChannelFile] = None
        stderr: Optional[paramiko.ChannelFile] = None

        try:
            # 执行命令
            stdin, stdout, stderr = ssh_client.exec_command(command, timeout=timeout)

            # 断言确保非空
            assert stdout is not None, "stdout 未正确初始化"
            assert stderr is not None, "stderr 未正确初始化"

            # 设置通道超时
            stdout.channel.settimeout(timeout)
            stderr.channel.settimeout(timeout)

            exit_code = stdout.channel.recv_exit_status()
            output = stdout.read().decode()  # 直接读取
            error = stderr.read().decode()  # 直接读取
            return exit_code, output, error

        except Exception as e:
            raise RuntimeError(f"执行命令失败: {str(e)}") from e

        finally:
            # 安全关闭所有流
            for stream in [stdin, stdout, stderr]:
                if stream is not None:
                    try:
                        stream.close()
                    except Exception:
                        pass  # 忽略关闭时的异常

    @staticmethod
    def get_directory_info(
        ssh_client: paramiko.SSHClient, directory_path: str, timeout: int = 30
    ) -> Dict[str, Dict[str, Any]]:
        """
        一次性获取目录中所有文件的信息，包括类型和软链接状态

        Args:
            ssh_client: SSH客户端
            directory_path: 目录路径
            timeout: 超时时间（秒）

        Returns:
            Dict[str, Dict[str, Any]]: 文件名到文件信息的映射
        """
        # 使用find命令一次性获取所有文件信息
        command = """
        cd {} 2>/dev/null && \
        find . -maxdepth 1 -mindepth 1 -exec sh -c '
            for file; do
                basename="$(basename "$file")"
                if [ -L "$file" ]; then
                    if [ -d "$file" ]; then
                        echo "$basename|symlink_dir"
                    else
                        echo "$basename|symlink_file"
                    fi
                elif [ -d "$file" ]; then
                    echo "$basename|directory"
                elif [ -f "$file" ]; then
                    echo "$basename|file"
                else
                    echo "$basename|unknown"
                fi
            done
        ' sh {{}} +
        """.format(
            shlex.quote(directory_path)
        )

        try:
            exit_code, output, error = SSHUtils.execute_command(
                ssh_client, command, timeout
            )

            file_info = {}
            if exit_code == 0 and output.strip():
                for line in output.strip().split("\n"):
                    if "|" in line:
                        filename, file_type = line.rsplit("|", 1)
                        is_dir = file_type in ["directory", "symlink_dir"]
                        is_symlink = file_type.startswith("symlink")

                        file_info[filename] = {
                            "is_dir": is_dir,
                            "is_symlink": is_symlink,
                            "type": file_type,
                        }

            return file_info

        except Exception as e:
            raise RuntimeError(f"获取目录信息失败: {str(e)}") from e

    @staticmethod
    def get_sftp_client(
        connection: SSHConnection, ssh_client: paramiko.SSHClient
    ) -> paramiko.SFTPClient:
        """
        获取SFTP客户端

        Args:
            connection: SSH连接对象
            ssh_client: SSH客户端

        Returns:
            paramiko.SFTPClient: SFTP客户端
        """
        # 如果连接已有SFTP客户端，直接返回
        if connection.sftp_client:
            return connection.sftp_client

        # 否则创建新的SFTP客户端
        sftp_client = ssh_client.open_sftp()
        connection.sftp_client = sftp_client
        return sftp_client


