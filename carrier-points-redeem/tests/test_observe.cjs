const { readFileSync } = require('node:fs');
const { join } = require('node:path');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const { test } = require('node:test');

const source = readFileSync(join(__dirname, '../scripts/observe.js'), 'utf8');
const script = new vm.Script(`(${source})()`);

function forbidden() {
  throw new Error('Sensitive data or mutation was accessed');
}

function button(label, { visible = true, aria = '' } = {}) {
  return {
    innerText: label,
    getAttribute: (name) => name === 'aria-label' ? aria : forbidden(),
    getClientRects: () => visible ? [{}] : [],
    get value() { return forbidden(); },
    click: forbidden,
  };
}

function observe(text, controls = [], pathname = '/jycalls/') {
  const result = script.runInNewContext({
    document: {
      body: text === null ? null : { innerText: text },
      querySelectorAll: () => controls,
      get cookie() { return forbidden(); },
    },
    location: {
      origin: 'https://apps.telefen.com', pathname,
      get search() { return forbidden(); },
      get hash() { return forbidden(); },
      get href() { return forbidden(); },
    },
    get localStorage() { return forbidden(); },
    get sessionStorage() { return forbidden(); },
    fetch: forbidden,
    XMLHttpRequest: forbidden,
  }, { timeout: 1000 });
  return JSON.parse(JSON.stringify(result));
}

test('an unloaded document leaves balances unknown', () => {
  const result = observe(null);
  assert.deepEqual(result.pointLines, []);
  assert.deepEqual(result.amountLines, []);
  assert.deepEqual(result.accounts, []);
  assert.ok(Object.values(result.signals).every((value) => value === false));
});

test('a visible zero and decimal cash remain source text rather than inferred values', () => {
  const result = observe('可用积分：0\n现金：0.00 元\n10元需要1000积分');
  assert.deepEqual(result.pointLines, ['可用积分：0', '10元需要1000积分']);
  assert.deepEqual(result.amountLines, ['现金：0.00 元', '10元需要1000积分']);
  assert.equal(result.loaded, undefined);
  assert.equal(result.cash, undefined);
});

test('phone numbers are masked in every returned text field', () => {
  const result = observe(
    '充值号码 +86 138-0013-8000\n账户13900139000积分1000\n订单接收 +8613800138000\n仅限本机 138 0013 8000',
    [button('账户13800138000')], '/account/13800138000',
  );
  assert.deepEqual(result.accounts, ['138****8000', '139****9000']);
  assert.ok(result.pointLines[0].includes('139****9000'));
  assert.ok(result.orderLines[0].includes('138****8000'));
  assert.ok(result.ruleLines[0].includes('138****8000'));
  assert.equal(result.buttons[0], '账户138****8000');
  assert.equal(result.page, 'https://apps.telefen.com/account/138****8000');
  assert.doesNotMatch(JSON.stringify(result), /13800138000|13900139000|0013[ -]8000/);
});

test('sensitive lines are excluded even when they contain financial keywords', () => {
  const result = observe('积分验证码：654321\n订单 Token=secret\n现金 payflag=secret2\n可用积分：900');
  assert.equal(result.signals.verification, true);
  assert.deepEqual(result.pointLines, ['可用积分：900']);
  assert.deepEqual(result.orderLines, []);
  assert.deepEqual(result.amountLines, []);
  assert.doesNotMatch(JSON.stringify(result), /654321|secret/);
});

test('mixed page signals do not decide the phase or claim success', () => {
  const result = observe('登录\n待支付\n短信验证码\n支付成功说明');
  assert.ok(Object.values(result.signals).every((value) => value === true));
  assert.equal(result.stage, undefined);
  assert.equal(result.phase, undefined);
  assert.equal(result.success, undefined);
});

test('hidden controls and input values are not read or returned', () => {
  const result = observe('可用积分：1000', [
    button('兑换'), button('隐藏', { visible: false }),
    button('', { aria: '查看订单' }), button('验证码654321'), button('兑换'),
  ]);
  assert.deepEqual(result.buttons, ['兑换', '查看订单']);
});

test('summary output stays bounded and deduplicated on a long page', () => {
  const text = Array.from({ length: 100 }, (_, i) => `可用积分 ${i} ${'规则'.repeat(150)}`).join('\n');
  const result = observe(text + '\n可用积分：1000\n可用积分：1000',
    Array.from({ length: 50 }, (_, i) => button(`按钮${i}`)));
  assert.equal(result.pointLines.length, 12);
  assert.ok(result.pointLines.every((line) => line.length <= 180));
  assert.equal(result.buttons.length, 25);
  const accounts = observe(Array.from({ length: 20 }, (_, i) => `账户138****${String(i).padStart(4, '0')}`).join('\n'));
  assert.equal(accounts.accounts.length, 4);
});

test('URL query/hash, credentials, storage, network and mutations remain inaccessible', () => {
  const result = observe('订单编号：TEST-123\n本单支付1000积分', [button('查看订单')]);
  assert.equal(result.page, 'https://apps.telefen.com/jycalls/');
  assert.deepEqual(result.orderLines, ['订单编号：TEST-123']);
});
