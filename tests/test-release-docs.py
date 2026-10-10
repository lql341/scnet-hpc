#!/usr/bin/env python3

from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / ".github" / "scripts" / "release_docs.py"


class ReleaseDocsTests(unittest.TestCase):
    def test_replaces_legacy_history_and_is_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "VERSION").write_text("1.2.3\n")
            (root / "CHANGELOG.md").write_text(
                "# Changelog\n\n## 1.2.3 - 2026-10-10\n\n- Current change.\n"
            )
            (root / "RELEASE_HIGHLIGHTS.md").write_text("- Current highlight.\n")
            (root / "RELEASE_HIGHLIGHTS_CN.md").write_text("- 当前亮点。\n")
            (root / "README.md").write_text(
                "# Product\n\n"
                "Current release: **1.2.2**\n\n"
                "```bash\nproduct --version\n```\n\n"
                "## What's new in 1.2.2\n\n"
                "- Old highlight.\n\n"
                "Product description that must remain.\n\n"
                "## 1.2.1 highlights\n\n"
                "- Older highlight.\n\n"
                "## Install\n\nInstall text.\n"
            )
            (root / "README_CN.md").write_text(
                "# 产品\n\n"
                "当前版本：**1.2.2**\n\n"
                "## 1.2.2 更新\n\n"
                "- 旧亮点。\n\n"
                "必须保留的产品说明。\n\n"
                "## 1.2.1 更新\n\n"
                "- 更旧的亮点。\n\n"
                "## 安装\n\n安装说明。\n"
            )

            subprocess.run(
                ["python3", str(SCRIPT)],
                cwd=root,
                check=True,
                text=True,
                capture_output=True,
            )
            first_english = (root / "README.md").read_text()
            first_chinese = (root / "README_CN.md").read_text()

            self.assertIn("Current release: **1.2.3**", first_english)
            self.assertIn("## 1.2.3 highlights", first_english)
            self.assertIn("Product description that must remain.", first_english)
            self.assertNotIn("1.2.2", first_english)
            self.assertNotIn("1.2.1", first_english)

            self.assertIn("当前版本：**1.2.3**", first_chinese)
            self.assertIn("## 1.2.3 更新", first_chinese)
            self.assertIn("必须保留的产品说明。", first_chinese)
            self.assertNotIn("1.2.2", first_chinese)
            self.assertNotIn("1.2.1", first_chinese)

            subprocess.run(
                ["python3", str(SCRIPT), "--check"],
                cwd=root,
                check=True,
                text=True,
                capture_output=True,
            )
            self.assertEqual(first_english, (root / "README.md").read_text())
            self.assertEqual(first_chinese, (root / "README_CN.md").read_text())


if __name__ == "__main__":
    unittest.main()
