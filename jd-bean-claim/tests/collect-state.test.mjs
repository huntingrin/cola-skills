import test from 'node:test';
import assert from 'node:assert/strict';
import {collectBeanState} from '../scripts/collect-state.mjs';

// Minimal synthetic DOM fixtures; no real account data or browser dependencies.
function fixture({balance='0',hostname='bean.jd.com',pending,ledger=true}={}) {
  const table=(heading,rows)=>({innerText:heading,querySelectorAll:()=>rows.map(cells=>({
    querySelectorAll:()=>cells.map(innerText=>({innerText}))
  }))});
  const tables=[];
  if(pending)tables.push(table('待领取京豆数量',pending));
  if(ledger)tables.push(table('京豆变化',[
    ['活动奖励京豆','2026-01-02 12:00:00','+3'],
    ['订单123456789012345678使用京豆','2026-01-01 12:00:00','-5']
  ]));
  globalThis.location={hostname};
  globalThis.document={body:{innerText:pending?'购物返京豆':'我的京豆 收支明细'},
    querySelectorAll:()=>tables,
    querySelector:selector=>selector==='.my-card-bean-num' && balance!==null?{textContent:balance}:null};
}
test('zero is a valid balance; absent pending section does not invent rewards',()=>{
  fixture();const s=collectBeanState();assert.equal(s.valid,true);assert.equal(s.balance,0);
  assert.equal(s.pendingState,'section_absent');assert.equal(s.signText,null);
  assert.ok(!JSON.stringify(s).includes('123456789012345678'));
});
test('reads pending total and retains only order suffix',()=>{
  fixture({balance:'1,000',pending:[['+7','2026-01-03 23:59:59','123456789012345678']]});
  const s=collectBeanState();assert.equal(s.balance,1000);assert.equal(s.pendingVisibleTotal,7);
  assert.equal(s.pending[0].orderSuffix,'5678');assert.equal(s.pendingState,'table_present');
});
test('wrong site, missing ledger and unparseable balance fail closed',()=>{
  for(const input of [{hostname:'example.com'},{balance:null},{balance:'loading'},{ledger:false}]){
    fixture(input);assert.equal(collectBeanState().valid,false);
  }
});
