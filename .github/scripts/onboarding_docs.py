"""Propagate the canonical first-use briefing into distribution READMEs."""
from __future__ import annotations

import argparse
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--skill-dir", required=True)
    args = parser.parse_args()
    source = Path(__file__).resolve().parents[2]
    start, end = "<!-- scnet-onboarding:start -->", "<!-- scnet-onboarding:end -->"
    for filename, heading, following in (
        ("README.md", "## What to prepare for first use", "Supported local operating systems:"),
        ("README_CN.md", "## 第一次使用，需要准备什么？", "支持的本地操作系统："),
    ):
        canonical = (source / filename).read_text(encoding="utf-8")
        section = heading + canonical.split(heading, 1)[1].split(following, 1)[0]
        section = section.replace(
            "(references/first-use.md)", f"({args.skill_dir}/references/first-use.md)"
        ).replace(" and configuration panel below.", ".").replace("和下方配置面板。", "。")
        block = start + "\n" + section.strip() + "\n" + end
        path = Path(filename)
        text = path.read_text(encoding="utf-8")
        if start in text:
            before, rest = text.split(start, 1)
            _, after = rest.split(end, 1)
            text = before + block + after
        else:
            position = text.find("\n## ", text.index("<!-- scnet-release:end -->"))
            if position < 0:
                raise ValueError(f"No insertion point in {filename}")
            text = text[:position] + "\n" + block + "\n" + text[position:]
        text = text.replace(
            "- Windows through WSL2; native Windows execution is not supported by the bundled Bash scripts",
            "- Native Windows supports Python OpenAPI and Windows Credential Manager; use WSL2 for automatic SSH installation and Bash workflows",
        ).replace(
            "- Windows 通过 WSL2 使用；内置 Bash 脚本不支持 Windows 原生环境",
            "- Windows 原生支持 Python OpenAPI 和系统凭据管理器；SSH 自动安装及 Bash 工作流通过 WSL2 使用",
        )
        path.write_text(text, encoding="utf-8")


if __name__ == "__main__":
    main()
