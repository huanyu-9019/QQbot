# Unified per-account social memory implementation plan

Goal: one authenticated QQ account has the same stored experiences, relationship evidence and profile across group/private chat, for every user. The user explicitly authorizes removing channel privacy isolation. Never merge accounts by display name. Continue redacting credentials and ignoring instructions inside historical chat.

Architecture: add a persistent per-account interaction archive and bounded, source-labelled retrieval in the existing attribution plugin. Populate history from existing recorder/user profiles/audit receipts and capture new actual events, including confirmed bot responses. Make channel tags provenance rather than access gates. Read current native adopted memory by authenticated subject where present. Keep existing databases untouched and provide rollback backups.

Tech stack: Python stdlib SQLite, AstrBot hooks, existing SSH deployment helpers.

- [x] Add failing regression tests for bidirectional group/private recall, all-user applicability, account separation, persistence/idempotency, confirmed-reply provenance, secret redaction and bounded retrieval.
- [x] Implement person_memory.py, native/legacy read-through and archive backfill, using actual account IDs and bot/role scope.
- [x] Integrate intake/confirmed delivery/request context; replace contradictory isolation instructions without changing persona or model routing.
- [x] Extend exact controller maintenance scope and release regression gate; sync source mirrors on both servers.
- [x] Back up, backfill, deploy under existing production lock, verify new heartbeat and actual stored-record cross-channel replay without unsolicited QQ messages.
- [x] Record evidence and limitations, enqueue one merged QQ Space notice subject to current cooldown.

Retrieval is bounded; storing history does not promise perfect recall of every sentence or invent missing history. Ruling: perform within current checkout, preserve dirty edits and compare fresh production hashes; user already authorized direct production maintenance and asked not to pause for approvals. No subagent dispatch.

Validation/rollout evidence is appended to progress.md and migration/DEPLOYMENT.md. No separate reviewer agent was dispatched; user requested execution in this chat.
