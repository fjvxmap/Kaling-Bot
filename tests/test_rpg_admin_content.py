from __future__ import annotations

import unittest

from tools.rpg_admin.app import normalize_content, read_content, validate_content


class RPGAdminContentTests(unittest.TestCase):
    def test_current_content_normalizes_and_validates(self) -> None:
        content = read_content()
        normalize_content(content)
        self.assertEqual(validate_content(content), [])


if __name__ == "__main__":
    unittest.main()
