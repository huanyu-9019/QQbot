# QQ Naturalness Loop Design

## Intent

Make automatic bot changes measurably more natural, keep the production service healthy, and give the owner a five-minute QQ Space report of server disk and memory capacity.

## Goals

- Replay the same fixed, fictional chat scenarios against current and candidate bot behavior before release.
- Reject a candidate unless its paired naturalness score improves and relevance, consistency, and boundaries do not materially regress.
- Continuously learn each group's aggregate speaking rhythm from incoming group messages and use it only in that group's replies.
- Record replay and production outcomes without putting private chat logs, credentials, or server state in Git.
- Persist only pseudonymous daily count features for group style, with a 14-day rolling retention and no member IDs or message text.
- Publish a deterministic disk/memory report to QQ Space every five minutes, reusing production's existing restricted API credential and NapCat WebSocket.
- Continue to use the labeled 1 GiB Codex relay key; missing prerequisites must fail visibly before enabling the service.

## Non-goals

- Train model weights or claim that an LLM judge proves human preference.
- Publish conversation text, identifiers, API keys, or internal service details to QQ Space.
- Send disk reports to QQ groups or direct messages.

## Chosen Approach

Use paired replay through the production Hermes-compatible API with the real message builder and synthetic, versioned scenarios. A separate Codex judge scores blinded replies on naturalness, relevance, consistency, and boundaries. Require at least 8 scenarios, a naturalness gain of 0.3 on a 1-5 scale, and no average regression below -0.2 on other dimensions. Keep replay records server-local. After release, score a fresh set of real, redacted conversation pairs against the fixed rubric; automatically restore the release snapshot if the holdout score drops by at least 0.3 after at least 8 pairs. If the holdout lacks enough evidence, report pending rather than claiming success.

The bridge updates compact, per-group aggregate counters from incoming group messages: message length, punctuation, emoji presence, and broad laughter/casual-language categories. It stores a salted HMAC group key and daily numeric counters only. Style context becomes active after 30 messages, expires after 14 days, and describes tendencies without quoting messages or imitating individual members. Private chats and bot replies do not enter this learner.

The latest user instruction supersedes the single-host report: one systemd timer on the Codex control host gathers both machines' memory, swap, and disk figures plus Codex service/heartbeat/log-fetch health and production bot/API service health. Publish one combined QQ Space report. From the request at 2026-11-05 01:28:58 Asia/Shanghai, publish every five minutes for two hours, then every four hours. Persist the original start time so restarts do not reset the phase. The timer checks every five minutes but the publisher sends only when the phase slot changes. Old single-host reporting is disabled. Public text contains no IPs, credentials, group IDs, or conversation content.

## Constraints and Defaults

- The Codex host polls logs every 5 minutes and applies a 30-minute assessment cooldown.
- The 1 GiB host has 2 GiB swap; replay requests run serially with a fixed timeout and bounded scenario count.
- The production `API_SERVER_KEY` stays in `/home/hermes/.hermes/.env`; the Codex relay key stays in `/home/admin/bin/codex-relay` and `/home/admin/.codex/config.toml`.
- Private runtime state remains under mode `0700` directories with files mode `0600`; no user log text is committed.
- QQ Space report cadence is five minutes for the first two hours, then four hours; timestamp is Asia/Shanghai.

## Acceptance

- Unit tests prove replay scoring gates and malformed/insufficient scenario handling.
- The candidate is rejected before production when replay fails or score thresholds are not met.
- A one-shot space report passes validation and reaches QQ Space; the timer is enabled and schedules every 5 minutes.
- Server prerequisites are checked: Codex CLI, relay config/key, SSH keys, schemas, source checkout, API reachability, Node runtime, QZone publisher, writable private state, and systemd units.
- Production and control services remain active; the newest deployed commit matches GitHub.
