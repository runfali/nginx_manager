from typing import Optional, Tuple, Dict, Any
import paramiko
import tempfile
import os
from app.services.ssh_pool import connection_pool, SSHConnection


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
    def execute_command(
        ssh_client: paramiko.SSHClient, command: str
    ) -> Tuple[int, str, str]:
        """
        执行SSH命令并返回退出码、标准输出和标准错误

        Args:
            ssh_client: SSH客户端
            command: 要执行的命令

        Returns:
            Tuple[int, str, str]: 退出码、标准输出和标准错误
        """
        # 初始化并明确类型注解
        stdin: Optional[paramiko.ChannelFile] = None
        stdout: Optional[paramiko.ChannelFile] = None
        stderr: Optional[paramiko.ChannelFile] = None

        try:
            # 执行命令
            stdin, stdout, stderr = ssh_client.exec_command(command)

            # 断言确保非空
            assert stdout is not None, "stdout 未正确初始化"
            assert stderr is not None, "stderr 未正确初始化"

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

    @staticmethod
    def with_ssh_connection(
        hostname: str,
        port: int,
        username: str,
        private_key_content: Optional[str],
        operation_func,
        *args,
        **kwargs,
    ):
        """
        使用SSH连接执行操作的装饰器函数

        Args:
            hostname: 主机名
            port: 端口
            username: 用户名
            private_key_content: 私钥内容
            operation_func: 要执行的操作函数
            *args, **kwargs: 传递给操作函数的参数

        Returns:
            Any: 操作函数的返回值
        """
        # 获取SSH连接
        connection, ssh_client = SSHUtils.get_ssh_connection(
            hostname=hostname,
            port=port,
            username=username,
            private_key_content=private_key_content,
        )

        try:
            # 确保ssh_client不为None
            if ssh_client is None:
                raise RuntimeError("SSH客户端未初始化或连接失败")

            # 执行操作
            return operation_func(ssh_client, *args, **kwargs)
        except Exception as e:
            raise e
