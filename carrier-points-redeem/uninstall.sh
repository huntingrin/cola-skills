#!/usr/bin/env bash
set -euo pipefail

SKILL_NAME="carrier-points-redeem"
TARGET=""

usage() {
  cat <<'EOF'
用法:
  ./uninstall.sh                    从检测到的宿主中卸载
  ./uninstall.sh --target codex     从 ~/.codex/skills 卸载
  ./uninstall.sh --target cola      从 ~/.cola/skills 卸载
  ./uninstall.sh --target claude    从 ~/.claude/skills 卸载
  ./uninstall.sh --target DIR       从指定 skills 目录卸载
  ./uninstall.sh --target all       从所有检测到的宿主卸载
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

remove_from() {
  local root="$1"
  local dest="$root/$SKILL_NAME"
  if [ -e "$dest" ] || [ -L "$dest" ]; then
    rm -rf "$dest"
    echo "已卸载: $dest"
  else
    echo "未安装: $dest"
  fi
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
  remove_from "$(resolve_target "$TARGET")"
else
  while IFS= read -r root; do
    remove_from "$root"
  done < <(detect_hosts)
fi
