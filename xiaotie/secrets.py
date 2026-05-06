"""
密钥管理器 - 分层密钥解析与安全存储

解析优先级: system keyring → env vars → encrypted config
支持配置文件中的 ${secret:key_name} 和 ${env:VAR_NAME} 占位符替换
"""

from __future__ import annotations

import logging
import os
import re
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# 占位符模式
_SECRET_PATTERN = re.compile(r"\$\{secret:([^}]+)\}")
_ENV_PATTERN = re.compile(r"\$\{env:([^}]+)\}")

# API key 模式 (用于自动迁移检测)
_API_KEY_FIELDS = {"api_key", "apikey", "api_secret", "token", "secret_key"}
_API_KEY_VALUE_PATTERN = re.compile(r"^[a-zA-Z0-9_\-]{20,}$")


def _keyring_available() -> bool:
    """检查 keyring 是否可用"""
    try:
        import keyring

        # 测试是否能访问后端
        keyring.get_keyring()
        return True
    except Exception:
        return False


class SecretManager:
    """分层密钥管理器

    解析顺序:
    1. System keyring (macOS Keychain / Linux Secret Service)
    2. 环境变量
    3. 配置文件明文 (仅作 fallback，不推荐)
    """

    SERVICE_NAME = "xiaotie"

    def __init__(self):
        self._has_keyring = _keyring_available()
        if not self._has_keyring:
            logger.debug("keyring 不可用，将使用环境变量 fallback")

    def get(self, key: str) -> Optional[str]:
        """获取密钥，按优先级从高到低解析

        Args:
            key: 密钥名称

        Returns:
            密钥值，未找到返回 None
        """
        # 1. keyring
        if self._has_keyring:
            try:
                import keyring

                value = keyring.get_password(self.SERVICE_NAME, key)
                if value is not None:
                    return value
            except Exception as e:
                logger.debug(f"keyring 读取失败 [{key}]: {e}")

        # 2. 环境变量 (尝试多种命名: XIAOTIE_KEY, KEY)
        for env_key in [f"XIAOTIE_{key.upper()}", key.upper()]:
            value = os.environ.get(env_key)
            if value is not None:
                return value

        return None

    def set(self, key: str, value: str, backend: str = "keyring") -> bool:
        """存储密钥

        Args:
            key: 密钥名称
            value: 密钥值
            backend: 存储后端 ("keyring" 或 "env")

        Returns:
            是否成功
        """
        if backend == "keyring":
            if not self._has_keyring:
                logger.error("keyring 不可用，无法存储。请安装 keyring 或使用环境变量")
                return False
            try:
                import keyring

                keyring.set_password(self.SERVICE_NAME, key, value)
                logger.info(f"密钥 [{key}] 已存储到 keyring")
                return True
            except Exception as e:
                logger.error(f"keyring 存储失败: {e}")
                return False
        elif backend == "env":
            os.environ[f"XIAOTIE_{key.upper()}"] = value
            logger.info(f"密钥 [{key}] 已设置为环境变量 XIAOTIE_{key.upper()}")
            return True
        else:
            logger.error(f"未知后端: {backend}")
            return False

    def delete(self, key: str) -> bool:
        """删除密钥

        Args:
            key: 密钥名称

        Returns:
            是否成功
        """
        deleted = False

        if self._has_keyring:
            try:
                import keyring

                keyring.delete_password(self.SERVICE_NAME, key)
                deleted = True
                logger.info(f"密钥 [{key}] 已从 keyring 删除")
            except Exception:
                pass

        # 清理环境变量
        for env_key in [f"XIAOTIE_{key.upper()}", key.upper()]:
            if env_key in os.environ:
                del os.environ[env_key]
                deleted = True

        return deleted

    def list_keys(self) -> list[dict]:
        """列出所有已知密钥及其来源

        Returns:
            [{"key": str, "source": str, "masked_value": str}, ...]
        """
        keys = []
        seen = set()

        # keyring 无法枚举，但我们可以检查已知的常见 key
        known_keys = [
            "api_key",
            "zhipu_api_key",
            "openai_api_key",
            "github_token",
            "telegram_token",
            "proxy_password",
        ]

        for key in known_keys:
            if key in seen:
                continue

            # 检查 keyring
            if self._has_keyring:
                try:
                    import keyring

                    value = keyring.get_password(self.SERVICE_NAME, key)
                    if value:
                        keys.append(
                            {
                                "key": key,
                                "source": "keyring",
                                "masked_value": _mask_value(value),
                            }
                        )
                        seen.add(key)
                        continue
                except Exception:
                    pass

            # 检查环境变量
            for env_key in [f"XIAOTIE_{key.upper()}", key.upper()]:
                value = os.environ.get(env_key)
                if value:
                    keys.append(
                        {
                            "key": key,
                            "source": f"env:{env_key}",
                            "masked_value": _mask_value(value),
                        }
                    )
                    seen.add(key)
                    break

        return keys

    def resolve_config(self, config: dict) -> dict:
        """递归解析配置中的 ${secret:...} 和 ${env:...} 占位符

        Args:
            config: 原始配置字典

        Returns:
            解析后的配置字典 (新副本)
        """
        return _resolve_dict(config, self)

    def migrate_config(self, config_path: str) -> list[str]:
        """扫描配置文件中的明文密钥，迁移到 keyring

        Args:
            config_path: config.yaml 路径

        Returns:
            已迁移的 key 列表
        """
        if not self._has_keyring:
            logger.error("keyring 不可用，无法迁移")
            return []

        try:
            import yaml
        except ImportError:
            logger.error("需要 PyYAML 来解析配置文件")
            return []

        path = Path(config_path)
        if not path.exists():
            logger.error(f"配置文件不存在: {config_path}")
            return []

        with open(path) as f:
            config = yaml.safe_load(f) or {}

        migrated = []
        modified = False

        for key, value in list(config.items()):
            if not isinstance(value, str):
                continue
            # 跳过已经是占位符的
            if value.startswith("${"):
                continue
            # 检查是否是 API key 字段
            key_lower = key.lower()
            is_secret_field = any(k in key_lower for k in _API_KEY_FIELDS)
            is_secret_value = _API_KEY_VALUE_PATTERN.match(value) and value != "YOUR_API_KEY_HERE"

            if is_secret_field and is_secret_value:
                secret_name = key_lower.replace("-", "_")
                if self.set(secret_name, value):
                    config[key] = f"${{secret:{secret_name}}}"
                    migrated.append(key)
                    modified = True
                    logger.info(f"已迁移 [{key}] → keyring (secret:{secret_name})")

        if modified:
            with open(path, "w") as f:
                yaml.dump(config, f, default_flow_style=False, allow_unicode=True)
            logger.info(f"配置文件已更新: {config_path}")

        return migrated


def _mask_value(value: str) -> str:
    """掩码显示密钥值"""
    if len(value) <= 8:
        return "****"
    return value[:4] + "****" + value[-4:]


def _resolve_value(value: str, manager: SecretManager) -> str:
    """解析单个字符串中的占位符"""

    def replace_secret(m):
        key = m.group(1)
        resolved = manager.get(key)
        if resolved is None:
            logger.warning(f"未找到密钥: {key}")
            return m.group(0)  # 保持原样
        return resolved

    def replace_env(m):
        key = m.group(1)
        resolved = os.environ.get(key)
        if resolved is None:
            logger.warning(f"未找到环境变量: {key}")
            return m.group(0)
        return resolved

    value = _SECRET_PATTERN.sub(replace_secret, value)
    value = _ENV_PATTERN.sub(replace_env, value)
    return value


def _resolve_dict(d: dict, manager: SecretManager) -> dict:
    """递归解析字典"""
    result = {}
    for k, v in d.items():
        if isinstance(v, str):
            result[k] = _resolve_value(v, manager)
        elif isinstance(v, dict):
            result[k] = _resolve_dict(v, manager)
        elif isinstance(v, list):
            result[k] = [
                _resolve_value(item, manager)
                if isinstance(item, str)
                else _resolve_dict(item, manager)
                if isinstance(item, dict)
                else item
                for item in v
            ]
        else:
            result[k] = v
    return result


# 全局单例
_secret_manager: Optional[SecretManager] = None


def get_secret_manager() -> SecretManager:
    """获取全局 SecretManager 实例"""
    global _secret_manager
    has_keyring = _keyring_available()
    if _secret_manager is None or _secret_manager._has_keyring != has_keyring:
        _secret_manager = SecretManager()
    return _secret_manager
