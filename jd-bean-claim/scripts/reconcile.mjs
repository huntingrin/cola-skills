// Pure reconciliation. Does not operate a browser or submit claims.
const key = row => JSON.stringify([row.description, row.time, Number(row.change)]);
function jdTime(value) {
  return typeof value === 'string' && /^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$/.test(value)
    ? Date.parse(value.replace(' ', 'T') + '+08:00') : NaN;
}
export function reconcile(before, after, {action, expectedBeans, startedAt, endedAt} = {}) {
  const counts = new Map();
  for (const row of before.ledger ?? []) counts.set(key(row), (counts.get(key(row)) ?? 0) + 1);
  const added = (after.ledger ?? []).filter(row => {
    const k = key(row), n = counts.get(k) ?? 0;
    if (n > 0) { counts.set(k, n - 1); return false; }
    return true;
  });
  const start = Date.parse(startedAt), end = Date.parse(endedAt);
  const type = action === 'shopping' ? /购物.*京豆/ : action === 'signin' ? /签到|活动奖励京豆/ : null;
  const candidates = added.filter(row => type?.test(row.description) && Number(row.change) > 0 &&
    jdTime(row.time) >= Math.floor(start / 1000) * 1000 && jdTime(row.time) <= end);
  const ledgerBeans = candidates.reduce((s, r) => s + Number(r.change), 0);
  const balanceDelta = Number.isFinite(before.balance) && Number.isFinite(after.balance)
    ? after.balance - before.balance : null;
  const verified = Boolean(before.valid && after.valid && type && Number.isFinite(start) &&
    Number.isFinite(end) && end >= start && Number.isInteger(expectedBeans) && expectedBeans > 0 &&
    ledgerBeans === expectedBeans && balanceDelta === expectedBeans);
  return {status: verified ? 'verified' : 'needs_review', action,
    creditedBeans: verified ? ledgerBeans : null, ledgerBeans, balanceDelta, candidates,
    note: 'Check action context and ledger coverage; generic activity rows alone do not prove sign-in attribution.'};
}
