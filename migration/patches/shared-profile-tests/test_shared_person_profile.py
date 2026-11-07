import json
from companion_v2.execution.models import TaskError
from tests.test_group_memory import GroupMemoryTests


class SharedPersonProfileTests(GroupMemoryTests):
    async def accepted(self, **options):
        # A new private turn does not replay the previous group's scripted tool.
        self.native.provider.client.state.behavior = None
        return await super().accepted(**options)

    async def test_own_group_statement_is_available_in_private_and_recall(self):
        await self.start_host()
        _, _, receipt = await self.save('我喜欢天文，周末会看星星')
        private, _ = await self.accepted(identifier='shared-private', text='还记得我的爱好吗')
        items = self.app.messages.acquaintance.shared_statements(private)
        self.assertEqual([x['memory_id'] for x in items], [receipt['memory_id']])
        self.assertEqual(items[0]['statement'], '我喜欢天文，周末会看星星')
        self.assertEqual(self.app.messages.acquaintance.recall(private)['shared_group_statements'], items)
        self.assertNotIn('group_id', json.dumps(items))
        from types import SimpleNamespace as NS
        from astrbot_host.core_reply_context import build_core_reply_prompt
        prompt = build_core_reply_prompt(self.app, private,
            NS(text='还记得我的爱好吗', instruction='', images=(), at=self.clock.now()), at=self.clock.now())
        self.assertIn('shared_person_profile', prompt.sections)
        self.assertIn('我喜欢天文，周末会看星星', prompt.instruction)
        await self.controller.terminate()
        from tests.group_host_support import group_config
        self.controller = self.make_controller(group_config())
        self.assertTrue((await self.controller.start()).is_success)
        private, _ = await self.accepted(identifier='shared-after-restart', text='再聊聊')
        self.assertEqual(self.app.messages.acquaintance.shared_statements(private)[0]['memory_id'], receipt['memory_id'])

    async def test_other_person_and_other_bot_do_not_enter_private_profile(self):
        await self.start_host()
        await self.save('我喜欢天文', sender='201')
        await self.save('我喜欢另一个机器人', target='group-c')
        private, _ = await self.accepted(identifier='shared-isolation', text='你好')
        self.assertEqual(self.app.messages.acquaintance.shared_statements(private), [])
        with self.assertRaises(TaskError):
            self.app.messages.acquaintance.shared_statements(private, speaker_id='201')

    async def test_private_only_bridge_does_not_export_other_group_statements(self):
        await self.start_host()
        a, _, _ = await self.save('这是A群的约定')
        b, _ = await self.receive('在B群', target='group-b')
        self.assertEqual(self.app.messages.acquaintance.shared_statements(a), [])
        self.assertEqual(self.app.messages.acquaintance.shared_statements(b), [])

    async def test_correction_and_retraction_are_reflected_in_shared_profile(self):
        await self.start_host()
        _, _, receipt = await self.save('我喜欢红茶')
        private, _ = await self.accepted(identifier='shared-correct', text='你好')
        self.assertEqual(len(self.app.messages.acquaintance.shared_statements(private)), 1)
        args = dict(input_handle='group-input-1', memory_id=receipt['memory_id'], expected_revision=1)
        await self.receive('我现在喜欢绿茶', commands=[('group.memory.remember', args | {'statement':'我现在喜欢绿茶'})])
        items = self.app.messages.acquaintance.shared_statements(private)
        self.assertEqual([(x['statement'], x['revision']) for x in items], [('我现在喜欢绿茶', 2)])
        await self.receive('撤回我的偏好', commands=[('group.memory.retract', args | {'expected_revision':2})])
        self.assertEqual(self.app.messages.acquaintance.shared_statements(private), [])

    async def test_withdrawn_source_and_cached_tool_results_are_not_reused(self):
        await self.start_host()
        original, batch, _ = await self.save('我喜欢红茶')
        private, _ = await self.accepted(identifier='shared-withdraw', text='你好')
        tools = self.app.tools.acquaintance
        cached, _ = tools.execute(private, 'unused', 'read', 'acquaintance.recall', {})
        self.assertEqual(len(cached['payload']['shared_group_statements']), 1)
        event = self.app.runtime.read_one('SELECT event_key FROM conversation_inputs WHERE batch_id=?', (batch,))
        self.app.withdraw(original, event[0]).unwrap()
        self.assertEqual(self.app.messages.acquaintance.shared_statements(private), [])
        checked, _ = tools.validate({'arguments_json':'{}'}, private, cached)
        self.assertEqual(checked['payload']['shared_group_statements'], [])
