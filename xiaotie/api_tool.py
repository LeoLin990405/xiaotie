"""
API 调用工具模块

提供通用的 HTTP API 调用能力，支持：
- RESTful API 调用
- 多种认证方式
- 速率限制
- 响应解析

使用示例:
    from xiaotie.api_tool import APITool, APIConfig

    # 基础用法
    api = APITool(APIConfig(
        base_url="https://api.example.com",
    ))
    result = api.get("/users/1")

    # 带认证
    api = APITool(APIConfig(
        base_url="https://api.example.com",
        auth={"type": "bearer", "token": "xxx"},
    ))
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Dict, Any, List, Callable, Union
import json
import time
import threading
from urllib.parse import urljoin, urlencode
from http.client import HTTPConnection, HTTPSConnection
from urllib.parse import urlparse
import ssl


class AuthType(Enum):
    """认证类型"""
    NONE = "none"
    BEARER = "bearer"
    BASIC = "basic"
    API_KEY = "api_key"
    CUSTOM = "custom"


class HTTPMethod(Enum):
    """HTTP 方法"""
    GET = "GET"
    POST = "POST"
    PUT = "PUT"
    PATCH = "PATCH"
    DELETE = "DELETE"
    HEAD = "HEAD"
    OPTIONS = "OPTIONS"


@dataclass
class AuthConfig:
    """认证配置"""
    type: str = "none"
    token: Optional[str] = None  # Bearer token
    username: Optional[str] = None  # Basic auth
    password: Optional[str] = None  # Basic auth
    api_key: Optional[str] = None  # API key
    api_key_header: str = "X-API-Key"  # API key header name
    custom_headers: Dict[str, str] = field(default_factory=dict)

    def get_headers(self) -> Dict[str, str]:
        """获取认证头"""
        auth_type = AuthType(self.type)

        if auth_type == AuthType.BEARER:
            return {"Authorization": f"Bearer {self.token}"}
        elif auth_type == AuthType.BASIC:
            import base64
            credentials = f"{self.username}:{self.password}"
            encoded = base64.b64encode(credentials.encode()).decode()
            return {"Authorization": f"Basic {encoded}"}
        elif auth_type == AuthType.API_KEY:
            return {self.api_key_header: self.api_key}
        elif auth_type == AuthType.CUSTOM:
            return self.custom_headers
        return {}


@dataclass
class APIConfig:
    """API 配置"""
    base_url: str = ""
    auth: Optional[Dict[str, Any]] = None
    timeout: float = 30.0
    rate_limit: float = 10.0  # 每秒请求数
    retry_count: int = 3
    retry_delay: float = 1.0
    default_headers: Dict[str, str] = field(default_factory=dict)
    verify_ssl: bool = True

    def __post_init__(self):
        if self.auth:
            self._auth_config = AuthConfig(**self.auth)
        else:
            self._auth_config = AuthConfig()

    @property
    def auth_config(self) -> AuthConfig:
        return self._auth_config


@dataclass
class APIResponse:
    """API 响应"""
    success: bool
    status_code: int = 0
    headers: Dict[str, str] = field(default_factory=dict)
    body: Any = None
    raw_body: bytes = b""
    elapsed_time: float = 0.0
    error_message: Optional[str] = None

    @property
    def json(self) -> Optional[Dict[str, Any]]:
        """解析 JSON 响应"""
        if isinstance(self.body, dict):
            return self.body
        if isinstance(self.body, str):
            try:
                return json.loads(self.body)
            except json.JSONDecodeError:
                return None
        return None

    @property
    def text(self) -> str:
        """获取文本响应"""
        if isinstance(self.body, str):
            return self.body
        if isinstance(self.body, bytes):
            return self.body.decode('utf-8', errors='replace')
        return str(self.body) if self.body else ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "status_code": self.status_code,
            "headers": self.headers,
            "body": self.body,
            "elapsed_time": self.elapsed_time,
            "error_message": self.error_message,
        }


class APIError(Exception):
    """API 错误基类"""
    pass


class RateLimitError(APIError):
    """速率限制错误"""
    pass


class TimeoutError(APIError):
    """超时错误"""
    pass


class AuthenticationError(APIError):
    """认证错误"""
    pass


class RateLimiter:
    """速率限制器"""

    def __init__(self, rate: float):
        """
        Args:
            rate: 每秒允许的请求数
        """
        self.rate = rate
        self.interval = 1.0 / rate if rate > 0 else 0
        self._last_request = 0.0
        self._lock = threading.Lock()

    def acquire(self) -> float:
        """获取请求许可，返回等待时间"""
        with self._lock:
            now = time.time()
            elapsed = now - self._last_request

            if elapsed < self.interval:
                wait_time = self.interval - elapsed
                time.sleep(wait_time)
                self._last_request = time.time()
                return wait_time
            else:
                self._last_request = now
                return 0.0

    def reset(self):
        """重置限制器"""
        with self._lock:
            self._last_request = 0.0


class HTTPClient:
    """HTTP 客户端"""

    def __init__(self, config: APIConfig):
        self.config = config
        self._parsed_url = urlparse(config.base_url) if config.base_url else None

    def request(
        self,
        method: str,
        path: str,
        headers: Optional[Dict[str, str]] = None,
        body: Optional[Union[str, bytes, Dict]] = None,
        params: Optional[Dict[str, Any]] = None,
    ) -> APIResponse:
        """发送 HTTP 请求"""
        start_time = time.time()

        try:
            # 构建 URL
            url = self._build_url(path, params)
            parsed = urlparse(url)

            # 创建连接
            if parsed.scheme == "https":
                context = ssl.create_default_context()
                if not self.config.verify_ssl:
                    context.check_hostname = False
                    context.verify_mode = ssl.CERT_NONE
                conn = HTTPSConnection(
                    parsed.netloc,
                    timeout=self.config.timeout,
                    context=context,
                )
            else:
                conn = HTTPConnection(
                    parsed.netloc,
                    timeout=self.config.timeout,
                )

            # 准备请求头
            request_headers = {
                "User-Agent": "xiaotie-api-tool/1.0",
                "Accept": "application/json",
            }
            request_headers.update(self.config.default_headers)
            request_headers.update(self.config.auth_config.get_headers())
            if headers:
                request_headers.update(headers)

            # 准备请求体
            request_body = None
            if body is not None:
                if isinstance(body, dict):
                    request_body = json.dumps(body).encode('utf-8')
                    request_headers["Content-Type"] = "application/json"
                elif isinstance(body, str):
                    request_body = body.encode('utf-8')
                else:
                    request_body = body

            # 发送请求
            request_path = parsed.path
            if parsed.query:
                request_path += "?" + parsed.query

            conn.request(method, request_path, body=request_body, headers=request_headers)

            # 获取响应
            response = conn.getresponse()
            raw_body = response.read()

            # 解析响应头
            response_headers = dict(response.getheaders())

            # 解析响应体
            content_type = response_headers.get("Content-Type", "")
            if "application/json" in content_type:
                try:
                    parsed_body = json.loads(raw_body.decode('utf-8'))
                except json.JSONDecodeError:
                    parsed_body = raw_body.decode('utf-8', errors='replace')
            else:
                parsed_body = raw_body.decode('utf-8', errors='replace')

            conn.close()

            return APIResponse(
                success=200 <= response.status < 300,
                status_code=response.status,
                headers=response_headers,
                body=parsed_body,
                raw_body=raw_body,
                elapsed_time=time.time() - start_time,
            )

        except TimeoutError as e:
            return APIResponse(
                success=False,
                elapsed_time=time.time() - start_time,
                error_message=f"Request timed out: {e}",
            )
        except Exception as e:
            return APIResponse(
                success=False,
                elapsed_time=time.time() - start_time,
                error_message=str(e),
            )

    def _build_url(self, path: str, params: Optional[Dict[str, Any]] = None) -> str:
        """构建完整 URL"""
        if self.config.base_url:
            url = urljoin(self.config.base_url, path)
        else:
            url = path

        if params:
            query_string = urlencode(params)
            separator = "&" if "?" in url else "?"
            url += separator + query_string

        return url


class APITool:
    """API 调用工具"""

    def __init__(self, config: Optional[APIConfig] = None):
        self.config = config or APIConfig()
        self._client = HTTPClient(self.config)
        self._rate_limiter = RateLimiter(self.config.rate_limit)
        self._callbacks: List[Callable[[APIResponse], None]] = []

    def on_response(self, callback: Callable[[APIResponse], None]) -> "APITool":
        """注册响应回调"""
        self._callbacks.append(callback)
        return self

    def _notify_callbacks(self, response: APIResponse):
        """通知回调"""
        for callback in self._callbacks:
            try:
                callback(response)
            except Exception:
                pass

    def request(
        self,
        method: str,
        path: str,
        headers: Optional[Dict[str, str]] = None,
        body: Optional[Union[str, bytes, Dict]] = None,
        params: Optional[Dict[str, Any]] = None,
        retry: bool = True,
    ) -> APIResponse:
        """发送请求"""
        # 速率限制
        self._rate_limiter.acquire()

        # 重试逻辑
        last_response = None
        attempts = self.config.retry_count if retry else 1

        for attempt in range(attempts):
            response = self._client.request(method, path, headers, body, params)
            last_response = response

            if response.success:
                break

            # 检查是否应该重试
            if response.status_code in [429, 500, 502, 503, 504]:
                if attempt < attempts - 1:
                    time.sleep(self.config.retry_delay * (attempt + 1))
                    continue

            break

        self._notify_callbacks(last_response)
        return last_response

    def get(
        self,
        path: str,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> APIResponse:
        """GET 请求"""
        return self.request("GET", path, headers=headers, params=params)

    def post(
        self,
        path: str,
        body: Optional[Union[str, bytes, Dict]] = None,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> APIResponse:
        """POST 请求"""
        return self.request("POST", path, headers=headers, body=body, params=params)

    def put(
        self,
        path: str,
        body: Optional[Union[str, bytes, Dict]] = None,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> APIResponse:
        """PUT 请求"""
        return self.request("PUT", path, headers=headers, body=body, params=params)

    def patch(
        self,
        path: str,
        body: Optional[Union[str, bytes, Dict]] = None,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> APIResponse:
        """PATCH 请求"""
        return self.request("PATCH", path, headers=headers, body=body, params=params)

    def delete(
        self,
        path: str,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> APIResponse:
        """DELETE 请求"""
        return self.request("DELETE", path, headers=headers, params=params)


class APIBuilder:
    """API 请求构建器"""

    def __init__(self, tool: APITool):
        self._tool = tool
        self._method = "GET"
        self._path = ""
        self._headers: Dict[str, str] = {}
        self._params: Dict[str, Any] = {}
        self._body: Optional[Union[str, bytes, Dict]] = None

    def method(self, method: str) -> "APIBuilder":
        """设置方法"""
        self._method = method.upper()
        return self

    def path(self, path: str) -> "APIBuilder":
        """设置路径"""
        self._path = path
        return self

    def header(self, key: str, value: str) -> "APIBuilder":
        """添加请求头"""
        self._headers[key] = value
        return self

    def headers(self, headers: Dict[str, str]) -> "APIBuilder":
        """设置请求头"""
        self._headers.update(headers)
        return self

    def param(self, key: str, value: Any) -> "APIBuilder":
        """添加查询参数"""
        self._params[key] = value
        return self

    def params(self, params: Dict[str, Any]) -> "APIBuilder":
        """设置查询参数"""
        self._params.update(params)
        return self

    def body(self, body: Union[str, bytes, Dict]) -> "APIBuilder":
        """设置请求体"""
        self._body = body
        return self

    def json(self, data: Dict[str, Any]) -> "APIBuilder":
        """设置 JSON 请求体"""
        self._body = data
        return self

    def execute(self) -> APIResponse:
        """执行请求"""
        return self._tool.request(
            method=self._method,
            path=self._path,
            headers=self._headers if self._headers else None,
            body=self._body,
            params=self._params if self._params else None,
        )


def create_api(base_url: str, **kwargs) -> APITool:
    """创建 API 工具的快捷方式"""
    config = APIConfig(base_url=base_url, **kwargs)
    return APITool(config)
