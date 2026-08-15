from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP_JS = ROOT / "web" / "rpg_web" / "static" / "rpg_web" / "app.js"
APP_CSS = ROOT / "web" / "rpg_web" / "static" / "rpg_web" / "app.css"
INDEX_TEMPLATE = ROOT / "web" / "rpg_web" / "templates" / "rpg_web" / "index.html"


class RPGWebNotificationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app_js = APP_JS.read_text(encoding="utf-8")
        cls.app_css = APP_CSS.read_text(encoding="utf-8")
        cls.index_template = INDEX_TEMPLATE.read_text(encoding="utf-8")

    def test_fixed_toast_ui_is_not_rendered_or_styled(self) -> None:
        self.assertNotIn('id="toast-region"', self.index_template)
        self.assertNotRegex(self.app_css, r"(?m)^\s*\.toast(?:-region|\b)")
        self.assertNotRegex(self.app_css, r"@keyframes\s+toast-")

    def test_action_paths_cannot_create_toasts(self) -> None:
        self.assertNotIn("#toast-region", self.app_js)
        self.assertIsNone(re.search(r"\bfunction\s+toast\s*\(", self.app_js))
        self.assertIsNone(re.search(r"\btoast\s*\(", self.app_js))


if __name__ == "__main__":
    unittest.main()
