# AgentBuilder SDK v2 演示
# VHS 演示脚本 - 展示 AgentBuilder API

Output sdk-demo.gif

Set FontSize 14
Set Width 1200
Set Height 800
Set Theme "Dracula"
Set Padding 20
Set TypingSpeed 30ms

# 启动 Python
Type "python3"
Enter
Sleep 1s

# 导入模块
Type "from xiaotie import AgentBuilder"
Enter
Sleep 500ms

Type "from xiaotie.tools import ReadTool, WriteTool, BashTool"
Enter
Sleep 500ms

# 创建 Agent
Type "agent = ("
Enter
Type "    AgentBuilder('demo-agent')"
Enter
Type "    .with_llm('claude-sonnet-4')"
Enter
Type "    .with_tools([ReadTool(), WriteTool(), BashTool()])"
Enter
Type "    .with_memory(max_tokens=4000)"
Enter
Type "    .build()"
Enter
Type ")"
Enter
Sleep 1s

# 显示 Agent 信息
Type "print(agent)"
Enter
Sleep 1s

# 退出
Type "exit()"
Enter
Sleep 500ms
