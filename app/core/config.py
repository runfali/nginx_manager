from pydantic_settings import BaseSettings
from pydantic import field_validator
from typing import List, Optional
import logging
import os
import secrets
from dotenv import load_dotenv

# 加载.env文件中的环境变量
load_dotenv()

# JWT密钥占位值：来源于README示例，已被公开，绝不允许作为真实密钥使用
_PLACEHOLDER_SECRET_KEY = "your-secret-key-for-jwt-token-generation"


class Settings(BaseSettings):
    # 数据库配置
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL", "mysql+pymysql://devops:devops@10.200.0.141/nginx_manager"
    )

    # 安全配置：SECRET_KEY 不再使用公开的内置默认值。
    # 未配置或仍为README示例占位值时，自动生成一次性随机密钥，防止JWT被公开默认密钥伪造。
    SECRET_KEY: str = os.getenv("SECRET_KEY", "")

    @field_validator("SECRET_KEY", mode="before")
    @classmethod
    def _ensure_secret_key(cls, v):
        if not v or v == _PLACEHOLDER_SECRET_KEY:
            return secrets.token_hex(32)
        return v
    ALGORITHM: str = os.getenv("ALGORITHM", "HS256")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(
        os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30")
    )

    # 应用配置
    APP_NAME: str = os.getenv("APP_NAME", "Nginx配置管理平台")
    APP_VERSION: str = os.getenv("APP_VERSION", "0.1.0")
    APP_DESCRIPTION: str = os.getenv(
        "APP_DESCRIPTION", "用于管理多环境Nginx配置的Web平台"
    )
    DEBUG: bool = os.getenv("DEBUG", "true").lower() == "true"

    # 环境列表
    ENVIRONMENTS: List[str] = ["dev", "test", "rebuild-test", "uat", "prd"]

    class Config:
        env_file = ".env"
        case_sensitive = True


# 创建全局设置对象
settings = Settings()

if not os.getenv("SECRET_KEY") or os.getenv("SECRET_KEY") == _PLACEHOLDER_SECRET_KEY:
    logging.getLogger(__name__).warning(
        "SECRET_KEY 未配置或仍为占位值，已自动生成临时随机密钥，"
        "进程重启后所有登录会话将失效。请尽快在 .env 中配置固定的强随机 SECRET_KEY。"
    )
