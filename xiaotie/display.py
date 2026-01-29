"""终端显示增强模块

学习自 Open Interpreter 的显示设计：
- Markdown 渲染
- 代码高亮
- 进度指示
- 思考过程折叠显示
"""

from __future__ import annotations

import sys
from typing import Optional

# 尝试导入 rich，如果没有则使用简单输出
try:
    from rich.console import Console
    from rich.markdown import Markdown
    from rich.syntax import Syntax
    from rich.panel import Panel
    from rich.text import Text
    from rich.live import Live
    from rich.spinner import Spinner
    HAS_RICH = True
except ImportError:
    HAS_RICH = False


class Display:
    """终端显示增强"""

    def __init__(self, use_rich: bool = True):
        self.use_rich = use_rich and HAS_RICH
        if self.use_rich:
            self.console = Console()
        else:
            self.console = None

    def print(self, text: str, style: Optional[str] = None):
        """打印文本"""
        if self.use_rich:
            self.console.print(text, style=style)
        else:
            print(text)

    def markdown(self, text: str):
        """渲染 Markdown"""
        if self.use_rich:
            self.console.print(Markdown(text))
        else:
            print(text)

    def code(self, code: str, language: str = "python", title: Optional[str] = None):
        """代码高亮显示"""
        if self.use_rich:
            syntax = Syntax(code, language, theme="monokai", line_numbers=True)
            if title:
                self.console.print(Panel(syntax, title=title, border_style="blue"))
            else:
                self.console.print(syntax)
        else:
            print(f"```{language}")
            print(code)
            print("```")

    def thinking(self, text: str, collapsed: bool = True):
        """显示思考过程"""
        if self.use_rich:
            if collapsed:
                # 折叠显示，只显示前几行
                lines = text.split("\n")
                preview = "\n".join(lines[:3])
                if len(lines) > 3:
                    preview += f"\n... ({len(lines) - 3} 更多行)"
                self.console.print(Panel(
                    preview,
                    title="💭 思考过程",
                    border_style="dim",
                    expand=False,
                ))
            else:
                self.console.print(Panel(
                    text,
                    title="💭 思考过程",
                    border_style="cyan",
                ))
        else:
            print(f"💭 思考: {text[:200]}...")

    def tool_call(self, name: str, args: dict, result: Optional[str] = None):
        """显示工具调用"""
        if self.use_rich:
            # 工具调用信息
            args_str = ", ".join(f"{k}={repr(v)[:30]}" for k, v in args.items())
            call_text = Text()
            call_text.append("🔧 ", style="bold")
            call_text.append(name, style="bold cyan")
            call_text.append(f"({args_str})", style="dim")

            self.console.print(call_text)

            if result:
                # 结果预览
                result_preview = result[:200] + "..." if len(result) > 200 else result
                self.console.print(f"   → {result_preview}", style="green")
        else:
            print(f"🔧 {name}({args})")
            if result:
                print(f"   → {result[:100]}...")

    def success(self, message: str):
        """成功消息"""
        if self.use_rich:
            self.console.print(f"✅ {message}", style="green")
        else:
            print(f"✅ {message}")

    def error(self, message: str):
        """错误消息"""
        if self.use_rich:
            self.console.print(f"❌ {message}", style="red")
        else:
            print(f"❌ {message}")

    def warning(self, message: str):
        """警告消息"""
        if self.use_rich:
            self.console.print(f"⚠️ {message}", style="yellow")
        else:
            print(f"⚠️ {message}")

    def info(self, message: str):
        """信息消息"""
        if self.use_rich:
            self.console.print(f"ℹ️ {message}", style="blue")
        else:
            print(f"ℹ️ {message}")

    def assistant(self, text: str):
        """助手回复"""
        if self.use_rich:
            self.console.print()
            self.console.print("🤖 小铁:", style="bold cyan")
            self.markdown(text)
        else:
            print(f"\n🤖 小铁:\n{text}")

    def user_prompt(self) -> str:
        """用户输入提示"""
        if self.use_rich:
            return self.console.input("\n[bold]👤 你:[/bold] ")
        else:
            return input("\n👤 你: ")

    def spinner(self, message: str = "思考中..."):
        """返回一个 spinner 上下文管理器"""
        if self.use_rich:
            return self.console.status(f"[cyan]{message}[/cyan]", spinner="dots")
        else:
            # 简单的占位符
            return _DummySpinner(message)


class _DummySpinner:
    """无 rich 时的占位 spinner"""

    def __init__(self, message: str):
        self.message = message

    def __enter__(self):
        print(f"⏳ {self.message}", end="", flush=True)
        return self

    def __exit__(self, *args):
        print(" 完成")

    def update(self, message: str):
        pass


class StreamDisplay:
    """流式输出显示器"""

    def __init__(self, display: Display):
        self.display = display
        self.thinking_buffer = ""
        self.content_buffer = ""
        self.thinking_started = False
        self.content_started = False

    def on_thinking(self, text: str):
        """处理思考内容"""
        if not self.thinking_started:
            if self.display.use_rich:
                self.display.console.print("\n💭 [dim]思考中...[/dim]", end="")
            else:
                print("\n💭 思考中...", end="", flush=True)
            self.thinking_started = True
        self.thinking_buffer += text

    def on_content(self, text: str):
        """处理回复内容"""
        if not self.content_started:
            if self.thinking_started:
                # 结束思考显示
                if self.display.use_rich:
                    self.display.console.print()
                else:
                    print()
            if self.display.use_rich:
                self.display.console.print("\n🤖 [bold cyan]小铁:[/bold cyan]")
            else:
                print("\n🤖 小铁:")
            self.content_started = True

        # 流式输出
        print(text, end="", flush=True)
        self.content_buffer += text

    def finish(self):
        """完成输出"""
        if self.content_started:
            print()  # 换行

    def get_thinking(self) -> str:
        return self.thinking_buffer

    def get_content(self) -> str:
        return self.content_buffer


# 全局显示实例
_display: Optional[Display] = None


def get_display() -> Display:
    """获取全局显示实例"""
    global _display
    if _display is None:
        _display = Display()
    return _display


def set_display(display: Display):
    """设置全局显示实例"""
    global _display
    _display = display
