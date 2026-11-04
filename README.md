# QQbot

QQ bot runtime source for the Hermes + NapCat OneBot deployment.

## Contents

- Current `qq-*.mjs` bridge modules and their focused Node.js tests.
- `qq-persona.md` and the checked-in QZone text assets used by the bot.
- No production credentials, `.env` files, user memory, or runtime state.

## Runtime

The production bridge currently runs as `qq-hermes-bridge.service` under the
`hermes` user and connects to a local Hermes API and NapCat OneBot WebSocket.
Deployment-specific endpoints and secrets must be supplied on the server and
must not be committed here.

Run the Node.js test suite with:

```sh
node --test qq-*.test.mjs
```

Before deploying a change, run the tests and verify the service health and
OneBot connection. Keep a recoverable production snapshot before replacement.
