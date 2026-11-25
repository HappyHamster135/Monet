"""KWin keeps independent preferences for hover, raising and click delivery."""
import unittest
from unittest.mock import patch

from tests.test_look import quick_helper


class WindowFocus(unittest.TestCase):
    def test_first_click_preserves_stacking_and_recognizes_the_native_release_action(self):
        q = quick_helper()
        for current, choice, expected in [
            ("Activate", "pass", "Activate and pass click"),
            ("activate AND pass click", "focus", "Activate"),
            ("Activate and raise", "pass", "Activate, raise and pass click"),
            ("Activate, pass click and raise on release", "pass", "Activate, pass click and raise on release"),
        ]:
            with self.subTest(current=current), patch.object(q, "kread_values", return_value=["ClickToFocus", expected, "457"]), \
                    patch.object(q, "kwrite", return_value=True) as write, patch.object(q, "kread", return_value=current), \
                    patch.object(q, "busctl", return_value=""):
                self.assertTrue(q.change_window_focus("first", choice)["ok"])
                write.assert_called_once_with("kwinrc", "MouseBindings", "CommandWindow1", expected)

    def test_custom_choices_read_only_and_failed_changes_reported(self):
        q = quick_helper()
        with patch.object(q, "kread_values", return_value=["FocusUnderMouse", "Minimize", "457"]) as values, \
                patch.object(q, "kwrite", return_value=False) as write, patch.object(q, "busctl", return_value=None) as reload:
            state = q.window_focus()
            self.assertEqual((state["policy"], state["first"], state["delay"]), ("FocusUnderMouse", "custom", 457))
            self.assertEqual(q.change_window_focus("delay", "-1")["problem"], "request")
            write.assert_not_called()
            self.assertEqual(q.change_window_focus("policy", "click")["problem"], "save")
            reload.assert_not_called()
            write.return_value = True
            self.assertEqual(q.change_window_focus("policy", "click")["problem"], "save")
            values.return_value = ["ClickToFocus", "Minimize", "457"]
            self.assertEqual(q.change_window_focus("policy", "click")["problem"], "reload")
            write.assert_called_with("kwinrc", "Windows", "FocusPolicy", "ClickToFocus")
