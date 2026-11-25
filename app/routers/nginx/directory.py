from fastapi import APIRouter, Depends, HTTPException, Request, Form
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from sqlalchemy.orm import Session
from typing import Optional, List
import os
import re
import shlex
import tempfile
import logging
import datetime
from fastapi import status

logger = logging.getLogger(__name__)

from app.core.database import get_db
from app.core.security import decrypt_private_key
from app.models.nginx_config import NginxConfig
from app.models.environment import Environment
from app.models.user import User
from app.routers.auth import get_current_active_user, ensure_env_access
from app.core.templates import templates
from app.models.nginx_config_version import NginxConfigVersion
from app.services.config_versions import (
    KEEP_VERSIONS,
    build_diff_rows,
    change_type_icon,
    change_type_label,
    diff_stats,
    ensure_initial_version,
    get_latest_version,
    get_versions,
    record_version,
)
from app.services.ssh_utils import (
    SSHUtils,
    validate_relative_path,
    validate_file_under_base,
)
from app.routers.nginx.operations import test_config as nginx_test_config
from app.routers.nginx.operations import reload_test as nginx_reload_test, reload_exec as nginx_reload_exec

router = APIRouter()


# 创建配置页面 - 所有已登录用户可访问
@router.get("/create/{env_id}", response_class=HTMLResponse)
async def create_config_page(
    request: Request,
    env_id: int,
    path: Optional[str] = None,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    # 获取环境信息
    env = db.query(Environment).filter(Environment.id == env_id).first()
    if not env:
        raise HTTPException(status_code=404, detail="环境不存在")

    # 非超级管理员禁止访问PRD环境
    ensure_env_access(env, current_user)

    # 获取环境列表（用于下拉选择）
    environments = db.query(Environment).filter(Environment.is_active == True).all()

    # 如果不是超级用户，过滤掉PRD环境
    if not current_user.is_superuser:
        environments = Environment.filter_prd(environments)

    # 确定当前路径（校验相对路径，防止绝对路径/.. 浏览服务器任意目录）
    current_path = path or ""
    try:
        full_path = validate_relative_path(env.nginx_path, current_path)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"非法的路径: {e}")

    # 预设文件路径
    suggested_file_path = f"{full_path}/new_config.conf"

    return templates.TemplateResponse(
        "config_create.html",
        {
            "request": request,
            "environments": environments,
            "current_user": current_user,
            "env_id": env_id,
            "current_path": current_path,
            "suggested_file_path": suggested_file_path,
            "selected_environment": env.name,
        },
    )


# 创建配置处理 - 所有已登录用户可访问
@router.post("/create/{env_id}")
async def create_config(
    request: Request,
    env_id: int,
    name: str = Form(...),
    environment: str = Form(...),
    file_path: str = Form(...),
    content: str = Form(...),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    # 获取环境信息
    env = db.query(Environment).filter(Environment.id == env_id).first()
    if not env:
        raise HTTPException(status_code=404, detail="环境不存在")

    # 非超级管理员禁止操作PRD环境
    ensure_env_access(env, current_user)

    # 检查环境是否存在
    selected_env = (
        db.query(Environment)
        .filter(Environment.name == environment, Environment.is_active == True)
        .first()
    )
    if not selected_env:
        return templates.TemplateResponse(
            "config_create.html",
            {
                "request": request,
                "error": "环境不存在或未激活",
                "current_user": current_user,
                "env_id": env_id,
            },
        )

    # 目标环境同样受PRD权限约束
    ensure_env_access(selected_env, current_user)

    # 检查配置名称是否已存在于该环境
    db_config = (
        db.query(NginxConfig)
        .filter(NginxConfig.name == name, NginxConfig.environment == selected_env.id)
        .first()
    )
    if db_config:
        return templates.TemplateResponse(
            "config_create.html",
            {
                "request": request,
                "error": "该环境下已存在同名配置",
                "current_user": current_user,
                "env_id": env_id,
            },
        )

    # 校验目标文件路径：必须是该环境Nginx目录内的绝对路径
    # （防止把任意文件写到服务器任意位置，如 authorized_keys）
    try:
        file_path = validate_file_under_base(selected_env.nginx_path, file_path)
    except ValueError as e:
        return templates.TemplateResponse(
            "config_create.html",
            {
                "request": request,
                "error": f"非法的文件路径: {e}",
                "current_user": current_user,
                "env_id": env_id,
            },
        )

    # 创建新配置
    new_config = NginxConfig(
        name=name,
        environment=selected_env.id,
        server_ip=selected_env.server_ip,
        file_path=file_path,
        content=content,
        created_by=current_user.id,
        updated_by=current_user.id,
    )

    db.add(new_config)
    db.flush()  # 先拿到 id，才能写首个版本快照
    record_version(
        db,
        new_config,
        new_config.content,
        "create",
        current_user.id,
        note="新建配置",
        force=True,
    )
    db.commit()
    db.refresh(new_config)

    # 将配置文件上传到服务器
    temp_path = None
    ssh = None
    sftp = None
    config_temp_path = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", delete=False) as config_temp_file:
            config_temp_file.write(content)
            config_temp_path = config_temp_file.name

        try:
            ssh = SSHUtils.get_ssh_or_fail(
                hostname=selected_env.server_ip,
                port=selected_env.ssh_port,
                username="root",
                private_key_content=decrypt_private_key(current_user.ssh_private_key),
            )
        except HTTPException as http_ex:
            return templates.TemplateResponse(
                "config_create.html",
                {
                    "request": request,
                    "error": str(http_ex.detail),
                    "current_user": current_user,
                    "env_id": env_id,
                },
            )

        sftp = ssh.open_sftp()
        sftp.put(config_temp_path, file_path)
        sftp.chmod(file_path, 0o644)

    except Exception as e:
        # 上传失败不再静默吞掉：明确告知，DB记录保留可稍后通过同步功能重推
        logger.exception("上传配置文件失败")
        return templates.TemplateResponse(
            "config_create.html",
            {
                "request": request,
                "error": f"配置已保存到数据库，但上传到服务器失败: {e}",
                "current_user": current_user,
                "env_id": env_id,
            },
        )

    finally:
        if config_temp_path is not None and os.path.exists(config_temp_path):
            os.unlink(config_temp_path)
        if sftp:
            sftp.close()

    # 创建成功后直接跳转到配置查看页面
    return RedirectResponse(
        url=f"/configs/browse/view/{new_config.id}", status_code=status.HTTP_302_FOUND
    )


# 查看配置页面 - 所有已登录用户可访问
@router.get("/view/{config_id}", response_class=HTMLResponse)
async def view_config_page(
    request: Request,
    config_id: int,
    rollback: Optional[str] = None,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    config = db.query(NginxConfig).filter(NginxConfig.id == config_id).first()
    if not config:
        raise HTTPException(status_code=404, detail="配置不存在")

    # 非超级管理员禁止查看PRD环境的配置
    ensure_env_access(config.env, current_user)

    # 老配置首次纳入版本管理：补一条 init 版本作为「回到最初」的锚点
    ensure_initial_version(db, config, current_user.id)

    versions = get_versions(db, config.id)
    latest = get_latest_version(db, config.id)

    return templates.TemplateResponse(
        "config_view.html",
        {
            "request": request,
            "config": config,
            "current_user": current_user,
            "versions": versions,
            "latest_version_id": latest.id if latest else None,
            "keep_versions": KEEP_VERSIONS,
            "change_type_label": change_type_label,
            "change_type_icon": change_type_icon,
            "rollback_state": rollback,
        },
    )


# 编辑配置页面 - 所有已登录用户可访问
@router.get("/view/{config_id}/edit", response_class=HTMLResponse)
async def edit_config_page(
    request: Request,
    config_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    config = db.query(NginxConfig).filter(NginxConfig.id == config_id).first()
    if not config:
        raise HTTPException(status_code=404, detail="配置不存在")

    # 非超级管理员禁止编辑PRD环境的配置
    ensure_env_access(config.env, current_user)

    # 获取环境列表
    environments = db.query(Environment).filter(Environment.is_active == True).all()

    # 如果不是超级用户，过滤掉PRD环境
    if not current_user.is_superuser:
        environments = Environment.filter_prd(environments)

    return templates.TemplateResponse(
        "config_edit.html",
        {
            "request": request,
            "config": config,
            "environments": environments,
            "current_user": current_user,
        },
    )


# 更新配置处理 - 所有已登录用户可访问
@router.post("/view/{config_id}/edit")
async def update_config(
    request: Request,
    config_id: int,
    name: str = Form(...),
    environment: str = Form(...),
    file_path: str = Form(...),
    content: str = Form(...),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    config = db.query(NginxConfig).filter(NginxConfig.id == config_id).first()
    if not config:
        raise HTTPException(status_code=404, detail="配置不存在")

    # 非超级管理员禁止修改PRD环境的配置
    ensure_env_access(config.env, current_user)

    # 检查环境是否存在
    env = (
        db.query(Environment)
        .filter(Environment.name == environment, Environment.is_active == True)
        .first()
    )
    if not env:
        return templates.TemplateResponse(
            "config_edit.html",
            {
                "request": request,
                "config": config,
                "error": "环境不存在或未激活",
                "current_user": current_user,
            },
        )

    # 目标环境同样受PRD权限约束
    ensure_env_access(env, current_user)

    # 校验目标文件路径：必须位于目标环境Nginx目录内
    try:
        file_path = validate_file_under_base(env.nginx_path, file_path)
    except ValueError as e:
        return templates.TemplateResponse(
            "config_edit.html",
            {
                "request": request,
                "config": config,
                "error": f"非法的文件路径: {e}",
                "current_user": current_user,
            },
        )

    # 检查配置名称是否已被其他配置使用
    db_config = (
        db.query(NginxConfig)
        .filter(
            NginxConfig.name == name,
            NginxConfig.environment == env.id,
            NginxConfig.id != config_id,
        )
        .first()
    )
    if db_config:
        return templates.TemplateResponse(
            "config_edit.html",
            {
                "request": request,
                "config": config,
                "error": "该环境下已存在同名配置",
                "current_user": current_user,
            },
        )

    # 更新配置信息
    previous_content = config.content
    config.name = name
    config.environment = env.id
    config.server_ip = env.server_ip
    config.file_path = file_path
    config.content = content
    config.updated_by = current_user.id

    # 内容真的变了才产生新版本（空保存不留下噪音版本）
    record_version(
        db,
        config,
        content,
        "update",
        current_user.id,
        note="编辑保存",
        previous_content=previous_content,
    )

    db.commit()
    db.refresh(config)

    try:
        ssh = SSHUtils.get_ssh_or_fail(
            hostname=env.server_ip,
            port=env.ssh_port,
            username="root",
            private_key_content=decrypt_private_key(current_user.ssh_private_key),
        )
        sftp = ssh.open_sftp()
        try:
            try:
                sftp.stat(config.file_path)
            except FileNotFoundError:
                pass
            else:
                backup_dir = "/usr/local/src/nginx_config_backups"
                timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                basename = os.path.basename(config.file_path)
                backup_name = f"{basename}.{timestamp}.bak"
                # 远端为Linux路径，显式用/拼接（Windows宿主机上os.path.join会产生反斜杠）
                backup_path = f"{backup_dir}/{backup_name}"

                # 远端路径一律shlex.quote，防止file_path拼入shell元字符
                SSHUtils.execute_command(
                    ssh, f"mkdir -p {shlex.quote(backup_dir)}"
                )
                SSHUtils.execute_command(
                    ssh,
                    f"cp {shlex.quote(config.file_path)} {shlex.quote(backup_path)}",
                )

                # 备份轮转：basename须通过白名单校验才允许进入glob
                if re.fullmatch(r"[A-Za-z0-9._-]+", basename or ""):
                    SSHUtils.execute_command(
                        ssh,
                        "cd {} && ls -t -- {}*.bak | tail -n +6 | xargs -r rm -f --".format(
                            shlex.quote(backup_dir), shlex.quote(basename)
                        ),
                    )
        finally:
            sftp.close()
    except Exception:
        logger.exception("远程备份失败，保存操作已完成")

    return RedirectResponse(
        url=f"/configs/browse/view/{config.id}", status_code=status.HTTP_302_FOUND
    )


# 版本差异页 - 所有已登录用户可访问
@router.get("/view/{config_id}/diff/{version_id}", response_class=HTMLResponse)
async def view_config_diff(
    request: Request,
    config_id: int,
    version_id: int,
    base: str = "prev",
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    config = db.query(NginxConfig).filter(NginxConfig.id == config_id).first()
    if not config:
        raise HTTPException(status_code=404, detail="配置不存在")

    # 非超级管理员禁止查看PRD环境的配置
    ensure_env_access(config.env, current_user)

    version = (
        db.query(NginxConfigVersion)
        .filter(
            NginxConfigVersion.id == version_id,
            NginxConfigVersion.config_id == config_id,
        )
        .first()
    )
    if not version:
        raise HTTPException(status_code=404, detail="版本不存在")

    # 上一版本：版本号比当前小的最近一条
    previous_version = (
        db.query(NginxConfigVersion)
        .filter(
            NginxConfigVersion.config_id == config_id,
            NginxConfigVersion.version_no < version.version_no,
        )
        .order_by(NginxConfigVersion.version_no.desc())
        .first()
    )

    if base == "current":
        # 该版本 vs 当前内容：用来确认「这个版本之后又改了什么」
        old_text = version.content
        old_label = f"v{version.version_no}"
        new_text = config.content
        new_label = "当前内容"
    else:
        old_text = previous_version.content if previous_version else ""
        old_label = (
            f"v{previous_version.version_no}" if previous_version else "（无更早版本）"
        )
        new_text = version.content
        new_label = f"v{version.version_no}"

    rows = build_diff_rows(old_text, new_text)
    stats = diff_stats(rows)

    latest = get_latest_version(db, config_id)

    return templates.TemplateResponse(
        "config_diff.html",
        {
            "request": request,
            "config": config,
            "version": version,
            "base": "current" if base == "current" else "prev",
            "old_label": old_label,
            "new_label": new_label,
            "rows": rows,
            "stats": stats,
            "is_current": latest is not None and latest.id == version.id,
            "has_changes": (stats["added"] + stats["removed"]) > 0,
            "has_previous": previous_version is not None,
            "current_user": current_user,
            "change_type_label": change_type_label,
            "change_type_icon": change_type_icon,
        },
    )


# 一键回滚 - 所有已登录用户可访问（与编辑同源权限：PRD 仅超级管理员）
@router.post("/view/{config_id}/rollback/{version_id}")
async def rollback_config(
    request: Request,
    config_id: int,
    version_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    config = db.query(NginxConfig).filter(NginxConfig.id == config_id).first()
    if not config:
        raise HTTPException(status_code=404, detail="配置不存在")

    # 与编辑保存使用同一套守卫，避免回滚成为绕过 PRD 限制的通道
    ensure_env_access(config.env, current_user)

    version = (
        db.query(NginxConfigVersion)
        .filter(
            NginxConfigVersion.id == version_id,
            NginxConfigVersion.config_id == config_id,
        )
        .first()
    )
    if not version:
        raise HTTPException(status_code=404, detail="版本不存在")

    # 内容已经一致：不动库，直接回详情页提示
    if config.content == version.content:
        return RedirectResponse(
            url=f"/configs/browse/view/{config_id}?rollback=noop",
            status_code=status.HTTP_302_FOUND,
        )

    # revert 语义：内容覆盖为历史版本，并追加一条 rollback 记录，绝不删除任何历史
    previous_content = config.content
    config.content = version.content
    config.updated_by = current_user.id
    record_version(
        db,
        config,
        version.content,
        "rollback",
        current_user.id,
        note=f"回滚到 v{version.version_no}",
        force=True,
        previous_content=previous_content,
    )
    db.commit()
    db.refresh(config)

    # 只回滚库内配置内容：不发 SSH、不自动 reload。
    # 生效仍由用户手动点击「重载配置」，统一走 nginx -t + 失败保护链路。
    return RedirectResponse(
        url=f"/configs/browse/view/{config_id}?rollback=done",
        status_code=status.HTTP_302_FOUND,
    )


# 目录浏览页面 - 所有已登录用户可访问
@router.get("/browse/{env_id}", response_class=HTMLResponse)
async def browse_directory(
    request: Request,
    env_id: int,
    path: Optional[str] = None,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    # 获取环境信息
    env = db.query(Environment).filter(Environment.id == env_id).first()
    if not env:
        raise HTTPException(status_code=404, detail="环境不存在")

    # 非超级管理员禁止浏览PRD环境
    ensure_env_access(env, current_user)

    # 确定当前路径（校验相对路径，防止绝对路径/.. 浏览服务器任意目录）
    current_path = path or ""
    try:
        full_path = validate_relative_path(env.nginx_path, current_path)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"非法的路径: {e}")

    # 生成面包屑导航
    breadcrumbs = []
    if current_path:
        parts = current_path.split("/")
        current = ""
        for part in parts:
            if part:
                current = os.path.join(current, part) if current else part
                breadcrumbs.append({"name": part, "path": current})

    # 连接服务器并获取目录内容
    ssh = None
    sftp = None
    items = []
    error = None
    success_message = request.query_params.get("success_message")

    try:
        connection, ssh = SSHUtils.get_ssh_connection(
            hostname=env.server_ip,
            port=env.ssh_port,
            username="root",
            private_key_content=decrypt_private_key(current_user.ssh_private_key),
        )

        if ssh is None:
            return templates.TemplateResponse(
                "directory_browser.html",
                {
                    "request": request,
                    "current_user": current_user,
                    "environment": env,
                    "env_id": env_id,
                    "current_path": current_path,
                    "breadcrumbs": breadcrumbs,
                    "items": items,
                    "error": "SSH连接失败",
                },
            )

        try:
            file_info = SSHUtils.get_directory_info(ssh, full_path, timeout=30)
        except Exception as e:
            return templates.TemplateResponse(
                "directory_browser.html",
                {
                    "request": request,
                    "current_user": current_user,
                    "environment": env,
                    "env_id": env_id,
                    "current_path": current_path,
                    "breadcrumbs": breadcrumbs,
                    "items": items,
                    "error": f"获取目录内容失败: {str(e)}",
                },
            )

        # 批量查询数据库中的配置文件
        conf_files = [
            name
            for name, info in file_info.items()
            if not info["is_dir"] and name.endswith(".conf")
        ]

        config_map = {}
        if conf_files:
            # 构建文件路径列表进行批量查询（远端为Linux，统一用/拼接，
            # 避免Windows宿主机上os.path.join产生反斜杠导致匹配失败）
            file_paths = [f"{full_path}/{name}" for name in conf_files]
            configs = (
                db.query(NginxConfig)
                .filter(
                    NginxConfig.file_path.in_(file_paths),
                    NginxConfig.environment == env.id,
                )
                .all()
            )
            config_map = {config.file_path: config.id for config in configs}

        # 处理文件信息
        for name, info in file_info.items():
            is_dir = info["is_dir"]

            # 只显示目录和.conf文件，过滤其他文件
            if not is_dir and not name.endswith(".conf"):
                continue

            item_full_path = f"{current_path}/{name}" if current_path else name

            # 如果是文件，检查是否已在数据库中
            config_id = None
            if not is_dir and name.endswith(".conf"):
                file_path = f"{full_path}/{name}"
                config_id = config_map.get(file_path)

            items.append(
                {
                    "name": name,
                    "is_dir": is_dir,
                    "full_path": item_full_path,
                    "config_id": config_id,
                }
            )

        # 排序：目录在前，文件在后，按名称排序
        items.sort(key=lambda x: (not x["is_dir"], x["name"]))

    except Exception as e:
        error = f"获取目录内容失败: {str(e)}"

    finally:
        # 关闭SFTP连接
        if sftp:
            sftp.close()
        # 不需要关闭SSH连接，由连接池管理

    return templates.TemplateResponse(
        "directory_browser.html",
        {
            "request": request,
            "current_user": current_user,
            "environment": env,
            "env_id": env_id,
            "current_path": current_path,
            "breadcrumbs": breadcrumbs,
            "items": items,
            "error": error,
            "success_message": success_message,
        },
    )


# 添加测试配置的路由
@router.post("/view/{config_id}/test")
async def test_config(
    config_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    # 直接调用nginx.operations模块中的test_config函数
    return await nginx_test_config(config_id, current_user, db)


# 重载前测试路由
@router.post("/view/{config_id}/reload-test")
async def reload_test_route(
    config_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    return await nginx_reload_test(config_id, current_user, db)


# 执行重载路由
@router.post("/view/{config_id}/reload-exec")
async def reload_exec_route(
    config_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    return await nginx_reload_exec(config_id, current_user, db)
