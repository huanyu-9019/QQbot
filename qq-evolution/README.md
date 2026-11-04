# QQ Evolution Supervisor

This directory contains the control-plane primitives for the unattended QQ bot improvement loop.

The supervisor is intentionally single-job on the 1 GiB Codex host. Production credentials, raw audit records, memory files, snapshots, and model transcripts stay outside Git. The model may return findings and a unified diff only; fixed code controls paths, tests, service names, restart, health checks, observation, and rollback.

Before enabling the systemd unit, configure the server-local `codex-relay`, SSH key, production source path, and state directories with mode `0700`/`0600`. Run the Python test suite and a simulated rollback cycle first.

The evaluator reads its source tree from `/home/admin/qq-evolution/development` by default. Set `QQ_EVOLUTION_REPO` in the server-local service environment to use another development checkout; the model working directory and patch allowlist are derived from the same path.

The service polls every five minutes and evaluates at most once per thirty minutes. Windows containing at least three reply pairs receive qualitative model assessment even when delivery succeeded. A hash of the last completed audit window prevents repeatedly changing the bot against unchanged conversations. Model request failures remain retryable errors.

Candidates have their hunk counts recomputed, then pass strict path and structure validation and a Git application check. Production snapshots its source, applies the same Git patch format, runs the Node suite, restarts the bridge, and checks service health over sixty seconds; failures restore the snapshot. Healthy releases advance the development Git baseline. With `QQ_EVOLUTION_GIT_REMOTE=origin`, commits are automatically pushed to `codex/qq-autonomous-evolution`; pending pushes retry on later polls. Two consecutive failed releases trigger a six-hour backoff before automatic recovery.

This loop learns by updating the bot's checked-in persona, rules and source. It does not train new model weights. Passing tests and service health checks do not establish that every conversational change improves quality; continued audit assessment supplies later feedback.
