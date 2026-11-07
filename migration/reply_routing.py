"""Keep bare names and mentions inside Companion's attributed reply pipeline."""


def companion_owns_wakeup(config):
    # AstrBot's built-in empty-prefix handler runs before ordinary listeners,
    # issues its own LLM request, and waits/stops without reaching our intake.
    config['wake_prefix'] = []
    config.setdefault('platform_settings', {}).update(
        empty_mention_waiting=False, empty_mention_waiting_need_reply=False)
    return config
