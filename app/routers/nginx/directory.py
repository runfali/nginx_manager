from fastapi import APIRouter, Depends, HTTPException, Request, Form
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from sqlalchemy.orm import Session
from typing import Optional, List
import os
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
from app.routers.auth import get_current_active_user
from app.core.templates import templates
from app.services.ssh_utils import SSHUtils
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

    # 获取环境列表（用于下拉选择）
    environments = db.query(Environment).filter(Environment.is_active == True).all()

    # 如果不是超级用户，过滤掉PRD环境
    if not current_user.is_superuser:
        environments = Environment.filter_prd(environments)

    # 确定当前路径
    current_path = path or ""
    full_path = (
        os.path.join(env.nginx_path, current_path) if current_path else env.nginx_path
    )

    # 预设文件路径
    suggested_file_path = os.path.join(full_path, "new_config.conf")

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
        except HTTPException:
            return templates.TemplateResponse(
                "config_create.html",
                {
                    "request": request,
                    "error": "SSH连接失败",
                    "current_user": current_user,
                    "env_id": env_id,
                },
            )

        sftp = ssh.open_sftp()
        sftp.put(config_temp_path, file_path)
        sftp.chmod(file_path, 0o644)

    except Exception as e:
        logger.exception("上传配置文件失败")

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
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    config = db.query(NginxConfig).filter(NginxConfig.id == config_id).first()
    if not config:
        raise HTTPException(status_code=404, detail="配置不存在")

    return templates.TemplateResponse(
        "config_view.html",
        {"request": request, "config": config, "current_user": current_user},
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
    config.name = name
    config.environment = env.id
    config.server_ip = env.server_ip
    config.file_path = file_path
    config.content = content
    config.updated_by = current_user.id

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
                backup_path = os.path.join(backup_dir, backup_name)

                SSHUtils.execute_command(ssh, f"mkdir -p {backup_dir}")
                SSHUtils.execute_command(
                    ssh, f"cp {config.file_path} {backup_path}"
                )

                SSHUtils.execute_command(
                    ssh,
                    f"ls -t {backup_dir}/{basename}*.bak | tail -n +6 | xargs -r rm -f",
                )
        finally:
            sftp.close()
    except Exception:
        logger.exception("远程备份失败，保存操作已完成")

    return RedirectResponse(
        url=f"/configs/browse/view/{config.id}", status_code=status.HTTP_302_FOUND
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

    # 确定当前路径
    current_path = path or ""
    full_path = (
        os.path.join(env.nginx_path, current_path) if current_path else env.nginx_path
    )

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
            # 构建文件路径列表进行批量查询
            file_paths = [os.path.join(full_path, name) for name in conf_files]
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

            item_full_path = os.path.join(current_path, name) if current_path else name

            # 如果是文件，检查是否已在数据库中
            config_id = None
            if not is_dir and name.endswith(".conf"):
                file_path = os.path.join(full_path, name)
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
