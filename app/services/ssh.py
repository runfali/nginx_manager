from typing import Optional, Tuple
import paramiko
import tempfile
import os
from app.services.ssh_pool import connection_pool, SSHConnection


class SSHService:
    def __init__(self, hostname: str, port: int = 22, username: str = "root"):
        self.hostname = hostname
        self.port = port
        self.username = username
        self._connection: Optional[SSHConnection] = None
        self._ssh: Optional[paramiko.SSHClient] = None
        self._sftp: Optional[paramiko.SFTPClient] = None
        self._temp_files = []

    def connect_with_key(
        self,
        private_key_content: Optional[str] = None,
        private_key_path: Optional[str] = None,
    ) -> None:
        """使用私钥内容或私钥文件建立SSH连接，从连接池获取或创建新连接

        Args:
            private_key_content: 私钥内容，可选
            private_key_path: 私钥文件路径，可选，如果未提供私钥内容和路径，将使用默认路径
        """
        try:
            # 从连接池获取连接
            self._connection = connection_pool.get_connection(
                hostname=self.hostname,
                port=self.port,
                username=self.username,
                private_key_content=private_key_content,
                private_key_path=private_key_path,
            )

            # 获取SSH客户端
            self._ssh = self._connection.ssh_client

        except Exception as e:
            self.cleanup()
            raise Exception(f"SSH连接失败: {str(e)}")

    def execute_command(self, command: str) -> Tuple[int, str, str]:
        """执行SSH命令并返回退出码、标准输出和标准错误"""
        if not self._ssh:
            raise RuntimeError("SSH未连接")

        # 初始化并明确类型注解（Paramiko 返回的均是 ChannelFile 类型）
        stdin: Optional[paramiko.ChannelFile] = None
        stdout: Optional[paramiko.ChannelFile] = None
        stderr: Optional[paramiko.ChannelFile] = None

        try:
            # exec_command 返回的 stdin/stdout/stderr 实际类型均为 ChannelFile
            stdin, stdout, stderr = self._ssh.exec_command(command)

            # 断言确保非空（exec_command 成功时必定有值）
            assert stdout is not None, "stdout 未正确初始化"
            assert stderr is not None, "stderr 未正确初始化"

            exit_code = stdout.channel.recv_exit_status()
            output = stdout.read().decode()  # 直接读取（已断言非空）
            error = stderr.read().decode()  # 直接读取（已断言非空）
            return exit_code, output, error

        except Exception as e:
            raise RuntimeError(f"执行命令失败: {str(e)}") from e

        finally:
            # 安全关闭所有流（无需类型检查，None 会跳过）
            for stream in [stdin, stdout, stderr]:
                if stream is not None:
                    try:
                        stream.close()
                    except Exception:
                        pass  # 忽略关闭时的异常

    def upload_file(
        self, local_content: str, remote_path: str, mode: int = 0o644
    ) -> None:
        """上传文件内容到远程服务器"""
        if not self._ssh:
            raise Exception("SSH未连接")

        temp_path = None
        try:
            # 创建临时文件
            with tempfile.NamedTemporaryFile(mode="w", delete=False) as temp_file:
                temp_file.write(local_content)
                temp_path = temp_file.name
                self._temp_files.append(temp_path)

            # 创建或获取SFTP客户端
            if self._connection and self._connection.sftp_client:
                self._sftp = self._connection.sftp_client
            else:
                self._sftp = self._ssh.open_sftp()
                if self._connection:  # 确保_connection不为None
                    self._connection.sftp_client = self._sftp

            # 上传文件
            self._sftp.put(temp_path, remote_path)
            self._sftp.chmod(remote_path, mode)

        except Exception as e:
            raise Exception(f"文件上传失败: {str(e)}")
        finally:
            if temp_path and os.path.exists(temp_path):
                try:
                    os.unlink(temp_path)
                    self._temp_files.remove(temp_path)
                except:
                    pass

    def download_file(self, remote_path: str) -> str:
        """从远程服务器下载文件内容"""
        if not self._ssh:
            raise Exception("SSH未连接")

        temp_path = None
        try:
            # 创建或获取SFTP客户端
            if self._connection and self._connection.sftp_client:
                self._sftp = self._connection.sftp_client
            else:
                self._sftp = self._ssh.open_sftp()
                if self._connection:  # 确保_connection不为None
                    self._connection.sftp_client = self._sftp

            # 创建临时文件
            temp_file = tempfile.NamedTemporaryFile(delete=False)
            temp_path = temp_file.name
            temp_file.close()
            self._temp_files.append(temp_path)

            # 下载文件
            self._sftp.get(remote_path, temp_path)

            # 读取文件内容
            content = ""
            # 尝试多种编码方式读取文件
            encodings = ["utf-8", "gbk", "gb2312", "latin1"]
            for encoding in encodings:
                try:
                    with open(temp_path, "r", encoding=encoding) as f:
                        content = f.read()
                    break  # 如果成功解码，跳出循环
                except UnicodeDecodeError:
                    continue

            # 如果所有编码都失败，使用二进制模式读取并使用latin1编码
            if not content:
                with open(temp_path, "rb") as f:
                    binary_content = f.read()
                    content = binary_content.decode("latin1")  # latin1可以处理任何字节

            return content

        except Exception as e:
            raise Exception(f"文件下载失败: {str(e)}")
        finally:
            if temp_path and os.path.exists(temp_path):
                try:
                    os.unlink(temp_path)
                    self._temp_files.remove(temp_path)
                except:
                    pass

    def cleanup(self) -> None:
        """清理资源"""
        # 清理SFTP连接
        if self._sftp:
            try:
                self._sftp.close()
            except:
                pass
            self._sftp = None

        # 清理SSH连接
        if self._ssh:
            try:
                self._ssh.close()
            except:
                pass
            self._ssh = None

        # 清理所有临时文件
        for temp_file in self._temp_files:
            try:
                if os.path.exists(temp_file):
                    os.unlink(temp_file)
            except:
                pass
        self._temp_files.clear()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.cleanup()
