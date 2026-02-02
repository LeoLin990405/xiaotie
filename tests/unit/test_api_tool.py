"""
API 调用工具测试
"""

import pytest
import json
import time
import threading
from unittest.mock import Mock, patch, MagicMock
from http.client import HTTPResponse

from xiaotie.api_tool import (
    APITool,
    APIConfig,
    APIResponse,
    AuthConfig,
    AuthType,
    HTTPMethod,
    RateLimiter,
    HTTPClient,
    APIBuilder,
    create_api,
    APIError,
    RateLimitError,
)


class TestAuthConfig:
    """测试认证配置"""

    def test_no_auth(self):
        """测试无认证"""
        config = AuthConfig(type="none")
        headers = config.get_headers()
        assert headers == {}

    def test_bearer_auth(self):
        """测试 Bearer 认证"""
        config = AuthConfig(type="bearer", token="test_token")
        headers = config.get_headers()
        assert headers["Authorization"] == "Bearer test_token"

    def test_basic_auth(self):
        """测试 Basic 认证"""
        config = AuthConfig(type="basic", username="user", password="pass")
        headers = config.get_headers()
        assert "Authorization" in headers
        assert headers["Authorization"].startswith("Basic ")

    def test_api_key_auth(self):
        """测试 API Key 认证"""
        config = AuthConfig(type="api_key", api_key="my_key")
        headers = config.get_headers()
        assert headers["X-API-Key"] == "my_key"

    def test_api_key_custom_header(self):
        """测试自定义 API Key 头"""
        config = AuthConfig(
            type="api_key",
            api_key="my_key",
            api_key_header="X-Custom-Key",
        )
        headers = config.get_headers()
        assert headers["X-Custom-Key"] == "my_key"

    def test_custom_auth(self):
        """测试自定义认证"""
        config = AuthConfig(
            type="custom",
            custom_headers={"X-Auth": "custom_value"},
        )
        headers = config.get_headers()
        assert headers["X-Auth"] == "custom_value"


class TestAPIConfig:
    """测试 API 配置"""

    def test_default_config(self):
        """测试默认配置"""
        config = APIConfig()
        assert config.base_url == ""
        assert config.timeout == 30.0
        assert config.rate_limit == 10.0
        assert config.retry_count == 3

    def test_custom_config(self):
        """测试自定义配置"""
        config = APIConfig(
            base_url="https://api.example.com",
            timeout=60.0,
            rate_limit=5.0,
            auth={"type": "bearer", "token": "xxx"},
        )
        assert config.base_url == "https://api.example.com"
        assert config.timeout == 60.0
        assert config.auth_config.token == "xxx"


class TestAPIResponse:
    """测试 API 响应"""

    def test_success_response(self):
        """测试成功响应"""
        response = APIResponse(
            success=True,
            status_code=200,
            body={"data": "test"},
        )
        assert response.success is True
        assert response.status_code == 200

    def test_json_property(self):
        """测试 JSON 属性"""
        response = APIResponse(
            success=True,
            status_code=200,
            body={"key": "value"},
        )
        assert response.json == {"key": "value"}

    def test_json_from_string(self):
        """测试从字符串解析 JSON"""
        response = APIResponse(
            success=True,
            status_code=200,
            body='{"key": "value"}',
        )
        assert response.json == {"key": "value"}

    def test_text_property(self):
        """测试文本属性"""
        response = APIResponse(
            success=True,
            status_code=200,
            body="Hello, World!",
        )
        assert response.text == "Hello, World!"

    def test_to_dict(self):
        """测试转换为字典"""
        response = APIResponse(
            success=True,
            status_code=200,
            body={"data": "test"},
        )
        d = response.to_dict()
        assert d["success"] is True
        assert d["status_code"] == 200


class TestRateLimiter:
    """测试速率限制器"""

    def test_create_limiter(self):
        """测试创建限制器"""
        limiter = RateLimiter(rate=10.0)
        assert limiter.rate == 10.0
        assert limiter.interval == 0.1

    def test_acquire_no_wait(self):
        """测试无需等待的获取"""
        limiter = RateLimiter(rate=10.0)
        wait_time = limiter.acquire()
        # 第一次获取不需要等待
        assert wait_time == 0.0

    def test_acquire_with_wait(self):
        """测试需要等待的获取"""
        limiter = RateLimiter(rate=100.0)  # 每秒 100 次，间隔 0.01 秒
        limiter.acquire()
        start = time.time()
        limiter.acquire()
        elapsed = time.time() - start
        # 应该等待约 0.01 秒
        assert elapsed >= 0.005  # 允许一些误差

    def test_reset(self):
        """测试重置"""
        limiter = RateLimiter(rate=10.0)
        limiter.acquire()
        limiter.reset()
        wait_time = limiter.acquire()
        assert wait_time == 0.0


class TestHTTPClient:
    """测试 HTTP 客户端"""

    def test_build_url_with_base(self):
        """测试带基础 URL 的构建"""
        config = APIConfig(base_url="https://api.example.com")
        client = HTTPClient(config)
        url = client._build_url("/users/1")
        assert url == "https://api.example.com/users/1"

    def test_build_url_with_params(self):
        """测试带参数的 URL 构建"""
        config = APIConfig(base_url="https://api.example.com")
        client = HTTPClient(config)
        url = client._build_url("/search", {"q": "test", "page": 1})
        assert "q=test" in url
        assert "page=1" in url

    def test_build_url_without_base(self):
        """测试无基础 URL 的构建"""
        config = APIConfig()
        client = HTTPClient(config)
        url = client._build_url("https://other.com/api")
        assert url == "https://other.com/api"


class TestAPITool:
    """测试 API 工具"""

    def test_create_tool(self):
        """测试创建工具"""
        tool = APITool()
        assert tool.config is not None

    def test_create_tool_with_config(self):
        """测试使用配置创建工具"""
        config = APIConfig(base_url="https://api.example.com")
        tool = APITool(config)
        assert tool.config.base_url == "https://api.example.com"

    def test_on_response_callback(self):
        """测试响应回调"""
        tool = APITool()
        responses = []

        def callback(response):
            responses.append(response)

        tool.on_response(callback)

        # 模拟请求
        with patch.object(tool._client, 'request') as mock_request:
            mock_request.return_value = APIResponse(success=True, status_code=200)
            tool.get("/test")

        assert len(responses) == 1

    @patch('xiaotie.api_tool.HTTPClient.request')
    def test_get_request(self, mock_request):
        """测试 GET 请求"""
        mock_request.return_value = APIResponse(
            success=True,
            status_code=200,
            body={"id": 1},
        )

        tool = APITool(APIConfig(base_url="https://api.example.com"))
        response = tool.get("/users/1")

        assert response.success is True
        mock_request.assert_called_once()

    @patch('xiaotie.api_tool.HTTPClient.request')
    def test_post_request(self, mock_request):
        """测试 POST 请求"""
        mock_request.return_value = APIResponse(
            success=True,
            status_code=201,
            body={"id": 1},
        )

        tool = APITool(APIConfig(base_url="https://api.example.com"))
        response = tool.post("/users", body={"name": "test"})

        assert response.success is True
        mock_request.assert_called_once()

    @patch('xiaotie.api_tool.HTTPClient.request')
    def test_retry_on_error(self, mock_request):
        """测试错误重试"""
        # 前两次失败，第三次成功
        mock_request.side_effect = [
            APIResponse(success=False, status_code=500),
            APIResponse(success=False, status_code=500),
            APIResponse(success=True, status_code=200),
        ]

        config = APIConfig(
            base_url="https://api.example.com",
            retry_count=3,
            retry_delay=0.01,
        )
        tool = APITool(config)
        response = tool.get("/test")

        assert response.success is True
        assert mock_request.call_count == 3

    @patch('xiaotie.api_tool.HTTPClient.request')
    def test_no_retry_on_client_error(self, mock_request):
        """测试客户端错误不重试"""
        mock_request.return_value = APIResponse(success=False, status_code=400)

        config = APIConfig(
            base_url="https://api.example.com",
            retry_count=3,
        )
        tool = APITool(config)
        response = tool.get("/test")

        assert response.success is False
        assert mock_request.call_count == 1


class TestAPIBuilder:
    """测试 API 请求构建器"""

    @patch('xiaotie.api_tool.HTTPClient.request')
    def test_builder_get(self, mock_request):
        """测试构建器 GET"""
        mock_request.return_value = APIResponse(success=True, status_code=200)

        tool = APITool()
        builder = APIBuilder(tool)
        response = (
            builder
            .method("GET")
            .path("/users")
            .param("page", 1)
            .execute()
        )

        assert response.success is True

    @patch('xiaotie.api_tool.HTTPClient.request')
    def test_builder_post_json(self, mock_request):
        """测试构建器 POST JSON"""
        mock_request.return_value = APIResponse(success=True, status_code=201)

        tool = APITool()
        builder = APIBuilder(tool)
        response = (
            builder
            .method("POST")
            .path("/users")
            .json({"name": "test"})
            .header("X-Custom", "value")
            .execute()
        )

        assert response.success is True

    @patch('xiaotie.api_tool.HTTPClient.request')
    def test_builder_chain(self, mock_request):
        """测试构建器链式调用"""
        mock_request.return_value = APIResponse(success=True, status_code=200)

        tool = APITool()
        response = (
            APIBuilder(tool)
            .method("GET")
            .path("/search")
            .params({"q": "test", "limit": 10})
            .headers({"Accept": "application/json"})
            .execute()
        )

        assert response.success is True


class TestCreateAPI:
    """测试创建 API 快捷方式"""

    def test_create_api(self):
        """测试 create_api 函数"""
        api = create_api("https://api.example.com")
        assert api.config.base_url == "https://api.example.com"

    def test_create_api_with_auth(self):
        """测试带认证的 create_api"""
        api = create_api(
            "https://api.example.com",
            auth={"type": "bearer", "token": "xxx"},
        )
        assert api.config.auth_config.token == "xxx"


class TestIntegration:
    """集成测试"""

    @patch('xiaotie.api_tool.HTTPClient.request')
    def test_full_workflow(self, mock_request):
        """测试完整工作流"""
        # 模拟响应
        mock_request.return_value = APIResponse(
            success=True,
            status_code=200,
            body={"users": [{"id": 1, "name": "Alice"}]},
        )

        # 创建 API 工具
        api = create_api(
            "https://api.example.com",
            auth={"type": "bearer", "token": "test_token"},
            rate_limit=100.0,
        )

        # 发送请求
        response = api.get("/users", params={"page": 1})

        assert response.success is True
        assert response.json["users"][0]["name"] == "Alice"

    @patch('xiaotie.api_tool.HTTPClient.request')
    def test_crud_operations(self, mock_request):
        """测试 CRUD 操作"""
        api = create_api("https://api.example.com")

        # GET
        mock_request.return_value = APIResponse(success=True, status_code=200)
        response = api.get("/users/1")
        assert response.success is True

        # POST
        mock_request.return_value = APIResponse(success=True, status_code=201)
        response = api.post("/users", body={"name": "test"})
        assert response.success is True

        # PUT
        mock_request.return_value = APIResponse(success=True, status_code=200)
        response = api.put("/users/1", body={"name": "updated"})
        assert response.success is True

        # PATCH
        mock_request.return_value = APIResponse(success=True, status_code=200)
        response = api.patch("/users/1", body={"name": "patched"})
        assert response.success is True

        # DELETE
        mock_request.return_value = APIResponse(success=True, status_code=204)
        response = api.delete("/users/1")
        assert response.success is True
