# 小铁 XiaoTie Demo
# VHS 演示脚本 - 展示核心功能

Output demo.gif

Set FontSize 14
Set Width 1200
Set Height 800
Set Theme "Dracula"
Set Padding 20
Set TypingSpeed 50ms

# 启动小铁
Type "xiaotie"
Enter
Sleep 2s

# 显示欢迎界面
Sleep 1s

# 输入问题
Type "帮我创建一个 hello.py 文件，打印 Hello World"
Sleep 500ms
Enter

# 等待 AI 响应
Sleep 5s

# 显示工具调用
Sleep 2s

# 查看文件
Type "/tree"
Enter
Sleep 2s

# 显示帮助
Type "/help"
Enter
Sleep 2s

# 退出
Type "/quit"
Enter
Sleep 1s
