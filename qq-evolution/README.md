# QQ Evolution Supervisor

This directory contains the control-plane primitives for the unattended QQ bot improvement loop.

The supervisor is intentionally single-job on the 1 GiB Codex host. Production credentials, raw audit records, memory files, snapshots, and model transcripts stay outside Git. The model may return findings and a unified diff only; fixed code controls paths, tests, service names, restart, health checks, observation, and rollback.

Before enabling the systemd unit, configure the server-local `codex-relay`, SSH key, production source path, and state directories with mode `0700`/`0600`. Run the Python test suite and a simulated rollback cycle first.
