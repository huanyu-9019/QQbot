"""Run with the production AstrBot SDK, without a QQ transport."""
import asyncio
from copy import deepcopy
from types import SimpleNamespace as NS
from astrbot.builtin_stars.astrbot.main import Main
from astrbot.api.message_components import Plain, At


async def check(config, component):
    async def current(*args, **kwargs):
        return None
    async def new(*args, **kwargs):
        return 'synthetic-conversation'
    plugin = Main.__new__(Main)
    plugin.context = NS(get_config=lambda **kwargs: config,
        conversation_manager=NS(get_curr_conversation_id=current, new_conversation=new))
    event = NS(unified_msg_origin='synthetic:test', get_messages=lambda: [component],
               get_self_id=lambda: '100', get_platform_id=lambda: 'synthetic',
               request_llm=lambda **kwargs: 'builtin_bypass_request')
    stream = plugin.handle_empty_mention(event)
    try:
        return await anext(stream, None)
    finally:
        await stream.aclose()


async def main():
    from reply_routing import companion_owns_wakeup
    old = {'wake_prefix': ['江生', '@江生'], 'platform_settings': {
        'empty_mention_waiting': True, 'empty_mention_waiting_need_reply': True}}
    fixed = companion_owns_wakeup(deepcopy(old))
    for label, component in [('private-name', Plain('江生')),
                             ('group-name', Plain('江生')), ('group-at', At(qq='100'))]:
        assert await check(old, component) == 'builtin_bypass_request', label + ' did not reproduce'
        assert await check(fixed, component) is None, label + ' still bypasses intake'
        print(label, 'reproduced before / no bypass after')


if __name__ == '__main__':
    asyncio.run(main())
