from tests.test_group_reply_admission import GroupReplyAdmissionTests
from set_social_preferences import apply
from types import SimpleNamespace as NS


class SocialAddressingTests(GroupReplyAdmissionTests):
    async def test_configured_name_is_admitted_without_host_prefix_or_at(self):
        # The upstream persona ID can be 'original'/'default', not the spoken name.
        event = self.event('social-name-before', '江生在吗')
        self.assertNotEqual((await self.candidate(event))['reason'], 'direct_word')
        context = (await self.controller.observe_group_early(event)).unwrap()
        result = apply(self.app.runtime, context)
        self.assertEqual(result['after']['conversation.presentation.group_wakeup_bot_name'], '江生')
        self.assertTrue(all(v for k, v in result['after'].items() if 'guard' in k or 'resist' in k))
        for i, text in enumerate(['江生', '江生在吗', '江生你怎么看']):
            event = self.event('social-name-after-' + str(i), text)
            event.is_at_or_wake_command = False
            decision = await self.candidate(event)
            self.assertTrue(decision['admitted'])
            self.assertEqual(decision['reason'], 'direct_word')
        foreign = self.event('social-foreign', '江生你怎么看')
        foreign.message_obj.message.insert(0, NS(type='At', qq='201'))
        self.assertFalse((await self.candidate(foreign))['admitted'])
        again = apply(self.app.runtime, context)
        self.assertEqual(again['changed'], [])
