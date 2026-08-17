import os
import tempfile
import logging
from app.services.ssh_utils import SSHUtils

logger = logging.getLogger(__name__)


async def deploy_config(
    ssh,
    config_content: str,
    remote_path: str,
    mode: int = 0o644,
) -> dict:
    config_temp_path = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", delete=False) as f:
            f.write(config_content)
            config_temp_path = f.name

        sftp = ssh.open_sftp()
        try:
            sftp.put(config_temp_path, remote_path)
            sftp.chmod(remote_path, mode)
        finally:
            sftp.close()

        exit_code, output, error = SSHUtils.execute_command(ssh, "nginx -t")
        if exit_code != 0:
            return {"success": False, "message": f"配置测试失败: {error}"}

        exit_code, output, error = SSHUtils.execute_command(ssh, "nginx -s reload")
        if exit_code != 0:
            return {"success": False, "message": f"配置重载失败: {error}"}

        return {"success": True, "message": "配置已成功重载"}
    except Exception as e:
        logger.exception("部署配置失败")
        return {"success": False, "message": f"部署失败: {str(e)}"}
    finally:
        if config_temp_path and os.path.exists(config_temp_path):
            try:
                os.unlink(config_temp_path)
            except Exception:
                pass
