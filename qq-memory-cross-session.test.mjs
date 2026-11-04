import test from 'node:test';
import assert from 'node:assert/strict';
import { record, recall } from './qq-memory.mjs';
const task = {kind:'group', userId:'424242', groupId:'777', sessionKey:'qq:group:777', speakerName:'小明', privateNickname:'', text:'我的兴趣是踢足球'};
record(task);
const privateTask = {kind:'private', userId:'424242', groupId:'', sessionKey:'qq:private:424242', speakerName:'', privateNickname:'小明'};
assert.match(recall(privateTask), /踢足球/);
test('explicit interest is available across group and private sessions', () => {});