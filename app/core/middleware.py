from fastapi import Request, status, HTTPException
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response
import logging
import traceback
from datetime import datetime

# 配置日志记录
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler("app.log"), logging.StreamHandler()],
)

logger = logging.getLogger(__name__)


class ErrorHandlerMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        try:
            response = await call_next(request)
            return response
        except HTTPException as e:
            # 已知 HTTP 异常（自带 status_code）
            status_code = e.status_code
            detail = str(e.detail) if hasattr(e, "detail") else str(e)

            # 记录HTTP异常日志
            logger.warning(
                "HTTP Exception\n"
                f"Status: {status_code}\n"
                f"Detail: {detail}\n"
                f"Path: {request.url.path}\n"
                f"Method: {request.method}\n"
                f"Client: {request.client.host if request.client else 'Unknown'}\n"
                f"Time: {datetime.now().isoformat()}"
            )

            # 根据请求类型返回响应
            if request.url.path.startswith("/api/"):
                return JSONResponse(
                    status_code=status_code,
                    content={
                        "detail": detail,
                        "path": request.url.path,
                        "timestamp": datetime.now().isoformat(),
                    },
                )
            else:
                from app.core.templates import templates

                return templates.TemplateResponse(
                    "error.html",
                    {
                        "request": request,
                        "status_code": status_code,
                        "detail": detail,
                        "timestamp": datetime.now().isoformat(),
                    },
                    status_code=status_code,
                )

        except Exception as e:
            # 未知异常，记录详细错误日志
            status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
            detail = "服务器内部错误"

            # 记录详细错误信息
            logger.error(
                "Internal Server Error\n"
                f"Error: {str(e)}\n"
                f"Traceback: {''.join(traceback.format_tb(e.__traceback__))}\n"
                f"Path: {request.url.path}\n"
                f"Method: {request.method}\n"
                f"Client: {request.client.host if request.client else 'Unknown'}\n"
                f"Time: {datetime.now().isoformat()}"
            )

            # 根据请求类型返回响应
            if request.url.path.startswith("/api/"):
                return JSONResponse(
                    status_code=status_code,
                    content={
                        "detail": detail,
                        "path": request.url.path,
                        "timestamp": datetime.now().isoformat(),
                    },
                )
            else:
                from app.core.templates import templates

                return templates.TemplateResponse(
                    "error.html",
                    {
                        "request": request,
                        "status_code": status_code,
                        "detail": detail,
                        "timestamp": datetime.now().isoformat(),
                    },
                    status_code=status_code,
                )
