#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_NAME="carrier-points-redeem"
TARGET=""
ARCHIVE_STANDALONE=0

usage() {
  cat <<'EOF'
用法:
  ./install.sh                    自动检测 Codex / Cola / Claude 并静默安装
  ./install.sh --target codex     安装到 ~/.codex/skills
  ./install.sh --target cola      安装到 ~/.cola/skills
  ./install.sh --target claude    安装到 ~/.claude/skills
  ./install.sh --target DIR       安装到指定 skills 目录
  ./install.sh --target all       安装到所有检测到的宿主

选项:
  --archive-standalone            把同目录下已安装的移动/联通/电信独立技能
                                  移到 .carrier-points-redeem-archive-* 备份目录
                                  （默认不动，便于回滚）

安装阶段不需要任何交互或配置；重复执行会整体替换旧版本。
EOF
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --target)
      if [ "$#" -lt 2 ]; then
        echo "错误: --target 需要一个值" >&2
        exit 2
      fi
      TARGET="$2"
      shift 2
      ;;
    --archive-standalone)
      ARCHIVE_STANDALONE=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "错误: 未知参数 $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

resolve_target() {
  case "$1" in
    codex)  printf '%s\n' "$HOME/.codex/skills" ;;
    cola)   printf '%s\n' "$HOME/.cola/skills" ;;
    claude) printf '%s\n' "$HOME/.claude/skills" ;;
    *)      printf '%s\n' "$1" ;;
  esac
}

copy_bundle() {
  local dest="$1"
  cp -R \
    "$SCRIPT_DIR/SKILL.md" \
    "$SCRIPT_DIR/README.md" \
    "$SCRIPT_DIR/THIRD_PARTY.md" \
    "$SCRIPT_DIR/LICENSE" \
    "$SCRIPT_DIR/agents" \
    "$SCRIPT_DIR/references" \
    "$SCRIPT_DIR/scripts" \
    "$SCRIPT_DIR/skills" \
    "$SCRIPT_DIR/tests" \
    "$SCRIPT_DIR/install.sh" \
    "$SCRIPT_DIR/uninstall.sh" \
    "$dest/"
}

install_to() {
  local root="$1"
  local dest="$root/$SKILL_NAME"
  local tmp="$root/.${SKILL_NAME}.tmp.$$"
  local backup="$root/.${SKILL_NAME}.bak.$$"

  mkdir -p "$root"
  rm -rf "$tmp"
  mkdir -p "$tmp"
  copy_bundle "$tmp"
  find "$tmp" -type d -name __pycache__ -prune -exec rm -rf {} +
  find "$tmp" -type f -name '*.pyc' -exec rm -f {} +
  chmod +x "$tmp/install.sh" "$tmp/uninstall.sh" "$tmp/tests/test_install.sh"

  if [ -e "$dest" ] || [ -L "$dest" ]; then
    rm -rf "$backup"
    mv "$dest" "$backup"
  fi

  if ! mv "$tmp" "$dest"; then
    echo "错误: 安装到 $dest 失败" >&2
    if [ -e "$backup" ] || [ -L "$backup" ]; then
      mv "$backup" "$dest"
    fi
    exit 1
  fi

  rm -rf "$backup"

  if [ "$ARCHIVE_STANDALONE" -eq 1 ]; then
    local archive="$root/.carrier-points-redeem-archive-$(date +%Y%m%d%H%M%S)-$$"
    local name
    for name in cmcc-points-redeem cucc-points-redeem ct-points-redeem; do
      if [ -e "$root/$name" ] || [ -L "$root/$name" ]; then
        mkdir -p "$archive"
        mv "$root/$name" "$archive/$name"
        echo "已归档独立版本: $root/$name -> $archive/$name"
      fi
    done
  fi

  echo "已安装: $dest"
}

detect_hosts() {
  local hosts=()
  if [ -d "$HOME/.codex" ] || [ -d "$HOME/.codex/skills" ]; then
    hosts+=("$HOME/.codex/skills")
  fi
  if [ -d "$HOME/.cola" ] || [ -d "$HOME/.cola/skills" ]; then
    hosts+=("$HOME/.cola/skills")
  fi
  if [ -d "$HOME/.claude" ] || [ -d "$HOME/.claude/skills" ]; then
    hosts+=("$HOME/.claude/skills")
  fi
  if [ "${#hosts[@]}" -eq 0 ]; then
    hosts+=("$HOME/.codex/skills")
  fi
  printf '%s\n' "${hosts[@]}"
}

if [ -n "$TARGET" ] && [ "$TARGET" != "all" ]; then
  install_to "$(resolve_target "$TARGET")"
else
  while IFS= read -r root; do
    install_to "$root"
  done < <(detect_hosts)
fi

echo "入口技能: $SKILL_NAME"
echo "使用示例: 帮我兑换积分，移动 13800138000"
