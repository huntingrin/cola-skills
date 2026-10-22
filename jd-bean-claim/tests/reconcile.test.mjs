import test from 'node:test';
import assert from 'node:assert/strict';
import {reconcile} from '../scripts/reconcile.mjs';
const row = {description:'活动奖励京豆',time:'2026-01-02 12:00:00',change:3};
const opts = {action:'signin',expectedBeans:3,startedAt:'2026-01-02T03:59:59Z',endedAt:'2026-01-02T04:00:02Z'};
const before = {valid:true,balance:10,ledger:[]};
test('matching prompt amount, time, ledger and balance verifies',()=>{
  assert.equal(reconcile(before,{valid:true,balance:13,ledger:[row]},opts).status,'verified');
});
test('unchanged balance remains unverified despite a success-like ledger',()=>{
  assert.equal(reconcile(before,{valid:true,balance:10,ledger:[row]},opts).status,'needs_review');
});
test('identical ledger rows retain multiplicity',()=>{
  assert.equal(reconcile({...before,ledger:[row]},{valid:true,balance:13,ledger:[row,row]},opts).creditedBeans,3);
});
test('newly visible old rows are not fresh rewards',()=>{
  assert.equal(reconcile(before,{valid:true,balance:13,ledger:[{...row,time:'2026-01-01 12:00:00'}]},opts).status,'needs_review');
});
test('wrong action, unknown balance or broken extraction cannot verify',()=>{
  for(const after of [{valid:false,balance:13,ledger:[row]},{valid:true,balance:null,ledger:[row]}])
    assert.equal(reconcile(before,after,opts).status,'needs_review');
  assert.equal(reconcile(before,{valid:true,balance:13,ledger:[row]},{...opts,action:'shopping'}).status,'needs_review');
});
test('already processed state has no newly credited rewards',()=>{
  const state={valid:true,balance:13,ledger:[row]};
  assert.equal(reconcile(state,state,opts).status,'needs_review');
});
