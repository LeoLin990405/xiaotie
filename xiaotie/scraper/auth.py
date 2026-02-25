"""
认证处理器

支持6种认证方式：NoAuth、BearerToken、Cookie、
CustomHeader、MD5Signature、GatewaySignature。
"""

from __future__ import annotations

import hashlib
import hmac
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, Optional


class AuthMethod(Enum):
    """认证方式"""

    NONE = "none"
    BEARER = "bearer"
    COOKIE = "cookie"
    CUSTOM_HEADER = "custom_header"
    MD5_SIGNATURE = "md5_signature"
    GATEWAY_SIGNATURE = "gateway_signature"


@dataclass
class AuthConfig:
    """认证配置"""

    method: AuthMethod = AuthMethod.NONE
    # Bearer Token
    token: Optional[str] = None
    # Cookie
    cookies: Dict[str, str] = field(default_factory=dict)
    # Custom Header
    custom_headers: Dict[str, str] = field(default_factory=dict)
    # MD5 Signature
    md5_secret: Optional[str] = None
    md5_param_name: str = "sign"
    md5_timestamp_param: str = "timestamp"
    # Gateway Signature
    gateway_app_key: Optional[str] = None
    gateway_app_secret: Optional[str] = None
    gateway_sign_header: str = "X-Gateway-Sign"
    gateway_key_header: str = "X-Gateway-Key"
    gateway_timestamp_header: str = "X-Gateway-Timestamp"


class AuthHandler:
    """认证处理器

    根据配置生成认证 headers、cookies 和签名参数。
    支持 MD5 签名和网关签名两种动态签名方式。
    """

    def __init__(self, config: Optional[AuthConfig] = None):
        self._config = config or AuthConfig()
        self._token: Optional[str] = None
        self._token_expires_at: float = 0.0
        self._token_refresh_callback: Optional[Callable] = None

    @property
    def method(self) -> AuthMethod:
        return self._config.method

    def set_token(self, token: str, expires_in: int = 3600):
        """手动设置 token（用于外部刷新逻辑）"""
        self._token = token
        self._token_expires_at = time.time() + expires_in

    def is_token_expired(self) -> bool:
        """检查 token 是否过期"""
        if not self._token:
            return True
        return time.time() >= self._token_expires_at

    def on_token_refresh(self, callback: Callable):
        """注册 token 刷新回调"""
        self._token_refresh_callback = callback

    def _generate_md5_sign(self, params: Dict[str, str]) -> Dict[str, str]:
        """生成 MD5 签名参数"""
        if not self._config.md5_secret:
            return {}
        ts = str(int(time.time()))
        # 按 key 排序拼接参数
        sorted_params = sorted(params.items())
        sign_str = "&".join(f"{k}={v}" for k, v in sorted_params)
        sign_str += f"&{self._config.md5_timestamp_param}={ts}"
        sign_str += f"&secret={self._config.md5_secret}"
        sign = hashlib.md5(sign_str.encode()).hexdigest()
        return {
            self._config.md5_param_name: sign,
            self._config.md5_timestamp_param: ts,
        }

    def _generate_gateway_sign(self) -> Dict[str, str]:
        """生成网关签名 headers"""
        if not (self._config.gateway_app_key and self._config.gateway_app_secret):
            return {}
        ts = str(int(time.time()))
        sign_str = f"{self._config.gateway_app_key}{ts}{self._config.gateway_app_secret}"
        sign = hmac.new(
            self._config.gateway_app_secret.encode(),
            sign_str.encode(),
            hashlib.sha256,
        ).hexdigest()
        return {
            self._config.gateway_key_header: self._config.gateway_app_key,
            self._config.gateway_timestamp_header: ts,
            self._config.gateway_sign_header: sign,
        }

    def get_headers(self) -> Dict[str, str]:
        """生成认证 headers"""
        headers: Dict[str, str] = {}

        if self._config.method == AuthMethod.BEARER:
            token = self._token or self._config.token
            if token:
                headers["Authorization"] = f"Bearer {token}"

        elif self._config.method == AuthMethod.CUSTOM_HEADER:
            headers.update(self._config.custom_headers)

        elif self._config.method == AuthMethod.GATEWAY_SIGNATURE:
            headers.update(self._generate_gateway_sign())

        return headers

    def get_cookies(self) -> Dict[str, str]:
        """获取认证 cookies"""
        if self._config.method == AuthMethod.COOKIE:
            return dict(self._config.cookies)
        return {}

    def get_sign_params(self, params: Optional[Dict[str, str]] = None) -> Dict[str, str]:
        """获取签名参数（用于 MD5 签名模式）"""
        if self._config.method == AuthMethod.MD5_SIGNATURE:
            return self._generate_md5_sign(params or {})
        return {}

    def apply_to_kwargs(self, kwargs: Dict[str, Any]) -> Dict[str, Any]:
        """将认证信息应用到请求参数"""
        headers = kwargs.get("headers", {})
        headers.update(self.get_headers())
        kwargs["headers"] = headers

        cookies = self.get_cookies()
        if cookies:
            existing = kwargs.get("cookies", {})
            existing.update(cookies)
            kwargs["cookies"] = existing

        if self._config.method == AuthMethod.MD5_SIGNATURE:
            params = kwargs.get("params", {})
            params.update(self.get_sign_params(params))
            kwargs["params"] = params

        return kwargs
