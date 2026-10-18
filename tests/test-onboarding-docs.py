"""Check first-use README propagation without network access."""
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / ".github/scripts/onboarding_docs.py"


class OnboardingDocsTests(unittest.TestCase):
    def test_both_distribution_layouts_preserve_content_and_resolve_links(self):
        for layout in ("skills/scnet-hpc", "plugins/scnet-hpc/skills/scnet-hpc"):
            with self.subTest(layout=layout), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                guide = root / layout / "references/first-use.md"
                guide.parent.mkdir(parents=True)
                guide.write_text("guide", encoding="utf-8")
                for filename, old in (
                    ("README.md", "- Windows through WSL2; native Windows execution is not supported by the bundled Bash scripts"),
                    ("README_CN.md", "- Windows 通过 WSL2 使用；内置 Bash 脚本不支持 Windows 原生环境"),
                ):
                    (root / filename).write_text(
                        "# Product\n\n<!-- scnet-release:end -->\n\n## Install\n\nKeep installation instructions.\n\n" + old + "\n",
                        encoding="utf-8",
                    )
                command = [sys.executable, str(SCRIPT), "--skill-dir", layout]
                subprocess.run(command, cwd=root, check=True)
                first = {name: (root / name).read_bytes() for name in ("README.md", "README_CN.md")}
                subprocess.run(command, cwd=root, check=True)
                for name, content in first.items():
                    self.assertEqual((root / name).read_bytes(), content)
                    text = content.decode("utf-8")
                    self.assertIn("Keep installation instructions.", text)
                    self.assertIn(f"]({layout}/references/first-use.md)", text)
                    self.assertIn("Accesskey", text)
                    self.assertIn("Secretkey", text)
                    self.assertIn("Credential Manager" if name == "README.md" else "系统凭据管理器", text)


if __name__ == "__main__":
    unittest.main()
