# QQbot

江生 QQ 社交智能体：生产使用 AstrBot、陪伴插件、消息记录器和 NapCat；
另一台服务器独立负责观察、评估、测试、修复和发布。

## Contents

- AstrBot compatibility and native plugin overrides in `migration/`, with regression tests.
- Controller and autonomous deployment code in `qq-evolution/`.
- Preserved `qq-*.mjs` router, Space tools and legacy bridge modules with Node.js tests.
- `qq-persona.md` and the checked-in QZone text assets used by the bot.
- No production credentials, `.env` files, user memory, or runtime state.

## Runtime

The production responder is `jiangsheng-astrbot.service`. The previous Hermes
bridge remains available for documented recovery; it is not a second active responder.
Deployment-specific endpoints and secrets must be supplied on the server and
must not be committed here.

部署与验收见 [migration/DEPLOYMENT.md](migration/DEPLOYMENT.md)。
提交、推送和查历史见 [GIT_WORKFLOW.md](GIT_WORKFLOW.md)。

Run the test suites with:

```sh
node --test qq-*.test.mjs
python -m unittest discover -s migration/tests
python -m unittest discover -s qq-evolution/tests
```

旧 Node.js 记忆测试依赖 Linux `/home/hermes/qq-persona.md`；Windows 下直接跑
整套会有路径错误，应在服务器既有测试环境验证，不要复制真实凭据或聊天数据来凑环境。

Before deploying a change, run the tests and verify the service health and
OneBot connection. Keep a recoverable production snapshot before replacement.
