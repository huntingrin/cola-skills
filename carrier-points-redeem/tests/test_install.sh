#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TMP="$(mktemp -d "${TMPDIR:-/tmp}/carrier-points-redeem-test.XXXXXX")"
trap 'rm -rf "$TMP"' EXIT

fail() {
  echo "FAIL: $*" >&2
  exit 1
}

assert_file() {
  [ -f "$1" ] || fail "缺少文件: $1"
}

echo "1. 首次安装"
bash "$ROOT/install.sh" --target "$TMP/skills" >/dev/null
DEST="$TMP/skills/carrier-points-redeem"
assert_file "$DEST/SKILL.md"
assert_file "$DEST/skills/cmcc-points-redeem/GUIDE.md"
assert_file "$DEST/skills/cucc-points-redeem/GUIDE.md"
assert_file "$DEST/skills/ct-points-redeem/GUIDE.md"
[ ! -e "$DEST/skills/cmcc-points-redeem/SKILL.md" ] || fail "子技能不应暴露 SKILL.md"
[ ! -e "$DEST/skills/cucc-points-redeem/SKILL.md" ] || fail "子技能不应暴露 SKILL.md"
[ ! -e "$DEST/skills/ct-points-redeem/SKILL.md" ] || fail "子技能不应暴露 SKILL.md"
assert_file "$DEST/skills/ct-points-redeem/scripts/transaction_state.py"
assert_file "$DEST/skills/cucc-points-redeem/references/browser-flow.md"
assert_file "$DEST/references/observe.md"
assert_file "$DEST/references/browser.md"
assert_file "$DEST/scripts/observe.js"
assert_file "$DEST/tests/test_observe.cjs"
assert_file "$DEST/tests/test_skill_contract.py"
[ ! -d "$DEST/.git" ] || fail "不应包含 .git"

echo "2. 重复安装会整体替换"
touch "$DEST/stale-file"
bash "$ROOT/install.sh" --target "$TMP/skills" >/dev/null
[ ! -e "$DEST/stale-file" ] || fail "旧文件未被清理"
assert_file "$DEST/SKILL.md"

echo "3. 运行文件完整复制且内容一致"
for name in SKILL.md references/browser.md references/observe.md scripts/observe.js \
  skills/cmcc-points-redeem/GUIDE.md skills/cucc-points-redeem/GUIDE.md \
  skills/ct-points-redeem/GUIDE.md; do
  cmp "$ROOT/$name" "$DEST/$name" || fail "安装文件与源码不同: $name"
done

echo "4. 归档旧独立版本（可选开关）"
mkdir -p "$TMP/skills/cmcc-points-redeem" "$TMP/skills/ct-points-redeem"
touch "$TMP/skills/cmcc-points-redeem/marker"
bash "$ROOT/install.sh" --target "$TMP/skills" --archive-standalone >/dev/null
[ ! -e "$TMP/skills/cmcc-points-redeem" ] || fail "旧独立版本未归档"
[ ! -e "$TMP/skills/ct-points-redeem" ] || fail "旧独立版本未归档"
ARCHIVED="$(find "$TMP/skills" -path '*/.carrier-points-redeem-archive-*/cmcc-points-redeem/marker' -print -quit)"
[ -n "$ARCHIVED" ] || fail "归档目录中缺少 marker"
assert_file "$DEST/SKILL.md"

echo "5. 卸载"
bash "$ROOT/uninstall.sh" --target "$TMP/skills" >/dev/null
[ ! -e "$DEST" ] || fail "卸载后目录仍存在"

echo "6. Cola 资源源目录预装（路径含空格）"
COLA_RESOURCE_SKILLS="$TMP/Cola Project/apps/agent-runtime/resources/skills"
bash "$ROOT/install.sh" --target "$COLA_RESOURCE_SKILLS" >/dev/null
BUNDLED="$COLA_RESOURCE_SKILLS/carrier-points-redeem"
assert_file "$BUNDLED/SKILL.md"
assert_file "$BUNDLED/scripts/observe.js"
cmp "$ROOT/scripts/observe.js" "$BUNDLED/scripts/observe.js" || fail "摘要函数未完整打包"
python3 -m unittest discover -s "$BUNDLED/tests" -p 'test_skill_contract.py' >/dev/null
node --test "$BUNDLED/tests/test_observe.cjs"
bash "$BUNDLED/uninstall.sh" --target "$COLA_RESOURCE_SKILLS" >/dev/null
[ ! -e "$BUNDLED" ] || fail "预装目录卸载失败"

echo "PASS"
