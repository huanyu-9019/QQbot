# Jiangsheng AstrBot deployment and recovery

Status: **production cutover complete, 2026-11-07**. AstrBot, companion and recorder run on 39.105.219.112. Controller 101.200.59.133 observes, evaluates and publishes tested changes. Neither runtime depends on the laptop.

## Installed versions and locations

- AstrBot 4.29.4: `86c24e846c0de78830f6a0bc402049edb0f0c671`, `/opt/jiangsheng-astrbot/app`.
- Companion 7.1.3: `c1faecf25de52a86d667d13aaaca9c3f2ee45536`; performance mode, foreground slots 2, background slots 1. Companion owns memory/relationships/style; native AstrBot owns TTS.
- Recorder 0.0.4: `8cb184e2890dee7d5031d3a8ef6b753209dc7d11`; 100000 records/30 days, thumbnail media. Compatibility worker bounds media to 512 MiB/30 days.
- Python 3.12 environment `/opt/jiangsheng-astrbot/venv`; data `/opt/jiangsheng-astrbot/runtime/data`.
- Compatibility source `/home/hermes/migration/plugin`; installed plugin `runtime/data/plugins/astrbot_plugin_jiangsheng`.
- Controller source `/home/admin/qq-evolution/development`; imports `/home/admin/qq-evolution/control`. Source marker `development/migration/ACTIVE_RUNTIME` is `astrbot`.

`jiangsheng-astrbot.service` is enabled/active; `qq-hermes-bridge.service` is disabled/inactive. NapCat connects to localhost 6199 `/ws/`; dashboard 6185 stays localhost-only. Heartbeat checks real OneBot online status, companion readiness and freshness. `/etc/jiangsheng-runtime` is `astrbot`.

## Preserved configuration

NapCat, model router 8650, current model priority/credentials and 300-second recovery probes remain authoritative. Read `.hermes/chat-routing.json` on the server rather than restoring historical lists. All inference is cloud-based. Separate STT uses cloud Gemini native audio; TTS uses existing MiniMax credentials, normal probability 2% and matching text output. Audits retain transcripts, synthesis source and actual send receipts.

Persona is synchronized from `/home/hermes/qq-persona.md`. Legacy profiles and same-scope summaries are imported as untrusted facts with equality/privacy filters; refresh preserves native companion data. Technical administration creates no owner/master relationship. Foreign mentions are vetoed before reply; message IDs are deduplicated across restarts.

Controller cadence: incidents every minute, quality collection every 300 seconds, existing learning schedule every 900 seconds. Cloud analysis and tests can extend a cycle. Learning records do not imply deployment; no patch is forced merely to meet cadence. Both hosts boot independently of the laptop.

## Verification evidence

Artifacts: `/opt/jiangsheng-astrbot/acceptance-{initial,resume,extended,tts}.json`; final gates `/var/lib/jiangsheng-astrbot-migration/acceptance.json`. Actual AstrBot and cloud providers were exercised with a disconnected OneBot capture endpoint; no test chat went to real groups. Verified foreign-mention silence, deduplication, aliases, recall after restart, red image versus a separately quoted blue image, inbound speech, audited TTS, three-message bursts and provider fallback.

Controller SSH collection verified hashed speakers, transcripts, voice source and delivery. Its Codex endpoint returned schema-valid JSON. After cutover, its actual release path deployed startup-time heartbeat instrumentation: snapshot, tests, restart, real completion, stable observation and baseline commit succeeded (`e48dff1`). Release history: `/home/hermes/qq-evolution-release.jsonl`; autonomous revisions may advance past this checkpoint.

Final regression: controller 93 tests, migration 18, production Node 64. Release gates retain both Node/Python suites. Production writes, repairs and switching share `/run/lock/jiangsheng-responder.lock`; controller publish/baseline changes share `release.lock`. Release health scopes failed-turn evidence to this startup while monitoring retains historical alerts. Failed validation restores the previous snapshot.

Management: http://39.105.219.112:6069/ . Actual helper and two-host snapshot verified. Windows Chrome rendered live assets using actual sanitized snapshots; browser login/authentication was not retested. Large changed-file lists are expandable; obsolete Hermes controls are disabled in AstrBot mode.

## Verified backups

- Production `/var/backups/jiangsheng-astrbot/20261106T183724Z/production.tar.gz`: SHA-256 `34ce6f2dcedbb15b217d3bfe49498e54107231687f43bf445a7c10ceb5dc70ba`; 5422 entries, 9753036 bytes.
- Extra production `integration-before.tar.gz`: SHA-256 `4ca37d3f78d3532112009045fe5bcd6ca272a0fde582c3a84af37cacb6dc69d7`.
- Controller original `controller-before.tar.gz`; extra `controller-integration-before.tar.gz`: SHA-256 `8f70cf7330a819c8f31287f89a097795676adc84a5e8317a02a9f7ff747673df`.
- Original NapCat `napcat-before-cutover.json` and admin HTML `admin-index-before.html` in the production backup directory.

Archives contain credentials/private data; keep root-only on the servers. Existing controller edits were archived as `5a75aa9` before integration; unrelated patch files were preserved.

## Executable rollback

Pause controller writers on 101.200.59.133:

```sh
systemctl stop qq-incident.timer qq-admin-status.timer
systemctl stop qq-evolution.service qq-incident.service qq-admin-status.service
```

On 39.105.219.112:

```sh
python3 /home/hermes/migration/switch.py rollback
systemctl is-active qq-hermes-bridge hermes-qq-api napcat-qq
systemctl is-active jiangsheng-astrbot || true
```

This stops/disables AstrBot before removing its NapCat client and starting/enabling Hermes. It refuses to start the old responder if the new one cannot stop. After successful rollback, update the controller marker and resume:

```sh
printf 'hermes\n' > /home/admin/qq-evolution/development/migration/ACTIVE_RUNTIME
chown admin:admin /home/admin/qq-evolution/development/migration/ACTIVE_RUNTIME
systemctl start qq-evolution.service qq-incident.timer qq-admin-status.timer
```

Keep the old API/data available. Archive restore is for selected damaged paths; do not overwrite newer conversations or credentials wholesale.

## Qzone and optional learning extension

Digest `astrbot-migration-20261107` is **queued**, not published: account cooldown defers it until 2026-11-08 02:21 CST. Limits remain at least four hours between attempts and three attempts/day. No restriction was bypassed.

The extra self-learning plugin is not enabled in production. Pinned source inspection found overlapping prompt/persona/memory responsibilities without a companion handoff; see `SELF_LEARNING_REVIEW.md`. Runtime/resource testing remains necessary before any later rollout.
