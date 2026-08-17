from typing import Dict, Optional, Tuple
import paramiko
import tempfile
import os
import time
import atexit


class SSHConnection:
    """SSH连接类，用于存储SSH连接信息"""

    _registered_temp_paths = set()
    _atexit_registered = False

    def __init__(
        self,
        hostname: str,
        port: int,
        username: str,
        private_key_content: Optional[str] = None,
        private_key_path: Optional[str] = None,
    ):
        self.hostname = hostname
        self.port = port
        self.username = username
        self.private_key_content = private_key_content
        self.private_key_path = private_key_path
        self.ssh_client: Optional[paramiko.SSHClient] = None
        self.sftp_client: Optional[paramiko.SFTPClient] = None
        self.last_used: float = time.time()
        self._temp_key_path: Optional[str] = None

        if not SSHConnection._atexit_registered:
            atexit.register(SSHConnection._cleanup_all_temp_files)
            SSHConnection._atexit_registered = True

        self._connect()

    @classmethod
    def _cleanup_all_temp_files(cls):
        for path in list(cls._registered_temp_paths):
            if os.path.exists(path):
                try:
                    os.unlink(path)
                except Exception:
                    pass
        cls._registered_temp_paths.clear()

    def _connect(self) -> None:
        """创建SSH连接"""
        try:
            # 创建SSH客户端
            self.ssh_client = paramiko.SSHClient()
            self.ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

            # 确定使用的私钥路径
            key_filename = None

            # 如果提供了私钥内容，创建临时文件
            if self.private_key_content:
                with tempfile.NamedTemporaryFile(mode="w", delete=False) as temp_file:
                    temp_file.write(self.private_key_content)
                    self._temp_key_path = temp_file.name
                    SSHConnection._registered_temp_paths.add(self._temp_key_path)
                    key_filename = self._temp_key_path
            # 如果提供了私钥路径，直接使用
            elif self.private_key_path and os.path.exists(self.private_key_path):
                key_filename = self.private_key_path
            # 如果没有提供有效的私钥，将抛出异常，由连接池处理

            # 连接SSH服务器
            self.ssh_client.connect(
                hostname=self.hostname,
                port=self.port,
                username=self.username,
                key_filename=key_filename,
                allow_agent=False,  # 禁用SSH代理
                look_for_keys=False,  # 禁用自动查找密钥
                # 移除禁用算法选项，以确保能够与服务器正确协商公钥算法
                timeout=10,  # 设置连接超时时间
            )

        except Exception as e:
            self.close()
            raise Exception(f"SSH连接失败: {str(e)}")

    def close(self) -> None:
        """关闭连接并清理资源"""
        # 关闭SFTP连接
        if self.sftp_client:
            try:
                self.sftp_client.close()
            except Exception:
                pass
            self.sftp_client = None

        # 关闭SSH连接
        if self.ssh_client:
            try:
                self.ssh_client.close()
            except Exception:
                pass
            self.ssh_client = None

        # 删除临时私钥文件
        if self._temp_key_path and os.path.exists(self._temp_key_path):
            try:
                os.unlink(self._temp_key_path)
            except Exception:
                pass
            SSHConnection._registered_temp_paths.discard(self._temp_key_path)
            self._temp_key_path = None


class SSHConnectionPool:
    """SSH连接池，用于管理SSH连接"""

    def __init__(self, max_connections: int = 10, connection_timeout: int = 300):
        self.max_connections = max_connections
        self.connection_timeout = connection_timeout  # 连接超时时间（秒）
        self.connections: Dict[str, SSHConnection] = {}
        self.default_key_path = "/data/nginx/AW"  # 默认SSH私钥路径

    def get_connection(
        self,
        hostname: str,
        port: int,
        username: str,
        private_key_content: Optional[str] = None,
        private_key_path: Optional[str] = None,
    ) -> SSHConnection:
        """获取SSH连接，如果连接池中存在则复用，否则创建新连接"""
        # 如果未提供私钥路径，使用默认路径
        if not private_key_path and not private_key_content:
            private_key_path = self.default_key_path

        # 生成连接键
        connection_key = f"{username}@{hostname}:{port}"

        # 检查连接是否存在且有效
        if connection_key in self.connections:
            connection = self.connections[connection_key]
            if connection.ssh_client:
                try:
                    connection.ssh_client.exec_command("echo ok", timeout=5)
                except Exception:
                    connection.close()
                    del self.connections[connection_key]
                else:
                    connection.last_used = time.time()
                    return connection

        # 如果连接池已满，清理最久未使用的连接
        if len(self.connections) >= self.max_connections:
            self._cleanup_connections()

        # 创建新连接
        connection = SSHConnection(
            hostname, port, username, private_key_content, private_key_path
        )
        self.connections[connection_key] = connection
        return connection

    def _cleanup_connections(self) -> None:
        """清理超时或最久未使用的连接"""
        current_time = time.time()
        # 找出超时的连接
        expired_keys = []
        for key, connection in self.connections.items():
            if current_time - connection.last_used > self.connection_timeout:
                expired_keys.append(key)

        # 关闭并移除超时连接
        for key in expired_keys:
            self.connections[key].close()
            del self.connections[key]

        # 如果仍然需要清理更多连接
        if len(self.connections) >= self.max_connections and not expired_keys:
            # 按最后使用时间排序
            sorted_connections = sorted(
                self.connections.items(), key=lambda x: x[1].last_used
            )
            # 关闭并移除最久未使用的连接
            oldest_key = sorted_connections[0][0]
            self.connections[oldest_key].close()
            del self.connections[oldest_key]

    def close_all(self) -> None:
        """关闭所有连接"""
        for connection in self.connections.values():
            connection.close()
        self.connections.clear()


# 创建全局连接池实例
connection_pool = SSHConnectionPool()
