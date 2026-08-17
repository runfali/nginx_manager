from pydantic_settings import BaseSettings
from typing import List, Optional
import os
from dotenv import load_dotenv

# 加载.env文件中的环境变量
load_dotenv()


class Settings(BaseSettings):
    # 数据库配置（请在 .env 中设置实际连接串）
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL", "mysql+pymysql://user:password@localhost:3306/nginx_manager"
    )

    # 安全配置
    SECRET_KEY: str = os.getenv(
        "SECRET_KEY", "your-secret-key-for-jwt-token-generation"
    )
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
