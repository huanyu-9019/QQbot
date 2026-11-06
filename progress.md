# SDD ledger — plan: docs/superpowers/plans/2026-11-07-astrbot-migration.md

User explicitly approved the migration design and continuous implementation, testing and production cutover.

Task 1: in progress. Production has Python 3.12.3, 1740 MiB RAM (623 MiB available), 23 GiB disk free; controller has 890 MiB RAM (440 MiB available). Existing services healthy. Backups started.

Ruling: use a sibling Git worktree through git fallback — native create_worktree rejected nested repository sourceRoot even though it is in the chat working directory. Existing dirty checkout is preserved.

Pre-flight: AstrBot consumes the existing localhost router; runtime and observer must share the existing audit format and new runtime paths; Qzone must continue using the global existing gate. Upstream APIs must be inspected before implementing compatibility.

Task 1 backup checkpoint: production archive `/var/backups/jiangsheng-astrbot/20261106T183724Z/production.tar.gz`, SHA-256 `34ce6f2dcedbb15b217d3bfe49498e54107231687f43bf445a7c10ceb5dc70ba`, 5422 entries, 9753036 bytes; all selected members verified. Controller backup nonempty verified.

Task 2 started: all three upstream sources cloned and pinned (see migration/DEPLOYMENT.md). Added Python 3.12 venv support; dependency installation began but completion is unverified. No AstrBot service or QQ platform was enabled.

Blocker: production SSH banner timeout from local and controller, while admin homepage 6069 returned 200. Need console recovery/diagnostics; root cause unconfirmed. Asked user for Workbench/VNC recovery. Do not claim old bot health from static homepage.

Ruling: stop additional production mutations pending restored access and health verification; continue local replay policies and recovery artifacts. Subsequent installation must be serial and resource-limited.

Local validation: policy seven tests and responder switch four tests first failed with missing implementation, then passed (11/11). Windows test exposed unclosed SQLite connection and it was fixed using explicit connection close. These helpers are not deployed; live acceptance remains incomplete.

Recovery checkpoint 2026-11-07 03:42 CST: SSH restored following user console reboot. Single resource-limited dependency install completed successfully. AstrBot 4.29.4 and both pinned plugins run disconnected from real QQ. Current production remains Hermes. Available memory ~482 MiB with both runtimes, swap unused. Companion requires foreground_slots >=2 for external tools; corrected from 1. Model routing read live and retained unchanged.

Task 1: complete — both archives verified and upstream versions pinned. Task 2: in progress — cloud MiniMax TTS returned 189554 bytes, Gemini native audio transcribed the sample successfully (proper-name homophone error noted). Added cloud STT adapter and media-only 512 MiB/30-day quota; new tests failed then passed, suite 13/13. Independent vision uses the retained router. Legacy persona loaded into AstrBot database and profiles imported with equality/privacy filter.

Task 4 partial evidence: disconnected OneBot run acceptance3 captured exactly four replies for four distinct directed messages despite duplicated delivery; foreign mention produced none, explicit name/recall correct, red image and quoted red image both answered red. Companion initialization succeeded. Test artifacts are server-local and never sent to QQ. Restart persistence, burst scenario, audio chain and controller adaptation still required.


Completion checkpoint 2026-11-07: tasks 1–5 complete. Actual disconnected acceptance passed aliases, restart memory, foreign mentions, duplicate IDs, red/quoted-blue images, inbound cloud speech, audited TTS and bursts. Controller sanitized new audit through SSH; its Codex endpoint returned valid JSON. Final regression: controller 93, migration 18, retained production Node 64.

Final review identified and fixed publication races, incomplete reply health, missing retained Node tests and historical failed-turn poisoning of release health. No remaining cutover blocker was found. Actual backend execution caught CRLF in the executable admin helper; Linux LF normalization fixed it and the real helper then passed.

Production cutover succeeded: AstrBot enabled/active, old bridge disabled/inactive, real QQ and companion ready, acceptance=false. The controller deployed a startup-heartbeat instrumentation patch through the full tested release path (e48dff1). Supervisor, incident timer and status timer resumed. Fresh text/vision probes passed with zero overdue turns. Both servers remain independent of the laptop.

Admin backend was verified directly; Windows Chrome rendered live assets with actual sanitized server snapshots (login not retested). Qzone migration/test digest queued under account_cooldown until Nov 8 02:21 CST; no publication claimed. Extra self-learning plugin remains outside production pending compatibility/resource validation. See migration/DEPLOYMENT.md for backups, evidence and rollback.

Optional plugin follow-up: inspected self-learning 4.7.3 source at bba9c57. Its request injection, direct persona writes and local memory/reply fallback overlap companion, while its delegation covers LivingMemory/Group Chat Plus. Kept outside production; source findings and the requirements for an isolated expression-only trial are recorded in migration/SELF_LEARNING_REVIEW.md.
