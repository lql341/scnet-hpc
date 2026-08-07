#!/usr/bin/env bash
# 把这个 skill 安装到本机的 Claude Code 配置目录。
#
#   ./install.sh              # 用户级（所有项目可用）
#   ./install.sh --project    # 当前项目的 .claude/skills/
#   ./install.sh --link       # 用符号链接（改仓库即生效，便于开发）
#
# 幂等：重复运行会先备份已有的同名 skill。

set -euo pipefail

SKILL_NAME="scnet-hpc"
SRC_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

MODE="user"
LINK="no"
for arg in "$@"; do
    case "$arg" in
        --project) MODE="project" ;;
        --link)    LINK="yes" ;;
        -h|--help) sed -n '2,9p' "$0" | sed 's/^# \?//'; exit 0 ;;
        *) echo "未知参数: $arg" >&2; exit 1 ;;
    esac
done

if [ "$MODE" = "project" ]; then
    DST_ROOT="$(pwd)/.claude/skills"
else
    # 尊重 CLAUDE_CONFIG_DIR（有些环境用非默认配置目录）
    DST_ROOT="${CLAUDE_CONFIG_DIR:-$HOME/.claude}/skills"
fi
DST="$DST_ROOT/$SKILL_NAME"

echo "==> 源:   $SRC_DIR"
echo "==> 目标: $DST"

[ -f "$SRC_DIR/SKILL.md" ] || { echo "错误: 源目录里找不到 SKILL.md" >&2; exit 1; }

mkdir -p "$DST_ROOT"

if [ "$(cd "$DST" 2>/dev/null && pwd || echo -)" = "$SRC_DIR" ]; then
    echo "==> 源和目标相同，无需安装"
    exit 0
fi

if [ -e "$DST" ] || [ -L "$DST" ]; then
    backup="$DST.bak.$(date +%Y%m%d%H%M%S)"
    mv "$DST" "$backup"
    echo "==> 已有安装，备份为 $(basename "$backup")"
fi

if [ "$LINK" = "yes" ]; then
    ln -s "$SRC_DIR" "$DST"
    echo "==> 已创建符号链接"
else
    mkdir -p "$DST"
    # 用 tar 而非 cp -r，跨平台行为更一致
    (cd "$SRC_DIR" && tar cf - --exclude='.git' --exclude='*.bak' .) \
        | (cd "$DST" && tar xf -)
    chmod +x "$DST"/scripts/*.sh 2>/dev/null || true
    echo "==> 已复制"
fi

echo
echo "已安装："
find "$DST/" -type f 2>/dev/null | sed "s|$DST/|    |" | sort

cat <<EOF

完成。下一步：

  1. 配置到集群的连接：
       $DST/scripts/setup-ssh.sh <私钥文件>

  2. 新增另一个集群：
       $DST/scripts/probe-cluster.sh <ssh别名> <短名> > $DST/clusters/<短名>.conf

  3. Claude Code 里涉及集群的任务会自动加载这个 skill，
     也可以直接调用 /$SKILL_NAME
EOF
