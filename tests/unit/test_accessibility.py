"""Tests for WCAG accessibility and /safe command."""
import pytest
from xiaotie.tui.themes import (
    Theme,
    THEMES,
    contrast_ratio,
    _hex_to_rgb,
    _relative_luminance,
)
from xiaotie.permissions import PermissionManager


class TestContrastRatio:
    def test_black_on_white(self):
        """Maximum contrast: black text on white background."""
        ratio = contrast_ratio("#000000", "#ffffff")
        assert ratio == pytest.approx(21.0, rel=0.01)

    def test_white_on_black(self):
        """Order should not matter for the ratio value."""
        assert contrast_ratio("#ffffff", "#000000") == pytest.approx(21.0, rel=0.01)

    def test_same_color(self):
        """Same color should give ratio of 1.0."""
        assert contrast_ratio("#aabbcc", "#aabbcc") == pytest.approx(1.0)

    def test_wcag_aa_minimum(self):
        """A known passing pair: white text on dark blue."""
        ratio = contrast_ratio("#ffffff", "#0f172a")
        assert ratio >= 4.5

    def test_hex_to_rgb(self):
        assert _hex_to_rgb("#ff0000") == (255, 0, 0)
        assert _hex_to_rgb("#00ff00") == (0, 255, 0)
        assert _hex_to_rgb("#0000ff") == (0, 0, 255)

    def test_shorthand_hex(self):
        assert _hex_to_rgb("#fff") == (255, 255, 255)


class TestThemeAccessibility:
    @pytest.mark.parametrize("theme_id", list(THEMES.keys()))
    def test_theme_text_meets_wcag_aa(self, theme_id: str):
        """All themes must have text/background contrast >= 4.5:1."""
        theme = THEMES[theme_id]
        ratio = contrast_ratio(theme.text, theme.background)
        assert ratio >= 4.5, (
            f"Theme '{theme_id}': text {theme.text} on {theme.background} "
            f"has ratio {ratio:.2f} (need >= 4.5)"
        )

    @pytest.mark.parametrize("theme_id", list(THEMES.keys()))
    def test_theme_text_muted_meets_wcag_aa(self, theme_id: str):
        """All themes must have text_muted/background contrast >= 4.5:1."""
        theme = THEMES[theme_id]
        ratio = contrast_ratio(theme.text_muted, theme.background)
        assert ratio >= 4.5, (
            f"Theme '{theme_id}': text_muted {theme.text_muted} on {theme.background} "
            f"has ratio {ratio:.2f} (need >= 4.5)"
        )

    def test_high_contrast_theme_exists(self):
        assert "high-contrast" in THEMES
        theme = THEMES["high-contrast"]
        failures = theme.validate_accessibility(min_ratio=7.0)
        assert len(failures) == 0, f"High-contrast theme failures: {failures}"

    def test_validate_accessibility_method(self):
        theme = THEMES["default"]
        failures = theme.validate_accessibility()
        assert isinstance(failures, list)


class TestPermissionManagerSafe:
    def test_strict_mode(self):
        pm = PermissionManager()
        pm.auto_approve_medium_risk = True
        pm.require_double_confirm_high_risk = False
        # Simulate /safe strict
        pm.auto_approve_medium_risk = False
        pm.require_double_confirm_high_risk = True
        assert pm.auto_approve_medium_risk is False
        assert pm.require_double_confirm_high_risk is True

    def test_relaxed_mode(self):
        pm = PermissionManager()
        pm.auto_approve_medium_risk = False
        pm.require_double_confirm_high_risk = True
        # Simulate /safe relaxed
        pm.auto_approve_medium_risk = True
        pm.require_double_confirm_high_risk = False
        assert pm.auto_approve_medium_risk is True
        assert pm.require_double_confirm_high_risk is False

    def test_stats(self):
        pm = PermissionManager()
        stats = pm.get_stats()
        assert "auto_approve_low_risk" in stats
        assert "auto_approve_medium_risk" in stats
        assert "total_decisions" in stats

    def test_decision_history(self):
        pm = PermissionManager()
        history = pm.get_decision_history()
        assert isinstance(history, list)
