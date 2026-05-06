"""
密钥管理 CLI 命令

xiaotie secret set/get/list/delete/migrate
"""

from __future__ import annotations

import getpass

from .base import CommandsBase


class SecretCommands(CommandsBase):
    """密钥管理命令"""

    ALIASES = {
        "sec": "secret",
    }

    def cmd_secret(self, args: str = ""):
        """密钥管理: secret <set|get|list|delete|migrate> [key]"""
        parts = args.strip().split(maxsplit=1)
        subcmd = parts[0] if parts else "list"
        subarg = parts[1].strip() if len(parts) > 1 else ""

        dispatch = {
            "set": self._secret_set,
            "get": self._secret_get,
            "list": self._secret_list,
            "ls": self._secret_list,
            "delete": self._secret_delete,
            "del": self._secret_delete,
            "rm": self._secret_delete,
            "migrate": self._secret_migrate,
        }

        handler = dispatch.get(subcmd)
        if handler is None:
            print(f"未知子命令: {subcmd}")
            print("用法: secret <set|get|list|delete|migrate> [key]")
            return

        handler(subarg)

    def _secret_set(self, key: str):
        """设置密钥"""
        from xiaotie.secrets import get_secret_manager

        if not key:
            print("用法: secret set <key_name>")
            return

        try:
            value = getpass.getpass(f"请输入 [{key}] 的值: ")
        except (EOFError, KeyboardInterrupt):
            print("\n已取消")
            return

        if not value:
            print("值不能为空")
            return

        mgr = get_secret_manager()
        if mgr.set(key, value):
            print(f"✓ 密钥 [{key}] 已安全存储")
        else:
            print("✗ 存储失败，请检查 keyring 是否可用")

    def _secret_get(self, key: str):
        """获取密钥 (掩码显示)"""
        from xiaotie.secrets import _mask_value, get_secret_manager

        if not key:
            print("用法: secret get <key_name>")
            return

        mgr = get_secret_manager()
        value = mgr.get(key)
        if value is None:
            print(f"未找到密钥: {key}")
        else:
            print(f"{key} = {_mask_value(value)}")

    def _secret_list(self, _: str = ""):
        """列出所有密钥"""
        from xiaotie.secrets import get_secret_manager

        mgr = get_secret_manager()
        keys = mgr.list_keys()

        if not keys:
            print("未找到任何已存储的密钥")
            print("提示: 使用 'secret set <key>' 添加密钥")
            return

        print(f"{'KEY':<25} {'SOURCE':<15} {'VALUE'}")
        print("-" * 55)
        for item in keys:
            print(f"{item['key']:<25} {item['source']:<15} {item['masked_value']}")

    def _secret_delete(self, key: str):
        """删除密钥"""
        from xiaotie.secrets import get_secret_manager

        if not key:
            print("用法: secret delete <key_name>")
            return

        mgr = get_secret_manager()
        if mgr.delete(key):
            print(f"✓ 密钥 [{key}] 已删除")
        else:
            print(f"未找到密钥: {key}")

    def _secret_migrate(self, config_path: str = ""):
        """迁移配置文件中的明文密钥到 keyring"""
        from pathlib import Path

        from xiaotie.secrets import get_secret_manager

        if not config_path:
            # 默认配置文件路径
            candidates = [
                Path("config/config.yaml"),
                Path("config.yaml"),
                Path.home() / ".xiaotie" / "config.yaml",
            ]
            for p in candidates:
                if p.exists():
                    config_path = str(p)
                    break

        if not config_path:
            print("未找到配置文件。用法: secret migrate [config_path]")
            return

        print(f"扫描配置文件: {config_path}")
        mgr = get_secret_manager()
        migrated = mgr.migrate_config(config_path)

        if migrated:
            print(f"\n✓ 已迁移 {len(migrated)} 个密钥到 keyring:")
            for key in migrated:
                print(f"  - {key}")
            print("\n配置文件已更新，明文密钥已替换为 ${secret:...} 占位符")
        else:
            print("未发现需要迁移的明文密钥")
