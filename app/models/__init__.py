"""数据模型包。

集中导入全部模型，确保 Base.metadata 在 create_all 时已注册所有表。
历史教训：漏导入的模型不会建表，运行期查询直接 500。
"""
from app.models.environment import Environment
from app.models.user import User
from app.models.nginx_config import NginxConfig
from app.models.nginx_config_version import NginxConfigVersion

__all__ = ["Environment", "User", "NginxConfig", "NginxConfigVersion"]
