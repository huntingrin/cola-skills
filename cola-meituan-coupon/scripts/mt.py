#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Cola 美团领券：一个脚本、只用标准库，每条命令直接打印要发给用户的话。

  claim                  领今天的券（没登录时打印要手机号的话术）
  sms PHONE              发验证码（发手机号即视为同意协议）
  login PHONE CODE       验证码登录，成功后直接领券
  history [DATES]        查领券记录，DATES=YYYYMMDD[,YYYYMMDD] / today / yesterday，默认今天
  logout                 退出登录

接口、登录存储、领券记录与美团开放平台官方技能 meituan-coupon v1.0.10 一致
（~/.xiaomei-workspace/skills_local_cache），两边共用一个登录。
"""
import datetime as dt
import hashlib
import json
import os
import random
import re
import ssl
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BASE_URL = "https://peppermall.meituan.com"
AUTH_KEY = "meituan-c-user-auth"
TASK_TYPE = "coupon"
CONFIG = json.loads((Path(__file__).with_name("config.json")).read_text(encoding="utf-8"))
BJ = dt.timezone(dt.timedelta(hours=8))

RULES = (
    "发手机号即表示同意美团[《领券服务规则》](https://open-pepper.meituan.com/eds/rules/meituan-coupon-skill-service-rule.html)、"
    "[《用户协议》](https://rules-center.meituan.com/rule-detail/4/1)和[《隐私政策》](https://rules-center.meituan.com/m/detail/guize/2)。"
)
ASK_PHONE = (
    "好，今天的美团外卖券加上买菜、闪购的券，一共 ¥100 多。告诉我你美团绑的手机号，我帮你领到账户里，只需要验证一次。\n\n" + RULES
)
ASK_PHONE_EXPIRED = "美团登录过期了，发我一下你美团绑的手机号，重新验证一次就好。"
TRY_LATER = "美团那边有点问题，没领上，过一会儿跟我说「领券」再试一次。"


# ── 本地存储（与 skill_cache_cli.py 的目录结构一致）────────────────────

def _workspace() -> Path:
    for k in ("SKILL_CACHE_WORKSPACE", "AGENT_WORKSPACE", "CLAUDE_WORKSPACE", "XIAOMEI_WORKSPACE"):
        if os.environ.get(k):
            return Path(os.environ[k]).expanduser()
    home = Path.home()
    ws = home / ".xiaomei-workspace"
    if not ws.exists() and (home / ".openclaw" / "workspace").is_dir():
        return home / ".openclaw" / "workspace"
    return ws


CACHE = _workspace() / "skills_local_cache"
AUTH_FILE = CACHE / ".shared" / "mt_auth_tokens.json"
DATA_DIR = CACHE / "meituan-coupon" / "data"
HISTORY_FILE = DATA_DIR / "mt_ods_coupon_history.json"
PHONE_HISTORY_FILE = DATA_DIR / "mt_ods_coupon_phone_history.json"


def _read(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8")) or {}
    except Exception:
        return {}


def _write(path: Path, data: dict, private=False):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    if private:
        try:
            os.chmod(tmp, 0o600)
        except OSError:
            pass
    os.replace(tmp, path)


def load_auth() -> dict:
    data = _read(AUTH_FILE)
    entry = data.get(AUTH_KEY) or {}
    if entry.get("user_token") or entry.get("device_token"):
        return entry
    # 旧版小美 / OpenClaw 的登录文件，找到就搬过来
    home = Path.home()
    for p in (os.environ.get("XIAOMEI_AUTH_FILE"), home / ".xiaomei-workspace" / "mt_auth_tokens.json",
              home / ".xiaomei-workspace" / "auth_tokens.json", home / ".openclaw" / "workspace" / "auth_tokens.json"):
        if not p:
            continue
        legacy = _read(Path(p))
        e = legacy.get(AUTH_KEY) or {}
        if e.get("user_token") or e.get("device_token"):
            _write(AUTH_FILE, legacy, private=True)
            return e
    return entry


def save_auth(entry: dict):
    data = _read(AUTH_FILE)
    data[AUTH_KEY] = entry
    _write(AUTH_FILE, data, private=True)


def mask(phone: str) -> str:
    return phone[:3] + "****" + phone[-4:]


def device_token(entry: dict, seed: str) -> str:
    if not entry.get("device_token"):
        raw = f"{seed}{int(time.time() * 1000)}{random.randint(0, 1000)}"
        entry["device_token"] = hashlib.md5(raw.encode()).hexdigest()
    return entry["device_token"]


# ── 网络 ──────────────────────────────────────────────────────────────

def _ssl_context():
    ctx = ssl.create_default_context()
    if ctx.cert_store_stats().get("x509_ca"):
        return ctx
    # 独立版 Python 找不到系统证书时，依次试 certifi 和系统自带的证书包
    try:
        import certifi
        ctx.load_verify_locations(certifi.where())
        return ctx
    except Exception:
        pass
    for f in ("/etc/ssl/cert.pem", "/etc/ssl/certs/ca-certificates.crt", "/etc/pki/tls/certs/ca-bundle.crt"):
        if os.path.exists(f):
            ctx.load_verify_locations(f)
            break
    return ctx


class NetError(Exception):
    pass


def post(path: str, body=None, params=None, timeout=15) -> dict:
    url = BASE_URL + path
    if params:
        url += "?" + urllib.parse.urlencode(params)
    data = json.dumps(body).encode() if body is not None else b""
    req = urllib.request.Request(url, data=data, method="POST", headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=_ssl_context()) as r:
            return json.loads(r.read().decode("utf-8"))
    except Exception as e:
        raise NetError(str(e))



# ── 券表格和话术 ──────────────────────────────────────────────────────

# 每类券的文案和链接（要改文案、换链接，只改这里）
# 分组：几类合成一行说；用途：这类券拿去干嘛；链接：「去使用」跳哪（None = 用券自带的链接）；
# 多领：结尾「还想多领」那句怎么说（None = 这类不推）
PROMO = "http://dpurl.cn/CFuhm7Dz"   # 美团红包天天领（Cola 推广位）
CONF = {
    "美团外卖":  {"分组": "外卖券",     "用途": "点外卖很划算",     "链接": PROMO, "多领": "外卖券"},
    "买菜·超市": {"分组": "买菜超市",   "用途": "买菜、买水果能用", "链接": PROMO, "多领": "买菜券"},
    "美团闪购":  {"分组": "闪购",       "用途": "买日用品、零食能用", "链接": PROMO, "多领": "闪购券"},
    "酒店":      {"分组": "酒店",       "用途": "出门住酒店用",     "链接": None,  "多领": None},
    "境外酒店":  {"分组": "境外酒店",   "用途": "出国住酒店用",     "链接": None,  "多领": None},
    "机票":      {"分组": "机票火车票", "用途": "出门买票用",       "链接": None,  "多领": None},
    "火车票":    {"分组": "机票火车票", "用途": "出门买票用",       "链接": None,  "多领": None},
}
ORDER = list(CONF)


def today() -> dt.date:
    return dt.datetime.now(BJ).date()


def kind(name):
    if "外卖" in name: return "美团外卖"
    if "商超" in name or "果蔬" in name or "买菜" in name: return "买菜·超市"
    if "闪购" in name: return "美团闪购"
    if "境外酒店" in name: return "境外酒店"
    if "酒店" in name or "民宿" in name: return "酒店"
    if "机票" in name: return "机票"
    if "火车" in name: return "火车票"
    return re.sub(r"-?养虾专(属|享)券", "", name) or name


def num(x):
    try:
        v = float(x); return int(v) if v == int(v) else v
    except Exception:
        return x


def amount(c):
    try:
        return float(c.get("discount_amount") or 0)
    except Exception:
        return 0.0


def threshold(c):
    m = re.search(r"满(\d+(?:\.\d+)?)", c.get("use_condition") or "")
    return m.group(1) if m else None


def cond(c):
    t = threshold(c)
    return f"满 {t}" if t else ("无门槛" if "无门槛" in (c.get("use_condition") or "") else (c.get("use_condition") or ""))


def expire(end):
    try:
        d = dt.date.fromisoformat((end or "")[:10])
    except Exception:
        return end or ""
    if d == today(): return "**今天过期**"
    if d == today() + dt.timedelta(days=1): return "**明天过期**"
    return f"{d.month:02d}-{d.day:02d}"


def order_of(c):
    k = kind(c["name"])
    return ORDER.index(k) if k in ORDER else 99


def table(coupons):
    out = ["| 用在哪 | 减多少 | 门槛 | 有效期到 | |", "|---|---|---|---|---|"]
    for c in sorted(coupons, key=lambda c: (order_of(c), -amount(c))):
        k = kind(c["name"]); a = num(c.get("discount_amount"))
        a = f"**¥{a}**" if k == "美团外卖" else f"¥{a}"
        url = CONF.get(k, {}).get("链接") or c.get("jump_url")
        out.append(f"| {k} | {a} | {cond(c)} | {expire(c.get('valid_end'))} | {f'[去使用]({url})' if url else ''} |")
    return "\n".join(out)


def guide(coupons):
    """按品类说一句：最大那张 + 拿去干嘛。"""
    groups = {}
    for c in coupons:
        cf = CONF.get(kind(c["name"]), {})
        g = groups.setdefault(cf.get("分组", kind(c["name"])), {"use": cf.get("用途", ""), "cs": [], "o": order_of(c)})
        g["cs"].append(c)
    lines = []
    for name, g in sorted(groups.items(), key=lambda x: x[1]["o"]):
        b = max(g["cs"], key=amount)
        top = ("最高" if len(g["cs"]) > 1 else "") + f"{cond(b).replace(' ', '')}减{num(b['discount_amount'])}"
        lines.append(f"• **{name}**：{top}，{g['use']}" if g["use"] else f"• **{name}**：{top}")
    return "这次的券这么用：\n" + "\n".join(lines)


def more(coupons):
    """结尾「还想多领」：只推这次真领到的品类，同一条链接的合成一句。"""
    by_link = {}
    kinds = {kind(c["name"]) for c in coupons}
    for k in ORDER:
        cf = CONF[k]
        if cf["多领"] and cf["链接"] and k in kinds:
            names = by_link.setdefault(cf["链接"], [])
            if cf["多领"] not in names: names.append(cf["多领"])
    if not by_link: return ""
    lines = [f"[再领一波{'、'.join(n)} 👉]({u})" for u, n in by_link.items()]
    return "\n\n还想多领？" + "\n".join(lines)


def tail(coupons):
    soon = [expire(c.get("valid_end")) for c in coupons]
    soon = [s for s in soon if "过期" in s]
    s = "券都在美团 App「我的 → 红包卡券」里"
    if soon:
        s += f"，有 {len(soon)} 张{'今天' if any('今天' in x for x in soon) else '明天'}就过期，抓紧用！"
    else:
        s += "。"
    return s + more(coupons)


def body(coupons):
    return table(coupons) + "\n\n" + guide(coupons) + "\n\n" + tail(coupons)


def format_coupon(e: dict) -> dict:
    lim = e.get("priceLimitAmountYuanStr", "")
    t = e.get("priceLimitType", 1)
    use = "无门槛" if t == 1 else (f"满{lim}元可用" if lim else "-")
    url = e.get("jumpUrl", "")
    if CONFIG.get("lch") and url:
        url += ("&" if "?" in url else "?") + "lch=" + CONFIG["lch"]
    end = e.get("endTime")
    return {
        "name": e.get("userEquityName", "-"),
        "discount_amount": e.get("discountAmountYuanStr", ""),
        "use_condition": use,
        "valid_end": dt.datetime.fromtimestamp(end / 1000, BJ).strftime("%Y-%m-%d") if end else "",
        "jump_url": url,
    }


# ── 命令 ──────────────────────────────────────────────────────────────

def logged_in():
    """返回 (entry, 提示语)。提示语非空说明要先登录。"""
    entry = load_auth()
    token = entry.get("user_token")
    if not token or not entry.get("terms_accepted"):
        return entry, (ASK_PHONE_EXPIRED if entry.get("authed_at") and entry.get("terms_accepted") else ASK_PHONE)
    try:
        code = post("/eds/claw/login/token/verify", params={"token": token}, timeout=10).get("code")
    except NetError:
        return entry, "网络不太好，没连上美团，过一会儿跟我说「领券」再试一次。"
    if code == 20005:
        entry["user_token"] = ""
        save_auth(entry)
        return entry, ASK_PHONE_EXPIRED
    if code != 0:
        return entry, TRY_LATER
    return entry, ""


def cmd_claim():
    entry, msg = logged_in()
    if msg:
        return print(("今天的券还没领上，" if msg == ASK_PHONE_EXPIRED else "") + msg)
    token, phone_masked = entry["user_token"], entry.get("phone_masked", "")
    sub = CONFIG["subChannelCode"]
    day = today().strftime("%Y%m%d")

    history, phone_history = _read(HISTORY_FILE), _read(PHONE_HISTORY_FILE)
    codes = history.get(sub, {}).get(token, {}).get(day, {}).get(TASK_TYPE, []) or (
        phone_history.get(sub, {}).get(phone_masked, {}).get(day, {}).get(TASK_TYPE, []) if phone_masked else [])
    first = not codes
    redeem = codes[-1] if codes else hashlib.md5(f"{token}_{phone_masked}_{day}".encode()).hexdigest()

    try:
        r = post("/eds/standard/equity/pkg/issue/claw",
                 {"subChannelCode": sub, "token": token, "equityPkgRedeemCode": redeem})
    except NetError:
        return print("网络不太好，没领上，过一会儿跟我说「领券」再试一次。")
    code = r.get("code")
    if code == 4010:
        return print("今天的券已经领过了，每天只能领一次，明天再领新的。")
    if code == 4009:
        return print("今天的领券活动结束了，明天再来领。")
    if code == 4011:
        return print("今天的券被领完了，明天早点来领。")
    if code != 0:
        return print(TRY_LATER)

    if first:
        for store, key in ((history, token), (phone_history, phone_masked)):
            if key:
                lst = store.setdefault(sub, {}).setdefault(key, {}).setdefault(day, {}).setdefault(TASK_TYPE, [])
                if redeem not in lst: lst.append(redeem)
        _write(HISTORY_FILE, history)
        if phone_masked:
            _write(PHONE_HISTORY_FILE, phone_history)

    cs = [format_coupon(e) for e in (r.get("data") or {}).get("successEquityList") or []]
    if not cs:
        return print("今天的券已经领过了，每天只能领一次，明天再领新的。" if not first else TRY_LATER)
    total = num(sum(amount(c) for c in cs))
    if first:
        print(f"领好了 🎉 {len(cs)} 张券一共 **¥{total}**，已经放进你的美团账户。\n\n" + body(cs))
    else:
        print("今天的券已经领过了，每天只能领一次。你今天的券：\n\n" + body(cs) + "\n\n明天再领新的。")


def check_phone(phone: str) -> str:
    if not (phone.isdigit() and len(phone) == 11):
        return "这个手机号好像不对，位数不够。再发我一下你美团绑的 11 位手机号？"
    if not re.match(r"1[3-9]", phone):
        return "这个号码好像不是真的手机号，再确认一下？发我你美团绑的那个手机号就行。"
    return ""


def send_sms(phone: str) -> str:
    entry = load_auth()
    entry["terms_accepted"] = True
    uuid = device_token(entry, phone)
    entry.setdefault("phone_masked", mask(phone))
    save_auth(entry)
    try:
        r = post("/eds/claw/login/sms/code/get", {"mobile": phone, "uuid": uuid}, timeout=10)
    except NetError:
        return "网络不太好，验证码没发出去，稍后再试一次。"
    code = r.get("code")
    if code == 0:
        return f"验证码已发到 {mask(phone)}，请查收短信，把 6 位验证码发我。"
    if code == 20010:
        link = (r.get("data") or {}).get("redirectUrl")
        return (f"美团要先做一次安全验证，点这个链接完成，完成后会自动给你发验证码：{link}"
                if link else "美团要先做一次安全验证，稍后再试一次。")
    return {
        20002: "验证码刚发过，等 1 分钟再试。",
        20004: "这个手机号还没注册美团，先在美团 App 注册一下再来。",
        20006: "这个号今天验证码发太多次了，明天再试。",
        20007: "这个号今天验证码发太多次了，明天再试。",
    }.get(code, "验证码没发出去，稍后再试一次。")


def cmd_sms(phone: str):
    print(check_phone(phone) or send_sms(phone))


def cmd_login(phone: str, sms_code: str):
    bad = check_phone(phone)
    if bad:
        return print(bad)
    if not (sms_code.isdigit() and 4 <= len(sms_code) <= 6):
        return print("验证码是短信里的 6 位数字，再发我一下？")
    entry = load_auth()
    uuid = device_token(entry, phone)
    try:
        r = post("/eds/claw/login/sms/code/verify", {"mobile": phone, "smsVerifyCode": sms_code, "uuid": uuid}, timeout=10)
    except NetError:
        return print("网络不太好，没验证上，把验证码再发我一次试试。")
    code = r.get("code")
    token = (r.get("data") or {}).get("token")
    if code == 0 and token:
        entry.update(user_token=token, phone_masked=mask(phone), authed_at=int(time.time()), terms_accepted=True)
        save_auth(entry)
        return cmd_claim()
    if code == 20003:
        resent = send_sms(phone)
        if resent.startswith("验证码已发到"):
            return print(f"验证码不对或过期了，我重新发了一条到 {mask(phone)}，请查收后把新的验证码发我。")
        return print("验证码不对或过期了。" + resent)
    if code == 20004:
        return print("这个手机号还没注册美团，先在美团 App 注册一下再来。")
    print("验证没通过，稍后再试一次。")


def parse_dates(arg: str):
    arg = (arg or "today").strip().lower()
    if arg in ("today", "今天"):
        return [today()]
    if arg in ("yesterday", "昨天"):
        return [today() - dt.timedelta(days=1)]
    parts = [dt.datetime.strptime(p.strip().replace("-", ""), "%Y%m%d").date() for p in arg.split(",")[:2]]
    start, end = min(parts), max(parts)
    return [start + dt.timedelta(days=i) for i in range((end - start).days + 1)]


def cmd_history(arg: str):
    try:
        days = [d.strftime("%Y%m%d") for d in parse_dates(arg)]
    except ValueError:
        return print("日期格式不对，用 YYYYMMDD 或 YYYYMMDD,YYYYMMDD。")
    entry, msg = logged_in()
    if msg:
        return print(msg)
    sub, token, pm = CONFIG["subChannelCode"], entry["user_token"], entry.get("phone_masked", "")
    codes = []
    for store, key in ((_read(HISTORY_FILE), token), (_read(PHONE_HISTORY_FILE), pm)):
        if key and not codes:
            data = store.get(sub, {}).get(key, {})
            codes = [c for d in days for c in data.get(d, {}).get(TASK_TYPE, [])]
    codes = list(dict.fromkeys(codes))
    none = "那几天没有领券记录，要现在帮你领吗？"
    if not codes:
        return print(none)
    try:
        r = post("/eds/standard/equity/pkg/claw/result/query",
                 {"subChannelCode": sub, "token": token, "equityPkgRedeemCodeList": codes})
    except NetError:
        return print("网络不太好，没查到，稍后再试一次。")
    if r.get("code") != 0:
        return print("美团那边有点问题，没查到，稍后再试一次。")
    cs = [format_coupon(e) for item in (r.get("data") or []) for e in item.get("successEquityList") or []]
    if not cs:
        return print(none)
    total = num(sum(amount(c) for c in cs))
    print(f"一共 {len(cs)} 张券，合计 **¥{total}**：\n\n" + table(cs))


def cmd_logout():
    entry = load_auth()
    entry["user_token"] = ""
    entry.pop("authed_at", None)
    save_auth(entry)
    print("已退出，下次领券要重新验证一次。")


def main(argv):
    cmd, args = (argv[0] if argv else "claim"), argv[1:]
    digits = [re.sub(r"\D", "", a) for a in args]
    if cmd == "claim":
        cmd_claim()
    elif cmd == "sms" and digits:
        cmd_sms(digits[0])
    elif cmd == "login" and len(digits) >= 2:
        cmd_login(digits[0], digits[1])
    elif cmd == "history":
        cmd_history(args[0] if args else "")
    elif cmd == "logout":
        cmd_logout()
    else:
        print(__doc__)
        sys.exit(2)


if __name__ == "__main__":
    main(sys.argv[1:])
