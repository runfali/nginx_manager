from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Boolean
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship, Mapped, mapped_column
from app.core.database import Base


class NginxConfig(Base):
    __tablename__ = "nginx_configs"

    id = Column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(
        String(255), nullable=False, index=True
    )  # 配置文件名称
    environment: Mapped[str] = mapped_column(
        String(50), nullable=False, index=True
    )  # 环境：dev, test, rebuild-test, uat, prd
    server_ip: Mapped[str] = mapped_column(String(50), nullable=False)  # 服务器IP地址
    file_path: Mapped[str] = mapped_column(
        String(255), nullable=False
    )  # 配置文件在服务器上的路径
    content: Mapped[str] = mapped_column(Text, nullable=False)  # 配置文件内容
    is_active = Column(Boolean, default=True)  # 是否为活动配置
    created_by = Column(Integer, ForeignKey("users.id"))  # 创建者ID
    updated_by: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id")
    )  # 最后更新者ID
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # 关联关系
    creator = relationship("User", foreign_keys=[created_by], backref="created_configs")
    updater = relationship("User", foreign_keys=[updated_by], backref="updated_configs")

    def __repr__(self):
        return f"<NginxConfig {self.name} ({self.environment})>"
