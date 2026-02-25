"""认证管理器单元测试

测试覆盖：
- AuthMethod 枚举（6种方式）
- AuthConfig 配置
- AuthHandler 认证处理器
  - NoAuth
  - Bearer Token
  - Cookie
  - CustomHeader
  - MD5 Signature
  - Gateway Signature
  - get_headers()
  - get_cookies()
  - get_sign_params()
  - apply_to_kwargs()
  - set_token() / is_token_expired()
  - on_token_refresh()
"""

from __future__ import annotations

import time
from unittest.mock import MagicMock

import pytest

from xiaotie.scraper.auth import AuthConfig, AuthHandler, AuthMethod


# ============================================================
# AuthMethod 测试
# ============================================================


class TestAuthMethod:

    def test_values(self):
        assert AuthMethod.NONE.value == "none"
        assert AuthMethod.BEARER.value == "bearer"
        assert AuthMethod.COOKIE.value == "cookie"
        assert AuthMethod.CUSTOM_HEADER.value == "custom_header"
        assert AuthMethod.MD5_SIGNATURE.value == "md5_signature"
        assert AuthMethod.GATEWAY_SIGNATURE.value == "gateway_signature"

    def test_count(self):
        assert len(AuthMethod) == 6


# ============================================================
# AuthConfig 测试
# ============================================================


class TestAuthConfig:

    def test_defaults(self):
        c = AuthConfig()
        assert c.method == AuthMethod.NONE
        assert c.token is None
        assert c.cookies == {}
        assert c.custom_headers == {}
        assert c.md5_secret is None
        assert c.md5_param_name == "sign"
        assert c.gateway_app_key is None
        assert c.gateway_app_secret is None

    def test_bearer_config(self):
        c = AuthConfig(method=AuthMethod.BEARER, token="my-token-123")
        assert c.token == "my-token-123"

    def test_cookie_config(self):
        c = AuthConfig(
            method=AuthMethod.COOKIE,
            cookies={"session": "abc123"},
        )
        assert c.cookies["session"] == "abc123"

    def test_custom_header_config(self):
        c = AuthConfig(
            method=AuthMethod.CUSTOM_HEADER,
            custom_headers={"X-Api-Key": "key123"},
        )
        assert c.custom_headers["X-Api-Key"] == "key123"

    def test_md5_config(self):
        c = AuthConfig(
            method=AuthMethod.MD5_SIGNATURE,
            md5_secret="my-secret",
            md5_param_name="signature",
        )
        assert c.md5_secret == "my-secret"
        assert c.md5_param_name == "signature"

    def test_gateway_config(self):
        c = AuthConfig(
            method=AuthMethod.GATEWAY_SIGNATURE,
            gateway_app_key="app-key",
            gateway_app_secret="app-secret",
        )
        assert c.gateway_app_key == "app-key"
        assert c.gateway_app_secret == "app-secret"


# ============================================================
# AuthHandler - NoAuth 测试
# ============================================================


class TestAuthHandlerNone:

    def test_no_auth_headers(self):
        handler = AuthHandler()
        headers = handler.get_headers()
        assert "Authorization" not in headers
        assert headers == {}

    def test_no_auth_cookies(self):
        handler = AuthHandler()
        cookies = handler.get_cookies()
        assert cookies == {}

    def test_method(self):
        handler = AuthHandler()
        assert handler.method == AuthMethod.NONE


# ============================================================
# AuthHandler - Bearer Token 测试
# ============================================================


class TestAuthHandlerBearer:

    def test_bearer_token_headers(self):
        config = AuthConfig(method=AuthMethod.BEARER, token="my-token")
        handler = AuthHandler(config)
        headers = handler.get_headers()
        assert headers["Authorization"] == "Bearer my-token"

    def test_bearer_no_token(self):
        config = AuthConfig(method=AuthMethod.BEARER)
        handler = AuthHandler(config)
        headers = handler.get_headers()
        assert "Authorization" not in headers

    def test_bearer_with_set_token(self):
        config = AuthConfig(method=AuthMethod.BEARER, token="old-token")
        handler = AuthHandler(config)
        handler.set_token("new-token", expires_in=3600)
        headers = handler.get_headers()
        assert headers["Authorization"] == "Bearer new-token"


# ============================================================
# AuthHandler - Cookie 测试
# ============================================================


class TestAuthHandlerCookie:

    def test_cookie_auth(self):
        config = AuthConfig(
            method=AuthMethod.COOKIE,
            cookies={"session": "abc", "token": "xyz"},
        )
        handler = AuthHandler(config)
        cookies = handler.get_cookies()
        assert cookies["session"] == "abc"
        assert cookies["token"] == "xyz"

    def test_cookie_empty(self):
        config = AuthConfig(method=AuthMethod.COOKIE)
        handler = AuthHandler(config)
        cookies = handler.get_cookies()
        assert cookies == {}

    def test_non_cookie_method_returns_empty(self):
        config = AuthConfig(method=AuthMethod.BEARER, token="tok")
        handler = AuthHandler(config)
        assert handler.get_cookies() == {}


# ============================================================
# AuthHandler - CustomHeader 测试
# ============================================================


class TestAuthHandlerCustomHeader:

    def test_custom_headers(self):
        config = AuthConfig(
            method=AuthMethod.CUSTOM_HEADER,
            custom_headers={"X-Api-Key": "key123", "X-App-Id": "app456"},
        )
        handler = AuthHandler(config)
        headers = handler.get_headers()
        assert headers["X-Api-Key"] == "key123"
        assert headers["X-App-Id"] == "app456"

    def test_custom_headers_empty(self):
        config = AuthConfig(method=AuthMethod.CUSTOM_HEADER)
        handler = AuthHandler(config)
        headers = handler.get_headers()
        assert headers == {}


# ============================================================
# AuthHandler - MD5 Signature 测试
# ============================================================


class TestAuthHandlerMD5:

    def test_md5_sign_params(self):
        config = AuthConfig(
            method=AuthMethod.MD5_SIGNATURE,
            md5_secret="test-secret",
        )
        handler = AuthHandler(config)
        params = handler.get_sign_params({"key": "value"})
        assert "sign" in params
        assert "timestamp" in params

    def test_md5_sign_no_secret(self):
        config = AuthConfig(method=AuthMethod.MD5_SIGNATURE)
        handler = AuthHandler(config)
        params = handler.get_sign_params({})
        assert params == {}

    def test_md5_sign_custom_param_name(self):
        config = AuthConfig(
            method=AuthMethod.MD5_SIGNATURE,
            md5_secret="secret",
            md5_param_name="signature",
            md5_timestamp_param="ts",
        )
        handler = AuthHandler(config)
        params = handler.get_sign_params({"a": "1"})
        assert "signature" in params
        assert "ts" in params

    def test_md5_sign_deterministic(self):
        """相同参数应产生相同签名（同一秒内）"""
        config = AuthConfig(
            method=AuthMethod.MD5_SIGNATURE,
            md5_secret="secret",
        )
        handler = AuthHandler(config)
        p1 = handler.get_sign_params({"key": "value"})
        p2 = handler.get_sign_params({"key": "value"})
        # 同一秒内签名应相同
        assert p1["sign"] == p2["sign"]

    def test_md5_headers_empty(self):
        """MD5 签名不产生 headers"""
        config = AuthConfig(
            method=AuthMethod.MD5_SIGNATURE,
            md5_secret="secret",
        )
        handler = AuthHandler(config)
        headers = handler.get_headers()
        assert headers == {}

    def test_non_md5_returns_empty_params(self):
        config = AuthConfig(method=AuthMethod.BEARER, token="tok")
        handler = AuthHandler(config)
        params = handler.get_sign_params({})
        assert params == {}


# ============================================================
# AuthHandler - Gateway Signature 测试
# ============================================================


class TestAuthHandlerGateway:

    def test_gateway_sign_headers(self):
        config = AuthConfig(
            method=AuthMethod.GATEWAY_SIGNATURE,
            gateway_app_key="my-key",
            gateway_app_secret="my-secret",
        )
        handler = AuthHandler(config)
        headers = handler.get_headers()
        assert "X-Gateway-Key" in headers
        assert "X-Gateway-Timestamp" in headers
        assert "X-Gateway-Sign" in headers
        assert headers["X-Gateway-Key"] == "my-key"

    def test_gateway_sign_no_credentials(self):
        config = AuthConfig(method=AuthMethod.GATEWAY_SIGNATURE)
        handler = AuthHandler(config)
        headers = handler.get_headers()
        assert headers == {}

    def test_gateway_custom_header_names(self):
        config = AuthConfig(
            method=AuthMethod.GATEWAY_SIGNATURE,
            gateway_app_key="key",
            gateway_app_secret="secret",
            gateway_sign_header="X-Sign",
            gateway_key_header="X-Key",
            gateway_timestamp_header="X-TS",
        )
        handler = AuthHandler(config)
        headers = handler.get_headers()
        assert "X-Sign" in headers
        assert "X-Key" in headers
        assert "X-TS" in headers


# ============================================================
# AuthHandler - Token 管理测试
# ============================================================


class TestAuthHandlerToken:

    def test_set_token(self):
        handler = AuthHandler()
        handler.set_token("new-token", expires_in=3600)
        assert handler._token == "new-token"
        assert handler._token_expires_at > time.time()

    def test_is_token_expired_no_token(self):
        handler = AuthHandler()
        assert handler.is_token_expired() is True

    def test_is_token_expired_true(self):
        handler = AuthHandler()
        handler._token = "tok"
        handler._token_expires_at = time.time() - 100
        assert handler.is_token_expired() is True

    def test_is_token_expired_false(self):
        handler = AuthHandler()
        handler._token = "tok"
        handler._token_expires_at = time.time() + 3600
        assert handler.is_token_expired() is False

    def test_on_token_refresh_callback(self):
        handler = AuthHandler()
        callback = MagicMock()
        handler.on_token_refresh(callback)
        assert handler._token_refresh_callback is callback


# ============================================================
# AuthHandler - apply_to_kwargs 测试
# ============================================================


class TestAuthHandlerApply:

    def test_apply_bearer_headers(self):
        config = AuthConfig(method=AuthMethod.BEARER, token="tok")
        handler = AuthHandler(config)
        kwargs = {}
        result = handler.apply_to_kwargs(kwargs)
        assert result["headers"]["Authorization"] == "Bearer tok"

    def test_apply_merges_headers(self):
        config = AuthConfig(method=AuthMethod.BEARER, token="tok")
        handler = AuthHandler(config)
        kwargs = {"headers": {"Accept": "application/json"}}
        result = handler.apply_to_kwargs(kwargs)
        assert result["headers"]["Accept"] == "application/json"
        assert result["headers"]["Authorization"] == "Bearer tok"

    def test_apply_cookies(self):
        config = AuthConfig(
            method=AuthMethod.COOKIE,
            cookies={"session": "abc"},
        )
        handler = AuthHandler(config)
        kwargs = {}
        result = handler.apply_to_kwargs(kwargs)
        assert result["cookies"]["session"] == "abc"

    def test_apply_md5_adds_params(self):
        config = AuthConfig(
            method=AuthMethod.MD5_SIGNATURE,
            md5_secret="secret",
        )
        handler = AuthHandler(config)
        kwargs = {"params": {"key": "value"}}
        result = handler.apply_to_kwargs(kwargs)
        assert "sign" in result["params"]
        assert "timestamp" in result["params"]
        assert result["params"]["key"] == "value"

    def test_apply_custom_headers(self):
        config = AuthConfig(
            method=AuthMethod.CUSTOM_HEADER,
            custom_headers={"X-Custom": "value"},
        )
        handler = AuthHandler(config)
        kwargs = {}
        result = handler.apply_to_kwargs(kwargs)
        assert result["headers"]["X-Custom"] == "value"
