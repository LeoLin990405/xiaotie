"""Profile 配置系统

参考 Open Interpreter 的设计：
- YAML 配置文件
- 多 Profile 支持
- 项目级配置
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml


@dataclass
class ProfileConfig:
    """Profile 配置"""

    # 基本信息
    name: str = "default"
    description: str = ""

    # LLM 配置
    provider: str = "openai"
    model: str = "gpt-4"
    api_key: Optional[str] = None
    api_base: Optional[str] = None
    temperature: float = 0.7
    max_tokens: int = 4096

    # Agent 配置
    system_prompt: Optional[str] = None
    system_prompt_path: Optional[str] = None
    max_steps: int = 50
    token_limit: int = 100000

    # 功能开关
    stream: bool = True
    enable_thinking: bool = True
    parallel_tools: bool = True
    auto_lint: bool = True
    auto_test: bool = False

    # 权限配置
    auto_approve_low_risk: bool = True
    interactive_permissions: bool = True

    # 工具配置
    enabled_tools: List[str] = field(
        default_factory=lambda: [
            "read_file",
            "write_file",
            "edit_file",
            "bash",
            "python",
            "calculator",
            "git",
            "web_search",
            "web_fetch",
        ]
    )
    disabled_tools: List[str] = field(default_factory=list)

    # 自定义命令
    lint_cmd: Optional[str] = None
    test_cmd: Optional[str] = None

    # 环境变量
    env: Dict[str, str] = field(default_factory=dict)


class ProfileManager:
    """Profile 管理器"""

    def __init__(self, profiles_dir: Optional[str] = None):
        if profiles_dir:
            self.profiles_dir = Path(profiles_dir)
        else:
            self.profiles_dir = Path.home() / ".xiaotie" / "profiles"

        self.profiles_dir.mkdir(parents=True, exist_ok=True)
        self._profiles: Dict[str, ProfileConfig] = {}
        self._current_profile: Optional[str] = None

    def _get_profile_path(self, name: str) -> Path:
        """获取 profile 文件路径"""
        return self.profiles_dir / f"{name}.yaml"

    def list_profiles(self) -> List[str]:
        """列出所有 profiles"""
        profiles = []
        for path in self.profiles_dir.glob("*.yaml"):
            profiles.append(path.stem)
        return sorted(profiles)

    def load_profile(self, name: str) -> ProfileConfig:
        """加载 profile"""
        # 检查缓存
        if name in self._profiles:
            return self._profiles[name]

        path = self._get_profile_path(name)
        if not path.exists():
            raise FileNotFoundError(f"Profile 不存在: {name}")

        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}

        # 处理环境变量引用
        data = self._expand_env_vars(data)

        # 创建配置
        config = ProfileConfig(name=name, **data)
        self._profiles[name] = config

        return config

    def save_profile(self, config: ProfileConfig):
        """保存 profile"""
        path = self._get_profile_path(config.name)

        # 转换为字典
        data = {
            "description": config.description,
            "provider": config.provider,
            "model": config.model,
            "temperature": config.temperature,
            "max_tokens": config.max_tokens,
            "max_steps": config.max_steps,
            "token_limit": config.token_limit,
            "stream": config.stream,
            "enable_thinking": config.enable_thinking,
            "parallel_tools": config.parallel_tools,
            "auto_lint": config.auto_lint,
            "auto_test": config.auto_test,
            "auto_approve_low_risk": config.auto_approve_low_risk,
            "interactive_permissions": config.interactive_permissions,
            "enabled_tools": config.enabled_tools,
            "disabled_tools": config.disabled_tools,
        }

        # 可选字段
        if config.api_key:
            data["api_key"] = config.api_key
        if config.api_base:
            data["api_base"] = config.api_base
        if config.system_prompt:
            data["system_prompt"] = config.system_prompt
        if config.system_prompt_path:
            data["system_prompt_path"] = config.system_prompt_path
        if config.lint_cmd:
            data["lint_cmd"] = config.lint_cmd
        if config.test_cmd:
            data["test_cmd"] = config.test_cmd
        if config.env:
            data["env"] = config.env

        with open(path, "w", encoding="utf-8") as f:
            yaml.dump(data, f, default_flow_style=False, allow_unicode=True)

        # 更新缓存
        self._profiles[config.name] = config

    def delete_profile(self, name: str):
        """删除 profile"""
        path = self._get_profile_path(name)
        if path.exists():
            path.unlink()
        self._profiles.pop(name, None)

    def create_default_profile(self) -> ProfileConfig:
        """创建默认 profile"""
        config = ProfileConfig(
            name="default",
            description="默认配置",
        )
        self.save_profile(config)
        return config

    def get_or_create_default(self) -> ProfileConfig:
        """获取或创建默认 profile"""
        try:
            return self.load_profile("default")
        except FileNotFoundError:
            return self.create_default_profile()

    def set_current_profile(self, name: str):
        """设置当前 profile"""
        if name not in self.list_profiles():
            raise ValueError(f"Profile 不存在: {name}")
        self._current_profile = name

    def get_current_profile(self) -> Optional[ProfileConfig]:
        """获取当前 profile"""
        if self._current_profile:
            return self.load_profile(self._current_profile)
        return None

    def _expand_env_vars(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """展开环境变量引用"""
        result = {}
        for key, value in data.items():
            if isinstance(value, str) and value.startswith("${") and value.endswith("}"):
                env_var = value[2:-1]
                result[key] = os.environ.get(env_var, "")
            elif isinstance(value, dict):
                result[key] = self._expand_env_vars(value)
            else:
                result[key] = value
        return result

    def merge_with_config(self, profile: ProfileConfig, config: Dict[str, Any]) -> ProfileConfig:
        """合并 profile 和运行时配置"""
        # 创建副本
        merged = ProfileConfig(
            name=profile.name,
            description=profile.description,
            provider=config.get("provider", profile.provider),
            model=config.get("model", profile.model),
            api_key=config.get("api_key", profile.api_key),
            api_base=config.get("api_base", profile.api_base),
            temperature=config.get("temperature", profile.temperature),
            max_tokens=config.get("max_tokens", profile.max_tokens),
            system_prompt=config.get("system_prompt", profile.system_prompt),
            system_prompt_path=config.get("system_prompt_path", profile.system_prompt_path),
            max_steps=config.get("max_steps", profile.max_steps),
            token_limit=config.get("token_limit", profile.token_limit),
            stream=config.get("stream", profile.stream),
            enable_thinking=config.get("enable_thinking", profile.enable_thinking),
            parallel_tools=config.get("parallel_tools", profile.parallel_tools),
            auto_lint=config.get("auto_lint", profile.auto_lint),
            auto_test=config.get("auto_test", profile.auto_test),
            auto_approve_low_risk=config.get(
                "auto_approve_low_risk", profile.auto_approve_low_risk
            ),
            interactive_permissions=config.get(
                "interactive_permissions", profile.interactive_permissions
            ),
            enabled_tools=config.get("enabled_tools", profile.enabled_tools),
            disabled_tools=config.get("disabled_tools", profile.disabled_tools),
            lint_cmd=config.get("lint_cmd", profile.lint_cmd),
            test_cmd=config.get("test_cmd", profile.test_cmd),
            env={**profile.env, **config.get("env", {})},
        )
        return merged


# 预设 Profiles
PRESET_PROFILES = {
    "coding": ProfileConfig(
        name="coding",
        description="编程助手模式",
        auto_lint=True,
        auto_test=True,
        parallel_tools=True,
        system_prompt="你是一个专业的编程助手，帮助用户编写高质量代码。",
    ),
    "research": ProfileConfig(
        name="research",
        description="研究模式 - 只读操作",
        auto_lint=False,
        auto_test=False,
        enabled_tools=["read_file", "web_search", "web_fetch", "code_analysis"],
        system_prompt="你是一个研究助手，帮助用户分析和理解代码。",
    ),
    "safe": ProfileConfig(
        name="safe",
        description="安全模式 - 需要确认所有操作",
        auto_approve_low_risk=False,
        interactive_permissions=True,
        system_prompt="你是一个谨慎的助手，所有操作都需要用户确认。",
    ),
}


def create_preset_profiles(manager: ProfileManager):
    """创建预设 profiles"""
    for name, config in PRESET_PROFILES.items():
        if name not in manager.list_profiles():
            manager.save_profile(config)
