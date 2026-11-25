from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.core.database import Base


class NginxConfigVersion(Base):
    """配置内容的全量版本快照。

    设计约定：
    - 每次写入 content 追加一条快照（不是 diff，diff 可随时算）；
    - version_no 在同一配置内单调自增，裁剪历史后不回收、不重置；
    - 回滚采用 revert 语义：追加一条 rollback 版本，绝不删除既有历史。
    """

    __tablename__ = "nginx_config_versions"

    id = Column(Integer, primary_key=True, index=True)
    config_id: Mapped[int] = mapped_column(
        ForeignKey("nginx_configs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    version_no: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    # create / update / sync / rollback / init
    change_type: Mapped[str] = mapped_column(String(20), nullable=False)
    change_note: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    config = relationship("NginxConfig", back_populates="versions")
    creator = relationship("User", foreign_keys=[created_by])

    __table_args__ = (
        Index("uq_nginx_config_version", "config_id", "version_no", unique=True),
    )

    def __repr__(self):
        return f"<NginxConfigVersion config={self.config_id} v{self.version_no} {self.change_type}>"
