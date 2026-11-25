"""配置版本历史与回滚的公共服务。

版本策略：
- 保留 KEEP_VERSIONS 条（当前内容 + 7 个历史），超出后按 version_no 从旧到新裁剪；
- 裁剪只删最旧的，version_no 不回收、不重置，用户看到的 v5 永远是同一份内容；
- 老配置没有任何版本时，首次访问会自动补一条 init 快照作为"回到最初"的锚点。
"""

import difflib
import logging
from typing import Dict, List, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.nginx_config import NginxConfig
from app.models.nginx_config_version import NginxConfigVersion

logger = logging.getLogger(__name__)

# 「最近 7 次」= 当前内容 + 7 个历史版本
KEEP_VERSIONS = 8

CHANGE_TYPE_LABELS = {
    "create": "新建",
    "update": "编辑",
    "sync": "同步",
    "rollback": "回滚",
    "init": "初始",
}

CHANGE_TYPE_ICONS = {
    "create": "fa-plus",
    "update": "fa-pen",
    "sync": "fa-cloud-download-alt",
    "rollback": "fa-undo-alt",
    "init": "fa-flag",
}


def change_type_label(change_type: Optional[str]) -> str:
    return CHANGE_TYPE_LABELS.get(change_type or "", change_type or "未知")


def change_type_icon(change_type: Optional[str]) -> str:
    return CHANGE_TYPE_ICONS.get(change_type or "", "fa-code-branch")


def get_versions(
    db: Session, config_id: int, limit: int = KEEP_VERSIONS
) -> List[NginxConfigVersion]:
    """按版本号倒序取该配置的历史版本（最新在前）。"""
    return (
        db.query(NginxConfigVersion)
        .filter(NginxConfigVersion.config_id == config_id)
        .order_by(NginxConfigVersion.version_no.desc())
        .limit(limit)
        .all()
    )


def get_latest_version(
    db: Session, config_id: int
) -> Optional[NginxConfigVersion]:
    return (
        db.query(NginxConfigVersion)
        .filter(NginxConfigVersion.config_id == config_id)
        .order_by(NginxConfigVersion.version_no.desc())
        .first()
    )


def _next_version_no(db: Session, config_id: int) -> int:
    current = (
        db.query(func.max(NginxConfigVersion.version_no))
        .filter(NginxConfigVersion.config_id == config_id)
        .scalar()
    )
    return int(current or 0) + 1


def prune_versions(db: Session, config_id: int, keep: int = KEEP_VERSIONS) -> int:
    """只保留最近的 keep 条版本快照，返回删除条数（不重置版本号）。"""
    keep_ids = [
        row[0]
        for row in db.query(NginxConfigVersion.id)
        .filter(NginxConfigVersion.config_id == config_id)
        .order_by(NginxConfigVersion.version_no.desc())
        .limit(keep)
        .all()
    ]
    if not keep_ids:
        return 0
    return (
        db.query(NginxConfigVersion)
        .filter(
            NginxConfigVersion.config_id == config_id,
            ~NginxConfigVersion.id.in_(keep_ids),
        )
        .delete(synchronize_session=False)
    )


def _append_version(
    db: Session,
    config_id: int,
    content: str,
    change_type: str,
    user_id: Optional[int],
    note: Optional[str],
) -> NginxConfigVersion:
    version = NginxConfigVersion(
        config_id=config_id,
        version_no=_next_version_no(db, config_id),
        content=content or "",
        change_type=change_type,
        change_note=note,
        created_by=user_id,
    )
    db.add(version)
    db.flush()
    return version


def record_version(
    db: Session,
    config: NginxConfig,
    content: str,
    change_type: str,
    user_id: Optional[int] = None,
    note: Optional[str] = None,
    force: bool = False,
    previous_content: Optional[str] = None,
) -> Optional[NginxConfigVersion]:
    """追加一条版本快照，调用方负责 db.commit()。

    - 内容与上一版本相同时默认不记录（空保存不产生噪音版本）；
    - 老配置首次纳入版本管理时，先用 previous_content（缺省用当前 content）
      补一条 init，再记录本次变更，保证历史链不断档。
    """
    has_any = (
        db.query(NginxConfigVersion.id)
        .filter(NginxConfigVersion.config_id == config.id)
        .first()
    )
    # 新建（create）本身就是首版，不需要再补 init；只有老配置的后续变更才需要
    if has_any is None and change_type not in ("init", "create"):
        _append_version(
            db,
            config.id,
            config.content if previous_content is None else previous_content,
            "init",
            user_id,
            "首次纳入版本管理，记录当时内容",
        )

    latest = get_latest_version(db, config.id)
    if not force and latest is not None and latest.content == (content or ""):
        return None

    version = _append_version(
        db, config.id, content, change_type, user_id, note
    )
    prune_versions(db, config.id)
    return version


def ensure_initial_version(
    db: Session, config: NginxConfig, user_id: Optional[int] = None
) -> bool:
    """老配置首次打开详情页时补一条 init 版本；已存在则不动。"""
    has_any = (
        db.query(NginxConfigVersion.id)
        .filter(NginxConfigVersion.config_id == config.id)
        .first()
    )
    if has_any is not None:
        return False
    _append_version(
        db, config.id, config.content, "init", user_id, "首次纳入版本管理，记录当时内容"
    )
    prune_versions(db, config.id)
    db.commit()
    return True


def build_diff_rows(
    old_text: Optional[str], new_text: Optional[str], context: int = 3
) -> List[Dict[str, object]]:
    """生成带行号的对齐 diff 行，供模板渲染。

    行类型：context / add / del / skip（段落省略）。
    """
    old_lines = (old_text or "").splitlines()
    new_lines = (new_text or "").splitlines()
    matcher = difflib.SequenceMatcher(None, old_lines, new_lines)
    rows: List[Dict[str, object]] = []

    for group in matcher.get_grouped_opcodes(context):
        if rows:
            rows.append({"type": "skip"})
        for tag, i1, i2, j1, j2 in group:
            if tag == "equal":
                for offset, line in enumerate(old_lines[i1:i2]):
                    rows.append(
                        {
                            "type": "context",
                            "old_no": i1 + offset + 1,
                            "new_no": j1 + offset + 1,
                            "text": line,
                        }
                    )
            elif tag == "delete":
                for offset, line in enumerate(old_lines[i1:i2]):
                    rows.append(
                        {
                            "type": "del",
                            "old_no": i1 + offset + 1,
                            "new_no": None,
                            "text": line,
                        }
                    )
            elif tag == "insert":
                for offset, line in enumerate(new_lines[j1:j2]):
                    rows.append(
                        {
                            "type": "add",
                            "old_no": None,
                            "new_no": j1 + offset + 1,
                            "text": line,
                        }
                    )
            elif tag == "replace":
                for offset, line in enumerate(old_lines[i1:i2]):
                    rows.append(
                        {
                            "type": "del",
                            "old_no": i1 + offset + 1,
                            "new_no": None,
                            "text": line,
                        }
                    )
                for offset, line in enumerate(new_lines[j1:j2]):
                    rows.append(
                        {
                            "type": "add",
                            "old_no": None,
                            "new_no": j1 + offset + 1,
                            "text": line,
                        }
                    )
    return rows


def diff_stats(rows: List[Dict[str, object]]) -> Dict[str, int]:
    added = sum(1 for row in rows if row["type"] == "add")
    removed = sum(1 for row in rows if row["type"] == "del")
    return {"added": added, "removed": removed}
