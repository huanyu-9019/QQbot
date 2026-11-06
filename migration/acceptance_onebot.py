"""Disconnected OneBot simulator. All outbound chat is captured, never sent to QQ."""
import argparse
import asyncio
import io
import json
import time
from pathlib import Path

from aiohttp import web
from PIL import Image
from websockets.asyncio.client import connect

SELF = 3899701587
USER = 199900001
GROUP = 888000001


async def main(mode):
    marker = Path('/etc/jiangsheng-runtime')
    if marker.exists() and marker.read_text().strip() == 'astrbot':
        raise RuntimeError('refusing simulated account connection to the production responder')
    sends = asyncio.Queue()
    captured = []
    run_id = int(time.time())
    png = io.BytesIO()
    Image.new('RGB', (240, 180), (255, 0, 0)).save(png, format='PNG')
    async def picture(_):
        return web.Response(body=png.getvalue(), content_type='image/png')
    blue = io.BytesIO()
    Image.new('RGB', (240, 180), (0, 0, 255)).save(blue, format='PNG')
    async def quoted_picture(_):
        return web.Response(body=blue.getvalue(), content_type='image/png')
    app = web.Application()
    app.router.add_get('/red.png', picture)
    app.router.add_get('/blue.png', quoted_picture)
    async def speech(_):
        path = Path(Path('/opt/jiangsheng-astrbot/speech-sample-path.txt').read_text())
        return web.Response(body=path.read_bytes(), content_type='audio/wav')
    app.router.add_get('/speech.wav', speech)
    runner = web.AppRunner(app)
    await runner.setup()
    await web.TCPSite(runner, '127.0.0.1', 6201).start()
    headers = {'X-Self-ID': str(SELF), 'X-Client-Role': 'Universal', 'User-Agent': 'OneBot/11 migration-acceptance'}
    for attempt in range(45):
        try:
            reader, writer = await asyncio.open_connection('127.0.0.1', 6199)
            writer.close()
            await writer.wait_closed()
            break
        except OSError:
            if attempt == 44:
                raise
            await asyncio.sleep(1)
    async with connect('ws://127.0.0.1:6199/ws/', additional_headers=headers) as ws:
        async def receive():
            async for frame in ws:
                obj = json.loads(frame)
                action = obj.get('action', '')
                params = obj.get('params', {})
                if action.startswith('send_'):
                    data = {'message_id': 9000000 + len(captured)}
                    for segment in params.get('message', []) if isinstance(params.get('message'), list) else []:
                        file = segment.get('data', {}).get('file', '')
                        if isinstance(file, str) and file.startswith('base64://'):
                            segment['data']['file'] = '<captured media: ' + str(len(file)-9) + ' base64 characters>'
                    captured.append({'action': action, 'params': params, 'at': time.time()})
                    await sends.put(captured[-1])
                elif action == 'get_login_info':
                    data = {'user_id': SELF, 'nickname': '江生'}
                elif action == 'get_status':
                    data = {'online': True, 'good': True}
                elif action == 'get_friend_list':
                    data = [{'user_id': USER, 'nickname': '验收用户', 'remark': ''}]
                elif action == 'get_group_list':
                    data = [{'group_id': GROUP, 'group_name': '迁移隔离验收'}]
                elif action in ('get_group_member_info', 'get_stranger_info'):
                    data = {'user_id': params.get('user_id', USER), 'nickname': '验收用户', 'card': '', 'role': 'member', 'sex': 'unknown', 'age': 0}
                elif action == 'get_group_info':
                    data = {'group_id': GROUP, 'group_name': '迁移隔离验收', 'member_count': 3, 'max_member_count': 200}
                elif action == 'get_group_member_list':
                    data = [{'user_id': USER, 'nickname': '验收用户', 'card': '', 'role': 'member'}]
                elif action == 'get_msg':
                    data = dict(message_id=params.get('message_id'), time=int(time.time()), message_type='group', group_id=GROUP,
                                sender={'user_id': USER, 'nickname': '验收用户'}, message=[{'type': 'image', 'data': {'file': 'blue.png', 'url': 'http://127.0.0.1:6201/blue.png'}}], raw_message='[图片]')
                elif action == 'get_version_info':
                    data = {'app_name': 'migration-acceptance', 'app_version': '1', 'protocol_version': 'v11'}
                else:
                    data = {}
                await ws.send(json.dumps(dict(status='ok', retcode=0, data=data, echo=obj.get('echo'))))
        task = asyncio.create_task(receive())
        await ws.send(json.dumps(dict(time=int(time.time()), self_id=SELF, post_type='meta_event', meta_event_type='lifecycle', sub_type='connect')))
        for _ in range(45):
            await asyncio.sleep(1)
            try:
                state = json.loads(Path('/opt/jiangsheng-astrbot/runtime/data/jiangsheng-health.json').read_text())
                if state.get('qqConnected') and state.get('companionReady') and time.time() - state['timestamp'] < 15:
                    break
            except (OSError, ValueError):
                pass
        else:
            raise RuntimeError('companion did not become ready in the disconnected test')

        async def event(text, number, segments=None):
            message = segments or [{'type': 'at', 'data': {'qq': str(SELF)}}, {'type': 'text', 'data': {'text': text}}]
            return dict(time=int(time.time()), self_id=SELF, post_type='message', message_type='group', sub_type='normal', message_id=run_id + number,
                        user_id=USER, group_id=GROUP, message=message, raw_message=text, font=0,
                        sender=dict(user_id=USER, nickname='验收用户', card='', role='member', sex='unknown', age=0, area='', level='', title=''))

        results = {}
        foreign = await event('他叫什么名字', 1, [{'type': 'at', 'data': {'qq': '199900002'}}, {'type': 'text', 'data': {'text': '他叫什么名字'}}])
        await ws.send(json.dumps(foreign))
        await asyncio.sleep(5)
        results['foreign_mention_no_reply'] = sends.empty()
        while not sends.empty():
            sends.get_nowait()
        async def turn(label, text, number, segments=None, duplicate=False):
            payload = await event(text, number, segments)
            await ws.send(json.dumps(payload))
            if duplicate:
                await ws.send(json.dumps(payload))
            try:
                item = await asyncio.wait_for(sends.get(), timeout=105)
                content = item['params'].get('message')
                results[label] = {'received': True, 'message': content}
                print(json.dumps({label: results[label]}, ensure_ascii=False), flush=True)
                await asyncio.sleep(3)
            except asyncio.TimeoutError:
                results[label] = {'received': False}
                print(json.dumps({label: results[label]}), flush=True)
        if mode == 'tts':
            await turn('voice_output', '只回复：语音验证成功。', 40)
        elif mode == 'extended':
            await turn('voice_understanding', '语音里说今天的阳光怎么样？', 20,
                [dict(type='at', data={'qq': str(SELF)}), dict(type='text', data={'text': '语音里说今天的阳光怎么样？'}),
                 dict(type='record', data={'file': 'http://127.0.0.1:6201/speech.wav', 'url': 'http://127.0.0.1:6201/speech.wav'})])
            for index, text in enumerate(['请分别记下：甲是苹果。', '乙是香蕉。', '甲和乙分别是什么？两个都回答。']):
                await ws.send(json.dumps(await event(text, 30 + index)))
                await asyncio.sleep(.3)
            burst_captures = []
            deadline = time.time() + 90
            while time.time() < deadline:
                try:
                    item = await asyncio.wait_for(sends.get(), timeout=8)
                    burst_captures.append(item)
                    print('BURST_CAPTURE', json.dumps(item, ensure_ascii=False), flush=True)
                except asyncio.TimeoutError:
                    pass
            results['burst'] = burst_captures
        elif mode == 'resume':
            await turn('persisted_alias', '我之前明确告诉你的名字是什么？只说名字。', 2)
        else:
            await turn('addressed_reply', '我叫测试小雨，请记住我的名字，只回复我的名字。', 2, duplicate=True)
            await turn('alias_recall', '我刚才说自己叫什么名字？只说名字。', 3)
            await turn('image', '图里主要是什么颜色？只回答颜色。', 4, [dict(type='at', data={'qq': str(SELF)}), dict(type='text', data={'text': '图里主要是什么颜色？只回答颜色。'}), dict(type='image', data={'file': 'red.png', 'url': 'http://127.0.0.1:6201/red.png'})])
            await turn('quoted_image', '引用图片主要是什么颜色？只回答颜色。', 5, [dict(type='reply', data={'id': str(run_id-100)}), dict(type='at', data={'qq': str(SELF)}), dict(type='text', data={'text': '引用图片主要是什么颜色？只回答颜色。'})])
        results['captures'] = captured
        path = Path('/opt/jiangsheng-astrbot/acceptance-' + mode + '.json')
        path.write_text(json.dumps(results, ensure_ascii=False, indent=2))
        print('ACCEPTANCE_RESULT', str(path), flush=True)
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)
    await runner.cleanup()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--mode', default='initial', choices=['initial', 'resume', 'extended', 'tts'])
    asyncio.run(main(parser.parse_args().mode))
