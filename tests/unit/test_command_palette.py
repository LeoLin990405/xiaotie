"""Command Palette 单元测试"""

import pytest

from xiaotie.tui.command_palette import (
    Command,
    CommandCategory,
    DEFAULT_COMMANDS,
    fuzzy_match,
    search_commands,
)


class TestFuzzyMatch:
    """模糊匹配算法测试"""

    def test_exact_match(self):
        """测试完全匹配"""
        matched, score = fuzzy_match("help", "help")
        assert matched
        assert score == 1000

    def test_prefix_match(self):
        """测试前缀匹配"""
        matched, score = fuzzy_match("hel", "help")
        assert matched
        assert score > 800

    def test_contains_match(self):
        """测试包含匹配"""
        matched, score = fuzzy_match("elp", "help")
        assert matched
        assert score > 700

    def test_subsequence_match(self):
        """测试子序列匹配"""
        matched, score = fuzzy_match("hp", "help")
        assert matched
        assert score > 0

    def test_no_match(self):
        """测试不匹配"""
        matched, score = fuzzy_match("xyz", "help")
        assert not matched
        assert score == 0

    def test_empty_query(self):
        """测试空查询"""
        matched, score = fuzzy_match("", "help")
        assert matched
        assert score == 0

    def test_case_insensitive(self):
        """测试大小写不敏感"""
        matched, score = fuzzy_match("HELP", "help")
        assert matched
        assert score == 1000

    def test_word_boundary_bonus(self):
        """测试单词边界加分"""
        # "new" 在 "new_session" 开头应该比在中间分数高
        matched1, score1 = fuzzy_match("new", "new_session")
        matched2, score2 = fuzzy_match("new", "renew")
        assert matched1 and matched2
        assert score1 > score2

    def test_consecutive_bonus(self):
        """测试连续匹配加分"""
        # "hel" 连续匹配应该比 "h_e_l" 分散匹配分数高
        matched1, score1 = fuzzy_match("hel", "help")
        matched2, score2 = fuzzy_match("hel", "h_e_l_p")
        assert matched1 and matched2
        assert score1 > score2


class TestSearchCommands:
    """命令搜索测试"""

    def test_search_empty_query(self):
        """测试空查询返回所有命令"""
        results = search_commands("", DEFAULT_COMMANDS)
        assert len(results) > 0
        assert len(results) <= 20  # 默认限制

    def test_search_by_name(self):
        """测试按名称搜索"""
        results = search_commands("help", DEFAULT_COMMANDS)
        assert len(results) > 0
        assert results[0][0].name == "help"

    def test_search_by_alias(self):
        """测试按别名搜索"""
        results = search_commands("q", DEFAULT_COMMANDS)
        # "q" 是 "quit" 的别名
        names = [r[0].name for r in results]
        assert "quit" in names

    def test_search_by_description(self):
        """测试按描述搜索"""
        results = search_commands("退出", DEFAULT_COMMANDS)
        assert len(results) > 0
        # 应该找到 quit 命令
        names = [r[0].name for r in results]
        assert "quit" in names

    def test_search_limit(self):
        """测试结果限制"""
        results = search_commands("", DEFAULT_COMMANDS, limit=5)
        assert len(results) <= 5

    def test_search_sorted_by_score(self):
        """测试结果按分数排序"""
        results = search_commands("s", DEFAULT_COMMANDS)
        if len(results) > 1:
            scores = [r[1] for r in results]
            assert scores == sorted(scores, reverse=True)

    def test_search_no_results(self):
        """测试无结果"""
        results = search_commands("xyzabc123", DEFAULT_COMMANDS)
        assert len(results) == 0


class TestCommand:
    """Command 数据类测试"""

    def test_create_command(self):
        """测试创建命令"""
        cmd = Command(
            name="test",
            description="测试命令",
            shortcut="Ctrl+T",
            category=CommandCategory.GENERAL,
            icon="󰋽",
            aliases=["t", "tst"],
        )
        assert cmd.name == "test"
        assert cmd.description == "测试命令"
        assert cmd.shortcut == "Ctrl+T"
        assert cmd.category == CommandCategory.GENERAL
        assert cmd.icon == "󰋽"
        assert "t" in cmd.aliases

    def test_search_text(self):
        """测试搜索文本生成"""
        cmd = Command(
            name="help",
            description="显示帮助",
            aliases=["h", "?"],
        )
        search_text = cmd.search_text
        assert "help" in search_text
        assert "显示帮助" in search_text
        assert "h" in search_text
        assert "?" in search_text

    def test_default_values(self):
        """测试默认值"""
        cmd = Command(name="test", description="测试")
        assert cmd.shortcut == ""
        assert cmd.category == CommandCategory.GENERAL
        assert cmd.icon == ""
        assert cmd.aliases == []


class TestCommandCategory:
    """CommandCategory 枚举测试"""

    def test_all_categories(self):
        """测试所有分类"""
        expected = ["general", "session", "model", "display", "tools", "debug"]
        actual = [c.value for c in CommandCategory]
        assert set(expected) == set(actual)

    def test_category_is_string(self):
        """测试分类是字符串类型"""
        assert isinstance(CommandCategory.GENERAL, str)
        assert CommandCategory.GENERAL == "general"


class TestDefaultCommands:
    """默认命令列表测试"""

    def test_has_essential_commands(self):
        """测试包含必要命令"""
        names = [cmd.name for cmd in DEFAULT_COMMANDS]
        essential = ["help", "quit", "new", "save", "models", "themes"]
        for cmd in essential:
            assert cmd in names, f"Missing essential command: {cmd}"

    def test_all_commands_have_description(self):
        """测试所有命令都有描述"""
        for cmd in DEFAULT_COMMANDS:
            assert cmd.description, f"Command {cmd.name} missing description"

    def test_all_commands_have_category(self):
        """测试所有命令都有分类"""
        for cmd in DEFAULT_COMMANDS:
            assert cmd.category in CommandCategory

    def test_no_duplicate_names(self):
        """测试无重复命令名"""
        names = [cmd.name for cmd in DEFAULT_COMMANDS]
        assert len(names) == len(set(names))

    def test_no_duplicate_shortcuts(self):
        """测试无重复快捷键（排除空快捷键）"""
        shortcuts = [cmd.shortcut for cmd in DEFAULT_COMMANDS if cmd.shortcut]
        assert len(shortcuts) == len(set(shortcuts))
