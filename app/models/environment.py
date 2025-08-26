from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, text
from sqlalchemy.sql import func
from app.core.database import Base
from sqlalchemy.orm import Mapped, mapped_column


class Environment(Base):
    __tablename__ = "environments"

    id = Column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(
        String(50), unique=True, index=True, nullable=False
    )  # 环境名称：dev, test, rebuild-test, uat, prd
    description: Mapped[str | None] = mapped_column(Text, nullable=True)  # 环境描述
    server_ip: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # 环境对应的服务器IP
    ssh_port: Mapped[int] = mapped_column(Integer, default=22)  # SSH端口
    nginx_path: Mapped[str] = mapped_column(
        String(255), default="/etc/nginx"
    )  # Nginx安装路径
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)  # 是否激活
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    def __repr__(self):
        return f"<Environment {self.name}>"
