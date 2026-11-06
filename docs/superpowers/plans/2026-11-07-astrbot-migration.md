# AstrBot migration implementation plan

Goal: replace Hermes and its QQ bridge with AstrBot without losing Jiangsheng's personality, useful memories, multimodal support, routing, or independent maintenance.

Spec: the user's migration brief in the main conversation on 2026-11-07. Execution is authorized through production cutover; no intermediate approvals required.

Architecture: keep NapCat, localhost model router (live configuration is authoritative), and existing rate-limited Qzone tools on 39.105.219.112. Install AstrBot and companion/recorder plugins in an isolated environment on that host. Adapt the observer and admin on 101.200.59.133. Both hosts must operate without the laptop.

Constraints: cloud inference only; do not expose secrets in source, models, or progress output. Preserve 300-second model recovery probes and Qzone cooldown/global limits. One responder at a time. No master/owner identity. Preserve existing unrelated local changes. Self-learning is a later validation step, never a second concurrent memory injector.

## Tasks

- [x] 1. Back up production/configuration/persona/memories/controller; verify archive and document rollback. Inventory upstream plugin APIs, resource requirements and pinned commits.
- [x] 2. Install a pinned AstrBot runtime and companion/recorder plugins without QQ connection. Configure current router, persona, migrated data, cloud vision/STT/TTS, retention, and performance mode. Verify startup and resource usage.
- [x] 3. Add tested compatibility/maintenance integration for structured audit, attribution, media, receipts, and persistence. Adapt controller collection, release/rollback and admin reporting. Verify against realistic event fixtures and actual provider requests.
- [x] 4. Run acceptance: mentions to others, direct mentions, images/replied images, aliases, burst deduplication, provider fallback, persistence after restart, and controller observation. Fix failures before enabling QQ.
- [x] 5. Stop old responder, enable new responder, verify online health and rollback entrypoint. Record version/tests; enqueue a Qzone digest using the existing cooldown gate. Validate self-learning separately only if foundation is stable.

## Review focus

Do not let default plugin wake-up rules reply to another person's mentions. Distinguish queued/generated/sent/failed messages. Do not let text-only fallbacks claim vision success. Ensure controller repair targets the new runtime rather than restarting the retired bridge. Bound recorder media storage and model context. Validate rollback restores exactly one responder.
