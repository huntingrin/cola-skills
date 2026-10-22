/** Pass this standalone function to a browser's evaluate capability. Read-only. */
export function collectBeanState() {
  const text = document.body.innerText;
  const tables = [...document.querySelectorAll('table')];
  const pendingTable = tables.find(t => t.innerText.includes('待领取京豆数量'));
  const ledgerTable = tables.find(t => t.innerText.includes('京豆变化'));
  const rawBalance = document.querySelector('.my-card-bean-num')?.textContent.trim();
  const balance = rawBalance && /^[\d,]+$/.test(rawBalance)
    ? Number(rawBalance.replaceAll(',', '')) : null;
  const rows = table => table ? [...table.querySelectorAll('tr')]
    .map(tr => [...tr.querySelectorAll('td')].map(td => td.innerText.trim()))
    .filter(cells => cells.length) : [];
  const pending = rows(pendingTable).filter(c => /^\+\s*\d/.test(c[0]))
    .map(c => ({beans: Number(c[0].replace(/[+\s,]/g, '')), expires: c[1],
      orderSuffix: c[2]?.slice(-4)}));
  const ledger = rows(ledgerTable).filter(c => c.length >= 3 && /^[+-]?\d+$/.test(c[2].replace(/[\s,]/g, '')))
    .map(c => ({description: c[0].replace(/\d{15,18}/g, '[order redacted]'),
      time: c[1], change: Number(c[2].replace(/[\s,]/g, ''))}));
  const sign = document.querySelector('#bean-sign-component');
  return {
    observedAt: new Date().toISOString(), site: location.hostname,
    valid: location.hostname === 'bean.jd.com' && balance !== null && Boolean(ledgerTable),
    balance, pending, pendingVisibleTotal: pending.reduce((s, r) => s + r.beans, 0),
    pendingState: pendingTable ? 'table_present' :
      (!text.includes('购物返京豆') && balance !== null && ledgerTable ? 'section_absent' : 'unknown'),
    coverage: 'visible DOM tables only; verify pagination',
    signText: sign?.innerText ?? null,
    signButtonImage: sign?.querySelector('.btn img')?.getAttribute('src') ?? null,
    // Image existence is NOT evidence of whether today's sign-in was completed.
    ledger
  };
}
