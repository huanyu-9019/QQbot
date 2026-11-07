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

Controller cadence: incidents every minute, quality collection every 300 seconds, learning evaluation every 1800 seconds. Cloud analysis and tests can extend a cycle. Learning records do not imply deployment; no patch is forced merely to meet cadence. Both hosts boot independently of the laptop.

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

## Private learning and detailed profiles — 2026-11-07 23:27 CST

Companion defaults now admit every private participant as an expression source, with a 30-minute scan interval. Private evidence and adopted rules remain scoped to each authenticated participant; group learning uses all members, at least 20 samples and its separate 30-minute scan. No explicit source/learning overrides were present at deployment. Candidate collection is not adoption: existing review/adoption gates remain, and this release does not claim any learned expression was adopted.

Learning request copies redact API keys, labelled credentials, private-key blocks, phone numbers and emails before cloud submission; original local audit evidence is unchanged. This is pattern-based redaction, not a guarantee that every possible personal detail is recognised. The portable upstream patch is `migration/patches/companion-learning.patch`, applied against pinned Companion 7.1.3. Companion backup: `/var/backups/jiangsheng-astrbot/private-learning-20261107T152254Z`; its root-only manifest records the original hashes and indexed backup files. The earlier group-default backup is `/var/backups/jiangsheng-astrbot/group-learning-20261107T150239Z/configuration.py`.

The compatibility request hook discourages fixed “嗯/嗯嗯/哦” openings and encourages source-backed, correctly attributed profile facts through existing memory tools. The controller reports `habitualAcknowledgementSessions`: at least five distinct delivered private turns, with 60% or more of the most recent 20 beginning with “嗯”; split/voice duplicates do not create additional turns. This is evaluation evidence, not a ban on ordinary acknowledgements or proof of improved real conversations.

The authenticated admin profile helper now reads the requested person's active, self-attributed native memory projection through read-only SQLite, alongside legacy fields. It displays source counts, attribution, confidence, conditions, validity dates, update time and revision. No raw source text/handles are exposed by this projection. Backend empty state is explicit. At verification native facts/operations were 0, and two enabled daily memory schedules existed; automatic memory reflection defaults to 23:50 Asia/Shanghai. No profile facts were invented or backfilled in this release.

Validation: 78 learning/privacy/configuration tests, 19 migration/admin tests, 105 controller tests; the controller suite also passed on its host. Actual admin helper returned the native projection; Windows Chrome rendered the live JavaScript using synthetic profile and empty-state data (authentication was not retested). Fresh runtime heartbeat confirmed QQ connected, Companion ready, acceptance disabled; controller service and incident/status timers were active. No new real QQ conversation was used as evidence that the “嗯” habit was resolved.

Admin backup: `/var/backups/jiangsheng-private-learning-20261107T152601Z`; controller backup: `/var/backups/jiangsheng-private-learning-20261107T152603Z`. Portable patch also copied to controller development sources. QQ Space event `private-learning-profile-20261107` is queued under `account_cooldown`, not sent.


## Shared identity and reply rhythm — 2026-11-08 00:14 CST

Deployed eight Companion runtime files with verified hashes and fresh QQ/Companion heartbeat. Root-only rollback snapshot: `/var/backups/jiangsheng-astrbot/shared-profile-reply-20261107T161335Z`. Portable runtime diff and isolated tests are in `migration/patches/companion-shared-profile-reply.patch` and `migration/patches/shared-profile-tests/`; design/limits in `migration/patches/SHARED_PROFILE.md`. Preserve these changes in subsequent autonomous releases; do not overwrite the live custom Jiangsheng plugin from a stale local copy.

Same-account names/aliases remain one native person card. The authenticated author's saved public group statements are revalidated and projected into their own private context/recall. Private facts never export to groups; other members/bots/roles and other group audiences cannot use this bridge. Corrections, retractions and source withdrawal invalidate cached results. Historical raw logs were not bulk-imported.

Reply defaults: continuation 8 turns/180 seconds; air-reference 6 replies/60 seconds and 30-second cooldown; help-question candidates enabled, interest candidacy 0.4, fatigue limit 10/30-minute decay. Group short-fragment waiting reduced from 15 to 2 seconds; private adaptive waiting 0.6–1.5 seconds, burst ceiling 4 seconds. These are waiting/candidacy settings, not end-to-end latency guarantees or guaranteed replies to every group message. Foreign mentions and duplicate-send guards remain. No relevant explicit native overrides were present.

Validation: five targeted sharing/privacy/correction tests passed; the updated sharing restart/native-context test and all 17 private-debounce tests passed in the 38-case regression run. Its three stale-fixture/assertion failures were corrected (native system-message position, actual 60-second air window, frozen-clock short-text wait); the final 17-case rerun including these, eight-turn cap, foreign mentions and all participation hints passed. Migration/admin 19/19 passed. Tests used isolated synthetic QQ fixtures, never real contacts. Live runtime and NapCat active, controller service and incident/status timers active, zero new runtime ERROR/Traceback at verification. Real post-release conversational improvement has not yet been measured.

QQ Space event `shared-profile-reply-20261108` accepted into the existing queue with `account_cooldown`; not published.


## Bare-name / mention reply incident — 2026-11-08 00:42 CST

Root cause: AstrBot built-in `handle_empty_mention` runs at `sys.maxsize-1`, before migration intake. A bare wake-prefix name or standalone mention issues its own LLM request and then waits/stops, leaving no `jiangsheng_turn`; the transport correctly rejects the unattributed send. This reproduces for private-name, group-name and group-mention scenarios using the actual built-in code. Connection-only health did not detect delivery health.

Fix: clear global `wake_prefix` and disable `platform_settings.empty_mention_waiting` / `empty_mention_waiting_need_reply`, so Companion listeners own these turns. Added idempotent `migration/reply_routing.py` and used it from the configuration generator to prevent reintroduction. Do not restore the old name wake-prefix settings or disable transport attribution guards as a workaround. No credentials/model-route changes. Temporary diagnostic plugin additions removed; unrelated production plugin content preserved. Backup: `/var/backups/jiangsheng-astrbot/bare-wakeup-20261107T164048Z`.

Validation: actual built-in reproducer fails the old behavior/avoids bypass after the new settings for all three scenarios; 20 migration tests pass; two native admission tests pass (standalone mention admission and foreign-mention suppression). The user's concrete-content tests produced confirmed delivery receipts in both private and group at approximately 00:38:55 and 00:39:08, before the configuration repair restarted the runtime. Bare-name real-world delivery after the restart has not yet been sampled. Fresh new runtime heartbeat shows QQ/Companion ready, and post-restart logs contain no send failure/Traceback. Model/end-to-end response time can still exceed the input debounce: those two real responses took about 33 seconds.

QQ Space notice `bare-wakeup-fix-20261108` is queued under `account_cooldown`, not published. Repair helper, generator and native reproducer are preserved on the controller development tree.


## Social addressing preferences — 2026-11-08 00:52 CST

Applied native role-level `conversation.presentation.group_wakeup_bot_name=江生` and enabled name matching through ReplyConfigurationOwner, retaining injection/privacy/reality-promise guards. AstrBot persona ID is `default`; the projection ID is not a usable spoken name. Actual native installation ID is `astrbot-private-companion-v2:multi:jiangsheng`, role `jiangsheng`, bot `bot-3899701587`. Resolve from runtime identity and persona_binding_events; role_bindings/conversation_batches may be empty in native core mode. Never infer installation ID from the directory name. Helper `migration/set_social_preferences.py` preserves the native owner revision, is idempotent, and requires a single matching active recorded role. Backup: `/var/backups/jiangsheng-astrbot/social-preferences-20261107T165159Z/companion-v2.sqlite3`.

Two isolated native tests passed: actual role config admits 江生 / 江生在吗 / 江生你怎么看 without mention or native wake flag, rejects a foreign-mention case, and is idempotent; existing delivered-followup test confirms continuing beyond three turns. This changes candidate admission, not a guarantee that every ambiguous name reference gets a reply. Model context still decides intent; continuing/reply quote paths are retained. Existing cloud expression learning retains scoped collection/review/adoption, and source instructions restrict learning to expression rather than copying identity or relationships. Stable identity/no-master instructions remain in the live request hook. No claim of measured intelligence improvement or guaranteed resistance to every prompt injection.

Live native configuration readback confirms 江生; fresh runtime heartbeat QQ/Companion ready and services active. Repair helper archived on controller. QQ Space `social-addressing-20261108` queued under account_cooldown, not published.


## Identity and social context repair — 2026-11-08 01:34 CST

Confirmed actual missed turn `jiangsheng:1411470091`: leading 江生 plus foreign @ was stopped by the early custom guard before inference. Confirmed a different account's `我是谁` was answered 环宇. Both custom structured-chain addressing and native admission now accept a leading vocative before a foreign mention; @other followed by 江生 stays silent. The request includes bounded public target-name facts for foreign mentions, separately from the actual speaker. Exact first-person identity questions are grounded in the current sender's legacy record, with an explicit unknown-name fallback. No same-name account merges.

The current speaker card exposes only a private-contact-known boolean, never private text or timings. Readback confirms 环宇 has both private and group contexts; the second speaker is KAKÀ and has no native private-contact link. This does not reconstruct the initial private acquaintance story or prove all episodic recall is fixed.

Production backup `/var/backups/jiangsheng-astrbot/identity-20261107T173439Z`; controller backup `/var/backups/jiangsheng-identity-20261107T173446Z`. Portable plugin mirrors preserve the previous English-leak and occasional-voice patches. Precise native maintenance allowlist now also covers group_admission and person/service with corresponding regression gates. Source mirrors synced to both servers. Expression schema instructions strengthened; per-material learning failures cannot be hidden by an unrelated successful batch.

Verification: 113 controller tests; identity, mixed-admission, person-card privacy and expression request regressions pass. Read-only replay using deployed hooks and actual stored sender records resolves 环宇 versus KAKÀ and includes the mentioned person's public facts. No extra QQ group test messages sent. New runtime startedAt=1794072903.378536, QQ/Companion ready, no import errors; controller service/timers active and its admin-user probe reports transport/model/vision healthy. Learning health remains false due to failed historical batches; one pending expression signal now exists, not adopted. Native reaction catalogue contains 12 verified migrated fixed stickers, but actual reaction sending is not yet verified. Autonomous private initiation remains disabled. No claim of complete autonomous evolution or measured intelligence improvement.


## Cross-channel familiarity — 2026-11-08 01:53 CST

User reported intimate private conversation becoming merely 群友 in the group. Root cause: private relationship memory is audience-isolated; group cards carried only a contact boolean and the privacy instruction encouraged withholding relationship details. Preserve privacy while projecting observed per-account contact familiarity (`unknown`, `contact`, `repeated_contact`) from native private context counts or legacy contact existence. This is not a romantic status/consent inference and exports no private text. Current account reads repeated_contact; the other account reads unknown. Added regression for repeated/single/legacy/no-contact projection and absence of private text.

Live request hook instructs natural same-person continuity and disallows dismissing the user's mismatch concern as 随口说说 or 群里大家都在. First cloud synthetic evaluation was evasive, so that formulation was strengthened; second synthetic response acknowledges prior distance and familiarity, while unknown account remains unknown. Synthetic model samples do not guarantee every future actual response, nor reconstruct private episodic memory. No intimate label was hard-coded, no private raw conversation exported. Precise native person-card maintenance gate covers this regression.

Backups: `/var/backups/jiangsheng-astrbot/familiarity-20261107T175148Z` and `familiarity-20261107T175308Z`; controller source mirror backups at corresponding timestamps. Both source mirrors and regression file synced. Fresh QQ/Companion heartbeat required after the final restart. QQ Space notice is merged under existing cooldown/rate limit; do not force delivery.


## Unified group/private person memory — 2026-11-08 02:10 CST

The user explicitly removed channel privacy isolation for EVERY account. Same-account group/private experiences, relationship evidence and migrated profile now reach both audiences; different accounts remain separated. Added `migration/plugin/person_memory.py` with a persistent per-account interaction ledger, Chinese bigram search, bounded relevant/earliest-private/recent-private/recent-group recall, redaction and authenticated-source labels. Intake saves real human messages before optional participation rejection; bot statements are stored only after QQ delivery receipts. The same request hook reads the shared ledger and full legacy user summary/profile in group and private. Native active/adopted per-person memories have a role/bot/subject-checked read-through; current native atom/relationship stores were empty, so actual historical backfill was necessary.

Backfilled 455 recorder rows (bot rows excluded unless confirmed through audit), adding 104 audit entries; resulting archive has 290 deduplicated exchanges for 11 accounts. A second run added zero. Existing native/recorder databases are not changed. Channel is retained as provenance. Stored history is not a claim that each statement is true, or that every sentence can always fit into model context. Former private-only instructions/reference docs were superseded. No romantic label or new personal claim was fabricated.

Maintenance: person_memory.py and awareness_context.py included in exact snapshots/sync/patch scope; repaired the pre-existing omission of group_admission/person service from the patch regex. Controller exposes sharedMemoryReady/sharedMemoryError/sharedMemoryLastRecall and detects explicit memory failure. Deployment preserves dirty/live changes using fresh hashes and the shared production lock. Rollback originals and native SQLite backup: `/var/backups/jiangsheng-astrbot/unified-memory-20261107T181026Z`; controller backup `/var/backups/jiangsheng-shared-memory-20261107T181030Z`. Native tool scope remains native; the authorized archive/read-through provides cross-channel recall, not a claim that all native memory tools changed their own API scopes.

Verification: 30 local migration tests and 115 controller tests pass. 29 staged production tests pass; the local pending admin-profile enhancement test is unrelated to this change and was not deployed with its old production admin module. Real stored-account replay places 26 shared exchanges (human and confirmed bot, private and group) into both group/private deployed hooks without sending unsolicited QQ messages. SQLite quick_check=ok; new heartbeat startedAt=1794075047.0823107 shows QQ/Companion/sharedMemoryReady true; no import or shared-memory errors. Actual cloud synthetic group recall correctly cites the private library encounter; the other synthetic account has no such records. Controller probe as admin reports memory ready and service/timers active. Native learning remains degraded by existing failed batches, not claimed fixed by this release.

Space notice must merge under the existing cooldown/rate limit. Historical data that was never saved cannot be reconstructed automatically; no guarantee of perfect episodic recall or completed autonomous social evolution.


## Active ordinary group participation — 2026-11-08 02:31 CST

User reports too little group replying and asks for frequent participation without addressing the role. Audit showed ordinary statements/short talk such as 我有两个服务器/第一次见/这种贴图bug becoming collection_only before inference. Native candidate admission admitted only named/question/interest/continuation cues and globally stopped new nonexplicit topics after the 12-turn follow-up fuse.

Changed actual native GroupReplyAdmission: ordinary readable non-foreign-addressed group messages now return role_choice for contextual inference; the follow-up fuse only limits inherited follow-up rather than muting fresh candidacy. Explicit addressing retains priority, foreign mentions remain protected, disabled wakeup/empty/punctuation-only input remain silent. Participation instructions now favor active ordinary statements/shares/complaints/jokes, not default listening. Native owner settings: question threshold30, wakeup cooldown0, air reference20/60sec with cooldown0, fatigue reference20 with 5min recovery; group interjection interval0 and daily20. New-topic ordinary replies are not the scarce self-initiated interjection budget. Bare group images can enter via image wakeup enabled/weight0.6; no new local model or route change. Removed the legacy native group privacy-isolation flag per the previous explicit all-users shared-memory request; injection and actual-action-receipt guards remain enabled.

Backups: `/var/backups/jiangsheng-astrbot/active-group-20261107T183154Z` (code and native SQLite), `/var/backups/jiangsheng-active-group-20261107T183157Z` (controller release gate). Native config writes validate/read back through the owner; preference/media helpers now preserve the active settings. Future releases run both mixed-address and active-admission regressions before native sync. Both servers have source mirrors.

Verification: new active-admission contract reproduced two prior failures and now passes five tests; mixed-address regression passes. 115 controller and 30 local migration tests pass. On deployed code both admission suites pass, fresh startedAt1794076331.6012108 shows QQ/Companion/shared memory ready, no import/shared-memory errors. Actual cloud tool-choice tests choose reply for ordinary unmentioned 我有两个服务器 and 今天好累. Native image admission/readback passes. These are admission/model checks, not a claim of a new confirmed QQ delivery after this rollout. Model may still skip genuinely unsuitable content, and participation does not promise one message per every incoming event. No unsolicited group test messages were sent.


## Sender-bound relationship replies — 2026-11-08 03:25 CST

Confirmed in delivered group audit: one account asked 我是你的谁 and received 你是我的环宇啊, then after correcting the bot received 你是我的龟仙人啊. Its own profile names KAKÀ, and the shared recall was already account-separated; existing exact identity protection only handled 我是谁. Shared conversation and prior bot errors were influencing relationship/self-identification answers.

Added authenticated sender binding of profile names and same-account relationship evidence on every request. Other accounts' aliases are explicitly marked as foreign; third-party references in summaries and previous bot claims are not identity facts. Known direct bot misidentifications are excluded from bounded recall without deleting original audit/history. Response hook corrects direct foreign-name claims; transport independently rejects bypassed name-confused text/audio before delivery. Ordinary third-person mentions remain permitted. No relationship or profile was fabricated, accounts were not merged, and same-account group/private sharing stays enabled.

Controller collector preserves redacted sender_identity_mismatch events; metrics exposes blockedIdentityReplies and quality evaluation now recognizes cross-account identity/relationship attribution as a concrete issue. This catches known alias misuse, not every possible semantic relationship error. Deployment uses fresh hashes, backup, responder lock and rollback. Initial 44-second readiness wait was too short on this host and rolled back; retry allowed 100 seconds and confirmed the new healthy process. Production backup /var/backups/jiangsheng-astrbot/sender-binding-20261107T192415Z; controller backup /var/backups/jiangsheng-sender-binding-20261107T192503Z. Local 34 migration and 116 controller tests pass; 22 production staged identity/memory/hook/policy tests pass. QQ connected, Companion and shared memory ready; controller service and timers active. Cloud contaminated-history replay is checked separately. No unsolicited QQ test messages were sent.

Cloud validation after rollout: actual deployed request hooks with deliberately misleading preceding group assistant text were replayed through qq-chat. Current KAKÀ account answered 你是KAKÀ啊 without inheriting 环宇/龟仙人/romantic labels; actual 环宇 account retained its own documented relationship. No new QQ messages were sent for these tests. Fresh runtime health remains all ready and journal has no matching import/attribute/syntax errors.


## Admin status publisher repaired — 2026-11-08 03:36 CST

User reported stale status after refresh. Confirmed production evolution-status.json was 8287 seconds old and qq-admin-status.service failed each minute, while timer remained active. Executed actual SSH probe as admin: NameError learning_status not defined. publish_admin_status.py serialized runtime_ready/probe_runtime but omitted the new learning_status dependency. Added that definition to the standalone remote payload in both controller copies, preserving runtime data and the 150-second stale threshold. No responder restart or auth change required.

Regression executes the entire serialized probe in AstrBot mode with isolated filesystem/transport dependencies, reproducing the exact NameError before the patch and passing after it. All 117 controller tests pass; three production staged admin tests pass. Service now reports Result=success / ExecMainStatus=0. Snapshot age 22 seconds, Codex listening and QQ connected/canReply true. Backup: /var/backups/jiangsheng-admin-status-20261107T193534Z. Live API handler and subsequent timer generation are separately verified.


## Git ownership and searchable release history — 2026-11-08 03:51 CST

User explicitly delegates project Git history, commits and pushes to local/server maintenance, requesting detailed searchable messages. Existing GitHub remote is huanyu-9019/QQbot. Local codex/astrbot-migration and server codex/qq-autonomous-evolution remain separate; shared commits are not rewritten and main is not overwritten. Existing automatic push and retry remain enabled with QQ_EVOLUTION_GIT_REMOTE=origin.

Added AGENTS.md and GIT_WORKFLOW.md: authorize routine Git work, require explicit staging, problem/cause/change/test/deployment/rollback bodies, history lookup before regression fixes, remote-SHA confirmation, and exclusion of secrets/raw chat/user databases. Expanded ignore rules for secret filenames, database/log artifacts and root scratch patches. Updated README to AstrBot and documented Linux-dependent legacy Node tests.

Autonomous deployment messages now carry technical scope, fixed issue category/layer, line counts, patch SHA-256 and validated production snapshot reference; raw model evidence, chat, stdout diagnostics and credentials are not copied into messages. Production success still precedes baseline commit; rejected releases do not create successful-deployment commits. The unit test creates a real local repo/bare remote, commits, pushes and checks archived content and full message. Local 118 maintenance and 34 migration tests pass; remote controller118 tests pass. Windows legacy Node suite fails on its hardcoded /home/hermes path; the existing Linux suite passes all64 tests. No claim that the unshipped local admin-profile enhancement is deployed.

Controller backup /var/backups/jiangsheng-git-management-20261107T195026Z. Detailed-message supervisor deployed to both source copies and restarted healthy. Current migration branch source and prior deployed fixes are organized into distinct commits; uploaded refs are verified after push. Existing source-only and unrelated dirty files are preserved. Space notice follows the existing queue/cooldown.


## Source-grounded person portrait — 2026-11-08 04:13 CST

The old profile mixed unverified relationship labels with a separate keyword-based relationship score; repeated phrases and question fragments were displayed as preferences, group aliases repeated by group ID, and JavaScript interpreted millisecond dates as seconds. Chat hooks also injected the same personal profile and private summary twice. Confirmed native memory_atoms and relationship_memories were both empty; real interaction history was available. This release does not claim a functioning structured-memory learning loop.

Added a shared conservative person_portrait read model, used by admin and chat profile_context. De-duplicates migrated clues, excludes obvious question fragments, separates habits/routine/boundary, and preserves relationship labels as legacy_unverified. Old scores/stage transitions no longer masquerade as current relationships or common experiences. Originals remain preserved. Authenticated account-bound timelines show earliest/recent actual human/bot excerpts, timestamps and true stored message count. Active native self memories and adopted relationships use the same identity-bound native reader as chat; third-party subjects and invalidated entries are excluded. Admin reads the same runtime legacy profiles as the chat plugin, and the HTTP projection retains portrait/native fields. Shared-person success suppresses the second personal profile/private summary injection, retaining failure fallback and group summaries.

Production staged40 migration tests and controller40 migration+118 maintenance tests pass. A regression reproduces duplicate injection before the guard. Actual profile helper -> server projection verifies147 stored human messages and12 excerpts for the inspected account;34 profile files normalize without modifying originals, with2 obvious fragments excluded. New native facts remain0 and UI says so. Actual Windows Chrome CDP loads production assets and checks synthesized profile rendering, seconds/milliseconds/ISO time and HTML escaping; this is not a new authenticated browser login test or unsolicited QQ message test. Fresh runtime confirms QQ/Companion/shared memory all ready. Linux helper payloads deploy with LF to preserve executable shebangs.

Production snapshot: /var/backups/jiangsheng-astrbot/person-portrait-20261107T201155Z (sources, legacy profiles, shared/native DB snapshots). Controller mirror backup: /var/backups/jiangsheng-person-portrait-20261107T201301Z. Restore the original source tree in that snapshot and restart jiangsheng-astrbot/grok-admin-panel to roll back; data originals were not rewritten. Code and tests synced to the autonomous development directory. See migration/PERSON_MEMORY.md for provenance and remaining native-learning limitation. QQ Space notification uses the existing low-frequency queue.


## Mention subjects and grounded identification — 2026-11-08 04:35 CST

Recent actual incoming and delivered records confirmed two failures: a bare foreign mention followed by an identity question was stopped as collection_only, while a bot-prefixed question about another member received an inability-to-identify response despite a valid account and group nickname. The existing sender-binding guard also lacked a distinct explanation of legitimate third-person identification. The previous name test used synthetic raw OneBot dictionaries, so it did not cover typed At components with raw_message unavailable.

Added transport-only segment normalization and intake preservation. A narrow third-person identity question about an @ target is admitted through both early policy and Companion candidate selection; direct conversation addressed to that member remains protected. Resolving targets uses bounded concurrent OneBot group-member lookups (3-second per-call bound, at most5), verifies returned account/group, and falls back to typed At names and same-account stored group aliases. Failed or mismatched lookups do not invent a real identity. Current sender and referenced people remain separate. Exact single-target identity questions receive a grounded name/alias answer at the response hook; broader social questions retain model judgment. No private transcript is injected for mentioned third parties.

Added directedToBot audit metadata so legitimate questions about someone else are not classified as foreign-address reply bugs. mention_target_unresolved survives collector sanitization as mentionResolutionFailures, and evaluator guidance distinguishes source lookup failures from absent facts. Collector/metrics/agent deployed to both controller source copies, with no change to model routing, recovery probes, Space limits or person-memory data.

Local and controller45 migration+120 maintenance tests pass. Production staged45 plus mixed-address1 and active-admission5 tests pass. Read-only replay of the two actual recorded message chains and current account profiles confirms the known alias and current group nickname; generated-response hook corrects an intentionally injected inability-to-identify answer. Replay uses recorded At components and stored profiles, not a live OneBot member API request; API success/mismatch/fallback are exercised with isolated transport fixtures. No unsolicited QQ test messages were sent. Fresh restarted runtime confirms QQ/Companion/shared memory ready and controller/service timers active.

Production snapshot /var/backups/jiangsheng-astrbot/mention-identification-20261107T203353Z; controller snapshot /var/backups/jiangsheng-mention-identification-20261107T203525Z. Restore original sources from the snapshot and restart the affected service for rollback. Runtime data was not rewritten. Source and tests synchronized to the autonomous development tree. Git archive uses the existing two separate branches and Space notice follows the existing cooldown queue.
