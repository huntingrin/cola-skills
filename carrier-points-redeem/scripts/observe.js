() => {
  // Read visible text only. Never touch input values, cookies, storage or requests.
  const mask = (value) => String(value || "").replace(
    /(^|[^\d])(?:\+?86[ -]?)?(1[3-9]\d(?:[ -]?\d){8})(?!\d)/g,
    (_, prefix, phone) => {
      const digits = phone.replace(/[ -]/g, "");
      return prefix + digits.slice(0, 3) + "****" + digits.slice(-4);
    }
  );
  const clean = (value) => mask(value).replace(/[\t \u00a0]+/g, " ").trim();
  const secret = /验证码|密码|cookie|token|payflag|authorization|goback/i;
  const raw = document.body ? document.body.innerText || "" : "";
  const lines = raw.split(/\r?\n/).map(clean).filter((line) => line && !secret.test(line));
  const collect = (pattern, limit) => [...new Set(
    lines.filter((line) => pattern.test(line)).map((line) => line.slice(0, 180))
  )].slice(0, limit);
  const controls = [...document.querySelectorAll(
    "button,a,[role=button],input[type=submit],input[type=button]"
  )];
  return {
    page: clean(location.origin + location.pathname).slice(0, 240),
    signals: {
      login: /登录|忘记密码/.test(raw),
      verification: /短信验证|验证码|获取短信/.test(raw),
      checkout: /收银台|确认支付|本单支付|待支付/.test(raw),
      result: /兑换成功|支付成功|充值成功|订单已完成|处理中/.test(raw),
    },
    accounts: [...new Set(lines.join("\n").match(/1[3-9]\d\*{4}\d{4}/g) || [])].slice(0, 4),
    pointLines: collect(/积分|AI\s*豆|余额/, 12),
    amountLines: collect(/\d\s*元|现金|实付|补款/, 12),
    orderLines: collect(/订单|单号|流水|处理中|兑换成功|支付成功|充值成功/, 8),
    ruleLines: collect(/仅限|本机|不退|不可退|有效期|续订|到期|当月|直充|返还|抵用/, 12),
    buttons: [...new Set(controls
      .filter((element) => element.getClientRects().length > 0)
      .map((element) => clean(element.innerText || element.getAttribute("aria-label")))
      .filter((label) => label && label.length <= 30 && !secret.test(label))
    )].slice(0, 25),
  };
}
