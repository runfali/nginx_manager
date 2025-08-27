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
    def execute_batch_commands(
        ssh_client: paramiko.SSHClient, commands: list[str], timeout: int = 30
    ) -> Dict[str, Tuple[int, str, str]]:
        """
        批量执行SSH命令，提高效率

        Args:
            ssh_client: SSH客户端
            commands: 要执行的命令列表
            timeout: 命令执行超时时间（秒）

        Returns:
            Dict[str, Tuple[int, str, str]]: 命令到结果的映射
        """
        results = {}

        # 将多个命令组合成一个复合命令
        combined_command = "; ".join(
            [
                f"echo 'CMD_START_{i}'; {cmd}; echo 'CMD_END_{i}_$?'"
                for i, cmd in enumerate(commands)
            ]
        )

        try:
            exit_code, output, error = SSHUtils.execute_command(
                ssh_client, combined_command, timeout
            )

            # 解析输出
            lines = output.strip().split("\n")
            current_cmd_idx = None
            current_output = []

            for line in lines:
                if line.startswith("CMD_START_"):
                    current_cmd_idx = int(line.split("_")[2])
                    current_output = []
                elif line.startswith("CMD_END_"):
                    parts = line.split("_")
                    cmd_idx = int(parts[2])
                    cmd_exit_code = int(parts[3])

                    if current_cmd_idx == cmd_idx:
                        cmd_output = "\n".join(current_output)
                        results[commands[cmd_idx]] = (cmd_exit_code, cmd_output, "")
                else:
                    if current_cmd_idx is not None:
                        current_output.append(line)

            # 如果解析失败，回退到逐个执行
            if len(results) != len(commands):
                results.clear()
                for cmd in commands:
                    try:
                        result = SSHUtils.execute_command(ssh_client, cmd, timeout)
                        results[cmd] = result
                    except Exception as e:
                        results[cmd] = (1, "", str(e))

        except Exception as e:
            # 如果批量执行失败，回退到逐个执行
            for cmd in commands:
                try:
                    result = SSHUtils.execute_command(ssh_client, cmd, timeout)
                    results[cmd] = result
                except Exception as cmd_e:
                    results[cmd] = (1, "", str(cmd_e))

        return results

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
        cd "{}" 2>/dev/null && \
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
            directory_path
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
