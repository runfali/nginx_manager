from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Boolean
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship, Mapped, mapped_column
from app.core.database import Base
from app.models.environment import Environment


class NginxConfig(Base):
    __tablename__ = "nginx_configs"

    id = Column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(
        String(255), nullable=False, index=True
    )  # 配置文件名称
    environment: Mapped[int] = mapped_column(
        ForeignKey("environments.id"), nullable=False, index=True
    )
    server_ip: Mapped[str] = mapped_column(String(50), nullable=False)  # 服务器IP地址
    file_path: Mapped[str] = mapped_column(
        String(255), nullable=False, index=True
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)  # 配置文件内容
    is_active = Column(Boolean, default=True)  # 是否为活动配置
    created_by = Column(Integer, ForeignKey("users.id"))  # 创建者ID
    updated_by: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id")
    )  # 最后更新者ID
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    env = relationship("Environment", back_populates="configs")

    creator = relationship("User", foreign_keys=[created_by], backref="created_configs")
    updater = relationship("User", foreign_keys=[updated_by], backref="updated_configs")

    versions = relationship(
        "NginxConfigVersion",
        back_populates="config",
        cascade="all, delete-orphan",
        order_by="NginxConfigVersion.version_no.desc()",
    )

    def __repr__(self):
        return f"<NginxConfig {self.name} ({self.environment})>"


# 显式导入版本模型，确保它随 NginxConfig 一起注册到 Base.metadata。
# create_all 只建「已注册」的表，漏导入会导致 nginx_config_versions 建不出来。
from app.models.nginx_config_version import NginxConfigVersion  # noqa: E402,F401
