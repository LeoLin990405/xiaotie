# 小铁 TUI 模式演示
# VHS 演示脚本 - 展示 TUI 功能

Output tui-demo.gif

Set FontSize 14
Set Width 1200
Set Height 800
Set Theme "Dracula"
Set Padding 20
Set TypingSpeed 50ms

# 启动 TUI 模式
Type "xiaotie --tui"
Enter
Sleep 3s

# 显示命令面板
Ctrl+k
Sleep 1s

# 搜索命令
Type "help"
Sleep 500ms
Enter
Sleep 2s

# 关闭帮助
Escape
Sleep 500ms

# 切换主题
Ctrl+t
Sleep 1s

# 选择主题
Down
Down
Enter
Sleep 1s

# 切换模型
Ctrl+m
Sleep 1s
Down
Enter
Sleep 1s

# 切换侧边栏
Ctrl+b
Sleep 1s
Ctrl+b
Sleep 1s

# 输入问题
Type "你好，小铁！"
Enter
Sleep 3s

# 退出
Ctrl+q
Sleep 1s
