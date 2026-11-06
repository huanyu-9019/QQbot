# Deployment ledger and recovery

Status: NOT CUT OVER. AstrBot startup, QQ acceptance, plugin integration and controller adaptation remain unfinished.

## Verified backups

Production archive: `/var/backups/jiangsheng-astrbot/20261106T183724Z/production.tar.gz`

SHA-256: `34ce6f2dcedbb15b217d3bfe49498e54107231687f43bf445a7c10ceb5dc70ba`

Archive entries: 5422; bytes: 9753036; all selected root members verified. Includes production QQ code/data, Hermes configuration, current router keys, persona, user/group memories, units and admin source. Contains secrets; preserve root-only permissions and never commit the archive.

Controller archive: `/var/backups/jiangsheng-astrbot/controller-before.tar.gz` (control modules, state and systemd units; existence/nonempty verified).

## Pinned upstream sources

- AstrBot: `86c24e846c0de78830f6a0bc402049edb0f0c671` at `/opt/jiangsheng-astrbot/app`
- Companion: `c1faecf25de52a86d667d13aaaca9c3f2ee45536` at `/opt/jiangsheng-astrbot/companion`
- Recorder: `8cb184e2890dee7d5031d3a8ef6b753209dc7d11` at `/opt/jiangsheng-astrbot/recorder`

Python 3.12 virtual environment: `/opt/jiangsheng-astrbot/venv`. Host originally lacked ensurepip; `python3.12-venv` was installed through apt. Core pip installation reached package installation; plugin pip installation reached dependency resolution. Completion is NOT verified. Do not start additional installers until checking the existing processes.

## Current blocker

During package installation, SSH to production stopped returning its banner. TCP port 22 accepts connections but SSH banner exchange times out from both the laptop and the controller. Public admin homepage on 6069 returned HTTP 200; this does not prove the bot or the host is healthy. Root cause is not yet known. No AstrBot service, platform connection, production cutover, or old service disable was performed.

Recover through Aliyun console Workbench/VNC, collect memory/load/process output, stop only migration pip processes and restart `ssh`. After access returns, inspect kernel OOM messages, install logs, service health and disk before resuming. Avoid repeated background installers; use a single resource-limited transient systemd installer (MemoryMax/CPUQuota/IOWeight), verifying each exit before continuing.

## Rollback

Before cutover, stop only migration installer/test processes; original units and router configuration have not been replaced. Verify `napcat-qq`, `qq-hermes-bridge`, `hermes-qq-api` and `qq-chat-router` are active.

`switch.py` is prepared but NOT deployed or invoked. Once installed on Linux, `python3 switch.py rollback` stops/disables `jiangsheng-astrbot` before enabling/starting `qq-hermes-bridge`. It intentionally refuses to start the old responder if stopping the new one fails. The old Hermes API and all old memory files must remain available until acceptance and the observation window pass.

Full archive restoration is for damaged legacy files only: verify SHA-256, stop affected services, extract selected paths retaining ownership, then `systemctl daemon-reload` and restart those services. Do not blindly overwrite live secrets, newer conversations or all systemd units.

## Acceptance still required

Policy unit tests pass (11), including fallback-to-old responder state transitions. They are NOT live AstrBot integration proof. Still required: runtime and plugin load, model router requests with current config, independent vision/STT/TTS, real receipts and voice text, archive retention, native companion memory migration, mention attribution, quoted image recovery, alias persistence, burst queues, provider failures, restart persistence, controller observation/repair/release, admin display and one-responder cutover.

All Qzone migration notices must use `/home/hermes/qq-qzone-post.mjs` and its existing cooldown/global rate limit. Do not test publication during the hold.
