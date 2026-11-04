# QQ Naturalness Loop Implementation Plan

> **For agentic workers:** Execute this plan task-by-task with the `executing-plans` skill. Steps use checkbox syntax.

**Goal:** Gate automatic QQ bot releases on paired naturalness replay, observe released changes, and publish five-minute QQ Space capacity reports.

**Architecture:** Keep fixed replay cases and policy in the control repository; run response generation against the live production-compatible message builder/API without publishing messages. Store detailed assessments locally. Run a separate, deterministic QZone reporting unit on the production host using existing credentials.

**Tech Stack:** Python 3 control plane, Node.js bot runtime, systemd service/timer, Hermes-compatible local API, NapCat QZone WebSocket.

**Spec:** `docs/superpowers/specs/2026-11-05-qq-naturalness-loop-design.md`

## Global Constraints

- Use the labeled 1 GiB Codex relay key already installed on the server.
- Never copy credentials or raw/private chat text into Git.
- QQ Space reports include disk and memory capacity only.
- Candidate release requires at least 8 replay scenarios, naturalness delta >= 0.3, and other dimension deltas >= -0.2.
- Post-release rollback requires at least 8 holdout pairs and naturalness regression <= -0.3.

## Review Focus

- Fewer than 8 scenarios: leave the candidate pending/rejected; test empty and undersized corpus.
- Model/API failure or malformed score: never treat it as a pass; test both.
- Candidate changes non-replayable modules: require the fixed production test suite and do not overstate replay coverage; test allowlisted paths.
- Repeated QZone timer run: unique update IDs prevent accidental duplicate retries; test duplicate invocation and pending result.
- Public report content: reject secrets, long identifiers, and oversized text; test validation.

---

### Task 1: Five-Minute QQ Space Capacity Report

**Files:** Create `qq-space-disk-report.mjs`, its Node tests, and systemd service/timer units.

- [ ] Test root disk/memory formatting, five-minute unique IDs, and rejection of unsafe content.
- [ ] Implement deterministic report generation using `statfsSync('/')` and OS memory totals.
- [ ] Call the existing QZone publisher as the `hermes` user with a unique update ID.
- [ ] Run one actual report and verify the returned publication ID without exposing credentials.
- [ ] Enable the timer at five-minute intervals and verify the next trigger.

### Task 2: Paired Replay Benchmark

**Files:** Create `qq-evolution/replay.py`, `replay.schema.json`, and fixed synthetic scenario fixtures; modify `agent.py`, `supervisor.py`, and tests.

- [ ] Test that fewer than 8 cases, malformed scores, API errors, and regressions fail closed.
- [ ] Generate baseline and candidate responses serially through isolated replay sessions.
- [ ] Use a blinded Codex scorecard with dimensions naturalness, relevance, consistency, and boundaries.
- [ ] Gate release on the spec thresholds and store the scorecard only in private server state.
- [ ] Deploy, run the benchmark, and verify no replay text is written to Git.

### Task 3: Post-Release Outcome and Automatic Rollback

**Files:** Modify `remote_release.py`, `supervisor.py`, `daemon.py`, and tests.

- [ ] Test pending release metadata, minimum holdout sample count, threshold-triggered restore, and healthy completion.
- [ ] Record the release snapshot, baseline score, and observation window privately.
- [ ] Compare at least 8 fresh redacted production pairs to the saved baseline after 24 hours.
- [ ] Restore the original snapshot and restart if naturalness falls by 0.3 or more; leave status pending when evidence is insufficient.
- [ ] Push compact score summaries and source commits to the existing GitHub branch; keep text and secrets server-local.

### Task 4: Server Readiness and Final Verification

**Files:** Update `qq-evolution/README.md` and deployment checks.

- [ ] Verify all required CLI, schemas, keys, source paths, API, Node runtime, publisher, writable state, and systemd units before activation.
- [ ] Run the complete Python and Node test suites.
- [ ] Confirm the QQ bridge, API, supervisor, and report timer are active; confirm local/GitHub commit equality.
- [ ] Inspect one sanitized report and one complete replay/release record.

### Task 5: Continuous Group Style Learning

**Files:** Create `qq-group-style.mjs` and tests; modify `qq-hermes-bridge.mjs`, `qq-persona-messages.mjs`, and `qq-evolution/remote_release.py`.

- [ ] Test that only incoming group messages contribute aggregate style counts, with groups isolated and no raw text/member identifiers persisted.
- [ ] Require at least 30 recent messages, expire counters after 14 days, and inject the resulting context only into the matching group's reply prompt.
- [ ] Limit persisted data to daily numeric counters under a salted HMAC group key; use private file/directory permissions.
- [ ] Add the module and test to production patch snapshots and the automatic rollout suite.
- [ ] Verify the systemd bridge stays healthy after deployment and learned context appears only after the sample threshold.
