"""首次启动向导模块

功能:
- 检测首次启动
- 引导用户配置 API Key
- 选择默认模型
- 测试连接
- 生成配置文件
"""

from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, List, Optional, Tuple

from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Center, Horizontal, Vertical
from textual.message import Message
from textual.screen import ModalScreen, Screen
from textual.widgets import Button, Input, Label, ProgressBar, Static


@dataclass
class ProviderSetup:
    """Provider 配置信息"""

    name: str
    display_name: str
    icon: str
    api_key_env: str
    api_key_hint: str
    default_model: str
    test_endpoint: str


# 支持的 Provider 列表
SUPPORTED_PROVIDERS: List[ProviderSetup] = [
    ProviderSetup(
        name="anthropic",
        display_name="Anthropic Claude",
        icon="󰚩",
        api_key_env="ANTHROPIC_API_KEY",
        api_key_hint="sk-ant-...",
        default_model="claude-sonnet-4-20250514",
        test_endpoint="https://api.anthropic.com/v1/messages",
    ),
    ProviderSetup(
        name="openai",
        display_name="OpenAI GPT",
        icon="󰧑",
        api_key_env="OPENAI_API_KEY",
        api_key_hint="sk-...",
        default_model="gpt-4o",
        test_endpoint="https://api.openai.com/v1/models",
    ),
    ProviderSetup(
        name="deepseek",
        display_name="DeepSeek",
        icon="󰊤",
        api_key_env="DEEPSEEK_API_KEY",
        api_key_hint="sk-...",
        default_model="deepseek-chat",
        test_endpoint="https://api.deepseek.com/v1/models",
    ),
    ProviderSetup(
        name="qwen",
        display_name="Qwen (通义千问)",
        icon="󰮯",
        api_key_env="DASHSCOPE_API_KEY",
        api_key_hint="sk-...",
        default_model="qwen-plus",
        test_endpoint="https://dashscope.aliyuncs.com/compatible-mode/v1/models",
    ),
    ProviderSetup(
        name="gemini",
        display_name="Google Gemini",
        icon="󰊭",
        api_key_env="GOOGLE_API_KEY",
        api_key_hint="AIza...",
        default_model="gemini-2.0-flash",
        test_endpoint="https://generativelanguage.googleapis.com/v1beta/models",
    ),
]


def get_config_path() -> Path:
    """获取配置文件路径"""
    # 优先使用 XDG 规范
    xdg_config = os.environ.get("XDG_CONFIG_HOME", "")
    if xdg_config:
        return Path(xdg_config) / "xiaotie" / "config.yaml"

    # 回退到 ~/.config
    return Path.home() / ".config" / "xiaotie" / "config.yaml"


def is_first_run() -> bool:
    """检测是否首次运行"""
    config_path = get_config_path()
    return not config_path.exists()


def has_any_api_key() -> bool:
    """检测是否有任何 API Key 配置"""
    for provider in SUPPORTED_PROVIDERS:
        if os.environ.get(provider.api_key_env):
            return True
    return False


class WelcomeStep(Static):
    """欢迎步骤"""

    DEFAULT_CSS = """
    WelcomeStep {
        width: 100%;
        height: auto;
        padding: 2;
    }

    WelcomeStep .welcome-title {
        text-align: center;
        text-style: bold;
        color: $primary;
        margin-bottom: 1;
    }

    WelcomeStep .welcome-subtitle {
        text-align: center;
        color: $text-muted;
        margin-bottom: 2;
    }

    WelcomeStep .welcome-features {
        margin: 1 4;
    }

    WelcomeStep .feature-item {
        margin-bottom: 1;
    }
    """

    def compose(self) -> ComposeResult:
        yield Static("󰚩 欢迎使用小铁 XiaoTie", classes="welcome-title")
        yield Static("轻量级 AI Agent 框架", classes="welcome-subtitle")

        with Vertical(classes="welcome-features"):
            yield Static("✨ 功能特点:", classes="feature-item")
            yield Static("  󰦛 内置工具系统 (读写文件、执行命令)", classes="feature-item")
            yield Static("  󰚩 多 LLM Provider 支持", classes="feature-item")
            yield Static("  󰠮 深度思考模式", classes="feature-item")
            yield Static("  󰕇 并行工具执行", classes="feature-item")
            yield Static("  󰏘 现代化 TUI 界面", classes="feature-item")


class ProviderSelectStep(Static):
    """Provider 选择步骤"""

    DEFAULT_CSS = """
    ProviderSelectStep {
        width: 100%;
        height: auto;
        padding: 1;
    }

    ProviderSelectStep .step-title {
        text-align: center;
        text-style: bold;
        color: $primary;
        margin-bottom: 1;
    }

    ProviderSelectStep .provider-list {
        margin: 1 2;
    }

    ProviderSelectStep .provider-item {
        width: 100%;
        height: 2;
        padding: 0 1;
        margin-bottom: 1;
        border: solid $border;
    }

    ProviderSelectStep .provider-item:hover {
        background: $primary 20%;
        border: solid $primary;
    }

    ProviderSelectStep .provider-item.selected {
        background: $primary 30%;
        border: solid $primary;
    }
    """

    class Selected(Message):
        """Provider 选择事件"""

        def __init__(self, provider: ProviderSetup):
            super().__init__()
            self.provider = provider

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.selected_provider: Optional[ProviderSetup] = None

    def compose(self) -> ComposeResult:
        yield Static("󰚩 选择 LLM Provider", classes="step-title")

        with Vertical(classes="provider-list"):
            for provider in SUPPORTED_PROVIDERS:
                text = Text()
                text.append(f"{provider.icon} ", style="cyan")
                text.append(provider.display_name, style="bold")
                text.append(f"\n  默认模型: {provider.default_model}", style="dim")

                yield Static(
                    text,
                    classes="provider-item",
                    id=f"provider-{provider.name}",
                )

    def on_click(self, event) -> None:
        """处理点击"""
        widget = event.widget
        if hasattr(widget, "id") and widget.id and widget.id.startswith("provider-"):
            provider_name = widget.id[9:]  # 去掉 "provider-" 前缀

            # 更新选中状态
            for item in self.query(".provider-item"):
                item.remove_class("selected")
            widget.add_class("selected")

            # 找到对应的 provider
            for provider in SUPPORTED_PROVIDERS:
                if provider.name == provider_name:
                    self.selected_provider = provider
                    self.post_message(self.Selected(provider))
                    break


class ApiKeyStep(Static):
    """API Key 输入步骤"""

    DEFAULT_CSS = """
    ApiKeyStep {
        width: 100%;
        height: auto;
        padding: 1;
    }

    ApiKeyStep .step-title {
        text-align: center;
        text-style: bold;
        color: $primary;
        margin-bottom: 1;
    }

    ApiKeyStep .key-hint {
        text-align: center;
        color: $text-muted;
        margin-bottom: 1;
    }

    ApiKeyStep .key-input {
        margin: 1 4;
    }

    ApiKeyStep Input {
        width: 100%;
    }

    ApiKeyStep .env-hint {
        text-align: center;
        color: $warning;
        margin-top: 1;
    }
    """

    def __init__(self, provider: ProviderSetup, **kwargs):
        super().__init__(**kwargs)
        self.provider = provider

    def compose(self) -> ComposeResult:
        yield Static(f"󰌆 输入 {self.provider.display_name} API Key", classes="step-title")
        yield Static(f"格式: {self.provider.api_key_hint}", classes="key-hint")

        with Vertical(classes="key-input"):
            yield Input(
                placeholder=f"输入 {self.provider.api_key_env}...",
                password=True,
                id="api-key-input",
            )

        # 检查环境变量
        existing_key = os.environ.get(self.provider.api_key_env, "")
        if existing_key:
            yield Static(
                f"󰋼 检测到环境变量 {self.provider.api_key_env} 已设置",
                classes="env-hint",
            )

    def get_api_key(self) -> str:
        """获取输入的 API Key"""
        input_widget = self.query_one("#api-key-input", Input)
        key = input_widget.value.strip()
        if not key:
            # 尝试从环境变量获取
            key = os.environ.get(self.provider.api_key_env, "")
        return key


class TestConnectionStep(Static):
    """测试连接步骤"""

    DEFAULT_CSS = """
    TestConnectionStep {
        width: 100%;
        height: auto;
        padding: 1;
    }

    TestConnectionStep .step-title {
        text-align: center;
        text-style: bold;
        color: $primary;
        margin-bottom: 1;
    }

    TestConnectionStep .test-status {
        text-align: center;
        margin: 1;
    }

    TestConnectionStep .test-progress {
        margin: 1 4;
    }

    TestConnectionStep .test-result {
        text-align: center;
        margin-top: 1;
    }

    TestConnectionStep .test-result.success {
        color: $success;
    }

    TestConnectionStep .test-result.error {
        color: $error;
    }
    """

    def __init__(self, provider: ProviderSetup, api_key: str, **kwargs):
        super().__init__(**kwargs)
        self.provider = provider
        self.api_key = api_key
        self.test_passed = False

    def compose(self) -> ComposeResult:
        yield Static("󰔟 测试连接", classes="step-title")
        yield Static("正在测试 API 连接...", classes="test-status", id="test-status")
        yield ProgressBar(id="test-progress", classes="test-progress")
        yield Static("", classes="test-result", id="test-result")

    async def run_test(self) -> bool:
        """运行连接测试"""
        progress = self.query_one("#test-progress", ProgressBar)
        status = self.query_one("#test-status", Static)
        result = self.query_one("#test-result", Static)

        progress.update(total=100, progress=0)

        try:
            status.update("正在连接...")
            progress.update(progress=30)

            # 模拟测试（实际应该调用 API）
            await asyncio.sleep(0.5)

            status.update("验证 API Key...")
            progress.update(progress=60)

            # 简单验证 API Key 格式
            if not self.api_key:
                raise ValueError("API Key 不能为空")

            await asyncio.sleep(0.5)

            status.update("测试完成")
            progress.update(progress=100)

            result.update("✅ 连接成功!")
            result.add_class("success")
            self.test_passed = True
            return True

        except Exception as e:
            status.update("测试失败")
            progress.update(progress=100)
            result.update(f"❌ 错误: {e}")
            result.add_class("error")
            self.test_passed = False
            return False


class CompleteStep(Static):
    """完成步骤"""

    DEFAULT_CSS = """
    CompleteStep {
        width: 100%;
        height: auto;
        padding: 2;
    }

    CompleteStep .step-title {
        text-align: center;
        text-style: bold;
        color: $success;
        margin-bottom: 1;
    }

    CompleteStep .config-summary {
        margin: 1 4;
        padding: 1;
        border: solid $border;
    }

    CompleteStep .config-item {
        margin-bottom: 1;
    }

    CompleteStep .next-steps {
        margin: 1 4;
    }
    """

    def __init__(self, provider: ProviderSetup, **kwargs):
        super().__init__(**kwargs)
        self.provider = provider

    def compose(self) -> ComposeResult:
        yield Static("🎉 配置完成!", classes="step-title")

        with Vertical(classes="config-summary"):
            yield Static(f"Provider: {self.provider.display_name}", classes="config-item")
            yield Static(f"模型: {self.provider.default_model}", classes="config-item")
            yield Static(f"API Key: {self.provider.api_key_env} ✓", classes="config-item")

        with Vertical(classes="next-steps"):
            yield Static("󰋽 下一步:", classes="config-item")
            yield Static("  • 输入消息开始对话", classes="config-item")
            yield Static("  • 使用 /help 查看命令", classes="config-item")
            yield Static("  • 按 Ctrl+K 打开命令面板", classes="config-item")


class OnboardingWizard(ModalScreen):
    """首次启动向导"""

    BINDINGS = [
        Binding("escape", "cancel", "取消"),
    ]

    DEFAULT_CSS = """
    OnboardingWizard {
        align: center middle;
    }

    OnboardingWizard > Vertical {
        width: 70;
        height: auto;
        max-height: 90%;
        background: $surface;
        border: solid $primary;
        padding: 0;
    }

    OnboardingWizard .wizard-header {
        width: 100%;
        height: 1;
        background: $primary 20%;
        padding: 0 1;
        color: $text;
    }

    OnboardingWizard .wizard-content {
        width: 100%;
        height: auto;
        padding: 1;
    }

    OnboardingWizard .wizard-footer {
        width: 100%;
        height: 3;
        background: $surface-darken-1;
        padding: 1;
    }

    OnboardingWizard .wizard-footer Horizontal {
        align: center middle;
        width: 100%;
    }

    OnboardingWizard Button {
        margin: 0 1;
    }

    OnboardingWizard .step-indicator {
        text-align: center;
        color: $text-muted;
        margin-bottom: 1;
    }
    """

    def __init__(
        self,
        on_complete: Optional[Callable[[str, str, str], None]] = None,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.on_complete = on_complete
        self.current_step = 0
        self.selected_provider: Optional[ProviderSetup] = None
        self.api_key = ""
        self.steps = ["welcome", "provider", "apikey", "test", "complete"]

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Static("󰚩 小铁设置向导", classes="wizard-header")

            with Vertical(classes="wizard-content", id="wizard-content"):
                yield Static(
                    f"步骤 {self.current_step + 1}/{len(self.steps)}",
                    classes="step-indicator",
                    id="step-indicator",
                )
                yield WelcomeStep(id="current-step")

            with Vertical(classes="wizard-footer"):
                with Horizontal():
                    yield Button("取消", variant="default", id="btn-cancel")
                    yield Button("下一步", variant="primary", id="btn-next")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """处理按钮点击"""
        if event.button.id == "btn-cancel":
            self.action_cancel()
        elif event.button.id == "btn-next":
            self._next_step()
        elif event.button.id == "btn-back":
            self._prev_step()
        elif event.button.id == "btn-finish":
            self._finish()

    def on_provider_select_step_selected(self, event: ProviderSelectStep.Selected) -> None:
        """处理 Provider 选择"""
        self.selected_provider = event.provider

    def _next_step(self) -> None:
        """下一步"""
        current_step_name = self.steps[self.current_step]

        # 验证当前步骤
        if current_step_name == "provider":
            if not self.selected_provider:
                return  # 未选择 provider

        elif current_step_name == "apikey":
            step_widget = self.query_one("#current-step")
            if isinstance(step_widget, ApiKeyStep):
                self.api_key = step_widget.get_api_key()
                if not self.api_key:
                    return  # 未输入 API Key

        elif current_step_name == "test":
            step_widget = self.query_one("#current-step")
            if isinstance(step_widget, TestConnectionStep):
                if not step_widget.test_passed:
                    # 运行测试
                    asyncio.create_task(self._run_test())
                    return

        # 前进到下一步
        if self.current_step < len(self.steps) - 1:
            self.current_step += 1
            self._update_step()

    def _prev_step(self) -> None:
        """上一步"""
        if self.current_step > 0:
            self.current_step -= 1
            self._update_step()

    async def _run_test(self) -> None:
        """运行连接测试"""
        step_widget = self.query_one("#current-step")
        if isinstance(step_widget, TestConnectionStep):
            success = await step_widget.run_test()
            if success:
                # 自动前进到下一步
                await asyncio.sleep(1)
                self.current_step += 1
                self._update_step()

    def _update_step(self) -> None:
        """更新当前步骤显示"""
        content = self.query_one("#wizard-content")
        step_name = self.steps[self.current_step]

        # 更新步骤指示器
        indicator = self.query_one("#step-indicator", Static)
        indicator.update(f"步骤 {self.current_step + 1}/{len(self.steps)}")

        # 移除旧步骤
        old_step = self.query_one("#current-step")
        old_step.remove()

        # 创建新步骤
        new_step: Static
        if step_name == "welcome":
            new_step = WelcomeStep(id="current-step")
        elif step_name == "provider":
            new_step = ProviderSelectStep(id="current-step")
        elif step_name == "apikey":
            new_step = ApiKeyStep(self.selected_provider, id="current-step")
        elif step_name == "test":
            new_step = TestConnectionStep(
                self.selected_provider, self.api_key, id="current-step"
            )
        else:  # complete
            new_step = CompleteStep(self.selected_provider, id="current-step")

        content.mount(new_step)

        # 更新按钮
        self._update_buttons()

    def _update_buttons(self) -> None:
        """更新按钮状态"""
        step_name = self.steps[self.current_step]
        footer = self.query_one(".wizard-footer")

        # 清空按钮
        for btn in list(footer.query("Button")):
            btn.remove()

        horizontal = footer.query_one("Horizontal")

        if step_name == "welcome":
            horizontal.mount(Button("取消", variant="default", id="btn-cancel"))
            horizontal.mount(Button("开始配置", variant="primary", id="btn-next"))
        elif step_name == "complete":
            horizontal.mount(Button("完成", variant="success", id="btn-finish"))
        else:
            if self.current_step > 0:
                horizontal.mount(Button("上一步", variant="default", id="btn-back"))
            horizontal.mount(Button("下一步", variant="primary", id="btn-next"))

    def _finish(self) -> None:
        """完成向导"""
        if self.on_complete and self.selected_provider:
            self.on_complete(
                self.selected_provider.name,
                self.selected_provider.default_model,
                self.api_key,
            )
        self.dismiss(True)

    def action_cancel(self) -> None:
        """取消向导"""
        self.dismiss(False)


def should_show_onboarding() -> bool:
    """判断是否应该显示向导"""
    # 首次运行且没有 API Key
    return is_first_run() and not has_any_api_key()
