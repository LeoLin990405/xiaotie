from dataclasses import dataclass

@dataclass
class AgentConfig:
    """Agent 配置"""

    max_steps: int = 50
    token_limit: int = 100000
    parallel_tools: bool = True
    enable_thinking: bool = True
    stream: bool = True
    quiet: bool = False
    # 摘要配置
    summary_threshold: float = 0.8  # 达到 token_limit 的 80% 时触发摘要
    summary_keep_recent: int = 5  # 摘要时保留最近 N 条用户消息
    # 缓存配置
    cache_enabled: bool = True
    cache_ttl: int = 3600  # 1小时
