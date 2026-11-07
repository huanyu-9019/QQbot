# Jiangsheng project maintenance

This is a personal QQ social-agent project. GitHub repository:
https://github.com/huanyu-9019/QQbot

## Git ownership and history

- The user authorizes the local agent and server maintenance agent to inspect
  history, create commits and push verified project changes without asking again.
- Fetch before reconciling branches. Preserve independent local maintenance and
  server autonomous branches; never force push, rewrite shared history or overwrite
  another checkout's dirty changes. Do not merge into main just to bypass a conflict.
- Commit each coherent fix or feature with its tests. Stage explicit paths/hunks;
  preserve unrelated changes and their staging. Record unshipped work as unshipped.
- Use a specific Chinese subject prefixed with fix/feat/docs/chore and a body with
  the observed problem, root cause, behavior change, validation, deployment state
  and rollback reference when available. Do not use generic "update" messages.
- Autonomous release commits must identify affected paths, issue category,
  patch SHA-256 and production snapshot receipt. Only advance the deployed
  baseline after production gates succeed. Retry failed pushes on subsequent
  polls; a local commit is not proof that GitHub received it.
- Before reporting completion, check the remote ref against the committed SHA.
- To investigate a regression, use git log --all --grep, git log -- path,
  git show, git blame and git log -S/-G. Explain the relevant commit before editing.

## Data and deployment

- Never commit keys, tokens, private SSH keys, authentication state, raw chat logs,
  personal profiles, memory databases or runtime caches. Scan selected content
  before pushing. Credentials stay in their authorized local/server secret stores.
- Repository code is not proof of production deployment. Keep deployment evidence
  and pending local work distinct in messages and commit bodies.
- Preserve NapCat, model-router priorities and five-minute recovery probes.
  Same-account group/private memory is shared; different QQ accounts stay separate.
- QQ/Codex servers must work without the local machine. Production changes require
  backups, relevant tests and a fresh health check. Respect QQ Space cooldowns.
- See GIT_WORKFLOW.md and migration/DEPLOYMENT.md for paths and operational history.
