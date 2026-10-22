#!/usr/bin/env python3
"""把 issue.py 的返回整理成 Cola 的固定话术 + 券表格。
用法：python3 issue.py --auto | python3 format_result.py [--cron-on]
--cron-on：用户已开启每日自动领券（不再追问定时；用于 8 点推送话术）
输出：可直接发给用户的 Markdown 文本。
"""
import sys, json, re, datetime

try:
    from zoneinfo import ZoneInfo
    TODAY = datetime.datetime.now(ZoneInfo("Asia/Shanghai")).date()
except Exception:
    TODAY = (datetime.datetime.utcnow() + datetime.timedelta(hours=8)).date()

# Cola 自己的美团推广链接（红包天天领）：外卖/买菜/闪购的「去使用」都走这里，下单才算 Cola 的
PROMO = "http://dpurl.cn/CFuhm7Dz"
PROMO_KINDS = ("美团外卖", "买菜·超市", "美团闪购")

ORDER = ["美团外卖", "买菜·超市", "美团闪购", "酒店", "境外酒店", "机票", "火车票"]


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


def cond(c):
    m = re.search(r"满(\d+(?:\.\d+)?)", c or "")
    return f"满 {m.group(1)}" if m else ("无门槛" if "无门槛" in (c or "") else (c or ""))


def expire(end):
    try:
        d = datetime.date.fromisoformat(end[:10])
    except Exception:
        return end or ""
    if d == TODAY: return "**今天过期**"
    if d == TODAY + datetime.timedelta(days=1): return "**明天过期**"
    return f"{d.month:02d}-{d.day:02d}"


def table(coupons):
    rows = sorted(coupons, key=lambda c: (ORDER.index(kind(c["name"])) if kind(c["name"]) in ORDER else 99, -float(c.get("discount_amount") or 0)))
    out = ["| 用在哪 | 减多少 | 门槛 | 有效期到 | |", "|---|---|---|---|---|"]
    for c in rows:
        k = kind(c["name"]); amt = num(c.get("discount_amount"))
        a = f"**¥{amt}**" if k == "美团外卖" else f"¥{amt}"
        url = PROMO if k in PROMO_KINDS else c.get("jump_url")
        link = f"[去使用]({url})" if url else ""
        out.append(f"| {k} | {a} | {cond(c.get('use_condition'))} | {expire(c.get('valid_end', ''))} | {link} |")
    return "\n".join(out)


# 每类券「拿去干嘛」：(分组名, 用途)
USE = {
    "美团外卖": ("外卖券", "点外卖很划算"),
    "买菜·超市": ("买菜超市", "买菜、买水果能用"),
    "美团闪购": ("闪购", "买日用品、零食能用"),
    "酒店": ("酒店", "出门住酒店用"),
    "境外酒店": ("境外酒店", "出国住酒店用"),
    "机票": ("机票火车票", "出门买票用"),
    "火车票": ("机票火车票", "出门买票用"),
}


def guide(coupons):
    """按品类说一句：最大那张 + 拿去干嘛。"""
    groups = {}
    for c in coupons:
        k = kind(c["name"]); g, use = USE.get(k, (k, ""))
        groups.setdefault(g, {"use": use, "cs": [], "o": ORDER.index(k) if k in ORDER else 99})["cs"].append(c)
    lines = []
    for g, v in sorted(groups.items(), key=lambda x: x[1]["o"]):
        b = max(v["cs"], key=lambda c: float(c.get("discount_amount") or 0))
        top = ("最高" if len(v["cs"]) > 1 else "") + f"{cond(b.get('use_condition')).replace(' ', '')}减{num(b['discount_amount'])}"
        lines.append(f"• **{g}**：{top}，{v['use']}" if v["use"] else f"• **{g}**：{top}")
    return "这次的券这么用：\n" + "\n".join(lines)


def soon_n(coupons):
    soon = [c for c in coupons if "过期" in expire(c.get("valid_end", ""))]
    when = "今天" if any("今天" in expire(c.get("valid_end", "")) for c in soon) else "明天"
    return len(soon), when


def tail(coupons):
    n, when = soon_n(coupons)
    s = "券都在美团 App「我的 → 红包卡券」里"
    s += (f"，有 {n} 张{when}就过期，抓紧用！" if n else "。")
    return s + f"\n\n还想多领？这里还有一波外卖、闪购券 👉 [美团红包天天领]({PROMO})"


def best_wm(coupons):
    wm = [c for c in coupons if kind(c["name"]) == "美团外卖"]
    if not wm: return ""
    # 优惠比例最高的那张
    def ratio(c):
        m = re.search(r"满(\d+(?:\.\d+)?)", c.get("use_condition") or "")
        return float(c["discount_amount"]) / float(m.group(1)) if m else 1
    b = max(wm, key=ratio)
    m = re.search(r"满(\d+(?:\.\d+)?)", b.get("use_condition") or "")
    return f"满 {m.group(1) if m else 0} 减 {num(b['discount_amount'])}"


ERR = {
    "ALREADY_RECEIVED": None,  # 走「今天已经领过」
    "ACTIVITY_ENDED": "今天的领券活动结束了，明天再帮你领。",
    "QUOTA_EXHAUSTED": "今天的券被领完了，明天早点帮你抢。",
    "TIMEOUT": "美团那边有点慢，没领上，我过一会儿再帮你试一次。",
    "NETWORK_ERROR": "网络不太好，没领上，我过一会儿再帮你试一次。",
}


def main():
    cron_on = "--cron-on" in sys.argv
    raw = sys.stdin.read().strip().splitlines()
    d = json.loads(raw[-1]) if raw else {}
    if not d.get("success"):
        e = d.get("error", "")
        if e in ("TOKEN_INVALID", "TERMS_NOT_ACCEPTED"):
            print("__NEED_LOGIN__"); return
        if e == "ALREADY_RECEIVED":
            print("今天的券已经领过了，每天只能领一次，明天再帮你领新的。"); return
        print(ERR.get(e) or ("今天的券没领上，美团那边有点问题，我中午再帮你试一次。" if cron_on else "美团那边有点问题，没领上，稍后再帮你试一次。")); return
    cs = d.get("coupons") or []
    total = num(sum(float(c.get("discount_amount") or 0) for c in cs))
    t = table(cs); body = t + "\n\n" + guide(cs) + "\n\n" + tail(cs)
    if not d.get("is_first_issue", True):
        print("今天的券已经领过了，每天只能领一次。你今天的券：\n\n" + body + "\n\n明天再帮你领新的。")
    elif cron_on:
        b = best_wm(cs)
        head = f"早，今天的券领好了：{len(cs)} 张一共 **¥{total}**。" + (f"点外卖用 {b} 那张最划算，中午记得用。" if b else "")
        print(head + "\n\n" + body)
    else:
        print(f"领好了 🎉 {len(cs)} 张券一共 **¥{total}**，已经放进你的美团账户。\n\n" + body)
    if not cron_on:
        print("\n另外，要不要我每天早上 8 点自动帮你领？这样每天的券都不会错过，也不用再验证 😊")


if __name__ == "__main__":
    main()
