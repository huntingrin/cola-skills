#!/bin/bash
# Cola 美团领券 · 入口（Mac / Linux）：bash run.sh <命令> [参数]
# 找 Python 3.8+（只用标准库）；没有就免密码装一个到 ~/.cola/runtime/python，再执行 mt.py。
set -u
DIR="$(cd "$(dirname "$0")" && pwd)"
RT="$HOME/.cola/runtime/python"
PYV=3.12.7; TAG=20241016
log(){ echo "[setup] $*" >&2; }
ok(){ "$1" -c 'import sys; sys.exit(0 if sys.version_info >= (3,8) else 1)' >/dev/null 2>&1; }

find_py(){
  local cands=("$RT/bin/python3" "$(command -v python3 2>/dev/null)" "$(command -v python 2>/dev/null)")
  for p in "${cands[@]}"; do
    [ -n "$p" ] && [ -x "$p" ] || continue
    # Mac 没装命令行工具时 /usr/bin/python3 只是个壳，一调用就弹安装框，跳过
    if [ "$p" = "/usr/bin/python3" ] && [ "$(uname)" = "Darwin" ] && ! xcode-select -p >/dev/null 2>&1; then continue; fi
    ok "$p" && { echo "$p"; return 0; }
  done
  return 1
}

install_py(){
  case "$(uname)-$(uname -m)" in
    Darwin-arm64) ARCH=aarch64-apple-darwin;;
    Darwin-x86_64) ARCH=x86_64-apple-darwin;;
    Linux-x86_64) ARCH=x86_64-unknown-linux-gnu;;
    Linux-aarch64) ARCH=aarch64-unknown-linux-gnu;;
    *) log "不支持的系统 $(uname)-$(uname -m)"; return 1;;
  esac
  F="cpython-${PYV}+${TAG}-${ARCH}-install_only.tar.gz"
  TMP="$(mktemp -d)"
  for BASE in "https://registry.npmmirror.com/-/binary/python-build-standalone/${TAG}" \
              "https://github.com/astral-sh/python-build-standalone/releases/download/${TAG}"; do
    log "下载 Python ${PYV}：$BASE"
    if curl -fsSL --retry 2 -m 600 -o "$TMP/py.tgz" "$BASE/${F//+/%2B}" && \
       curl -fsSL -m 60 -o "$TMP/py.sha" "$BASE/${F//+/%2B}.sha256"; then
      WANT="$(awk '{print $1}' "$TMP/py.sha")"; GOT="$(shasum -a 256 "$TMP/py.tgz" 2>/dev/null || sha256sum "$TMP/py.tgz")"; GOT="${GOT%% *}"
      if [ "$WANT" = "$GOT" ]; then
        rm -rf "$RT"; mkdir -p "$(dirname "$RT")"
        tar -xzf "$TMP/py.tgz" -C "$TMP" && mv "$TMP/python" "$RT" && rm -rf "$TMP" && return 0
      fi
      log "校验没通过，换下一个源"
    fi
  done
  rm -rf "$TMP"; return 1
}

PY="$(find_py)" || { install_py && PY="$(find_py)"; } || {
  echo "电脑上缺个运行环境，我没装上，你把这段报错截图发给鲁班。"; exit 1; }
exec "$PY" -B "$DIR/mt.py" "$@"
