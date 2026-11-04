import test from 'node:test';
import assert from 'node:assert/strict';
import { buildMessages } from './qq-persona-messages.mjs';

const task = {kind:'private', userId:'freshness-regression', text:'这个现在发布了吗'};
test('every ordinary turn receives the current Shanghai date, including midnight rollover', () => {
  const early = buildMessages(task,{now:new Date('2026-11-04T15:59:00Z')})[0].content;
  const late = buildMessages(task,{now:new Date('2026-11-04T16:01:00Z')})[0].content;
  assert.match(early, /2026年11月4日 23:59/);
  assert.match(late, /2026年11月5日 00:01/);
});
test('current facts must be checked and stale conversation claims cannot serve as evidence', () => {
  const system = buildMessages(task)[0].content;
  assert.match(system, /必须先用 web_search/);
  assert.match(system, /历史聊天.*不是实时事实依据/);
  assert.match(system, /搜索摘要.*发布日期/);
});

import * as facts from './qq-live-facts.mjs';
test('current questions and release-date followups require evidence, casual chat does not', () => {
  assert.equal(facts.requiresFreshFacts?.('现在英国首相是谁'), true);
  assert.equal(facts.requiresFreshFacts?.('iPhone Duo什么时候发布的'), true);
  assert.equal(facts.requiresFreshFacts?.('去年吗'), true);
  assert.equal(facts.requiresFreshFacts?.('我今天很开心'), false);
});
test('unverified current answers are withheld, successful current-turn search permits the answer', () => {
  assert.equal(facts.hasFreshSearchEvidence?.({output:[{type:'message',content:[]}]}), false);
  const output=[{type:'function_call',name:'web_search',call_id:'a'},
    {type:'function_call_output',call_id:'a',output:'<untrusted_tool_result>\n'+JSON.stringify({success:true,data:{web:[{url:'https://example.com',title:'Current announcement'}]}})+'\n</untrusted_tool_result>'}];
  assert.equal(facts.hasFreshSearchEvidence?.({output}), true);
  output[1].output=JSON.stringify({error:'search unavailable'});
  assert.equal(facts.hasFreshSearchEvidence?.({output}), false);
});
