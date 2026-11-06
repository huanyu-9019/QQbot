# Optional self-learning integration check

Source inspected after the foundation cutover: NickCharlie/astrbot_plugin_self_learning 4.7.3, commit `bba9c57ce2f4e6ddba79e034893ce4d0ab61bbcd`.

Decision: **keep it outside production for now**. This is source compatibility analysis, not a successful runtime/load or resource test.

Evidence from the pinned source:

- `main.py:509` registers an LLM request hook for diversity, social context and jargon injection. Companion already injects conversation/relationship context.
- `services/hooks/llm_hook_handler.py:640` rewrites the request system prompt with its additions.
- `services/persona/persona_updater.py:1229` and `services/persona/temporary_persona_updater.py:103` call the host persona manager to update persona content. Current deployment deliberately keeps a stable persona with one tested source of publication.
- `docs/integrations.md` delegates local memory to LivingMemory and reply generation to Group Chat Plus when those plugins are detected; otherwise local behavior remains. Those are not the installed companion plugin, so enabling the defaults would not establish the required ownership boundaries.

A later isolated trial must disable overlapping persona evolution, affection/social context, local memory writing/injection and reply generation. It must prove that only expression/jargon learning remains, add an explicit companion-compatible handoff, and measure memory/CPU before rollout. No additional inference model, listener or memory writer was installed on either server by this assessment. Current learning continues through companion and the controller's existing evaluation/release loop.
