"""Apply source-attributed Jiangsheng reply preferences through the native owner.

Run on the QQ host with Companion's package on PYTHONPATH. This does not rename
the AstrBot persona ID or modify any user profile, model route or credential.
"""
import json
from datetime import datetime, timezone
from pathlib import Path

from companion_v2.configuration.models import ConfigLayer, ConfigTarget
from companion_v2.foundation.refs import SubjectRef, SubjectKind
from companion_v2.conversation.reply_settings import ReplyConfigurationOwner, configuration_fields, target_for, GROUP_SAFETY_DEFAULTS
from companion_v2.conversation.segmentation import SegmentationPolicy
from companion_v2.execution.models import TaskContext
from companion_v2.storage.runtime import StorageRuntime


def apply(runtime, context=None, *, target=None):
    fields = configuration_fields(SegmentationPolicy(), False, 0)
    owner = ReplyConfigurationOwner(runtime)
    target = target or target_for(context, ConfigLayer.ROLE)
    before = owner.read(target, fields)
    changes = {'conversation.presentation.group_wakeup_bot_name': '江生',
               'conversation.presentation.group_wakeup_bot_name_enabled': True,
               'conversation.presentation.group_wakeup_question_threshold': 30,
               'conversation.presentation.group_wakeup_image_enabled': True,
               'conversation.presentation.group_wakeup_image_weight': 0.6,
               'conversation.presentation.group_wakeup_cooldown_seconds': 0,
               'conversation.presentation.group_conversation_followup_seconds': 300,
               'conversation.presentation.group_conversation_followup_max_turns': 12,
               'conversation.presentation.group_air_guard_max_bot_replies': 20,
               'conversation.presentation.group_air_guard_cooldown_seconds': 0,
               'conversation.presentation.group_wakeup_fatigue_limit': 20,
               'conversation.presentation.group_wakeup_fatigue_decay_minutes': 5,
               'conversation.presentation.group_high_intensity_enabled': False,
               **{'conversation.presentation.' + key: key != 'enable_group_privacy_guard' for key in GROUP_SAFETY_DEFAULTS}}
    result = owner.write(target, fields, changes=changes, reset=(),
                         expected_revision=before.revision, observed_at=datetime.now(timezone.utc))
    saved = owner.read(target, fields)
    assert all(saved.fields[key].value == value for key, value in changes.items())
    return {'revision': result.revision, 'changed': list(result.changed_fields),
            'before': {key: before.fields[key].value for key in changes},
            'after': {key: saved.fields[key].value for key in changes}}


if __name__ == '__main__':
    root = Path('/opt/jiangsheng-astrbot/runtime/data/plugin_data/astrbot_plugin_private_companion/installations/jiangsheng/runtime')
    import sqlite3
    with sqlite3.connect('file:' + str(root / 'companion-v2.sqlite3') + '?mode=ro', uri=True) as db:
        installation = db.execute("SELECT value FROM runtime_metadata WHERE key='installation_id'").fetchone()[0]
        records = [json.loads(row[0]) for row in db.execute('SELECT record_json FROM persona_binding_events ORDER BY sequence DESC')]
    records = [r for r in records if r.get('selector', {}).get('bot_id') == 'bot-3899701587' and not r.get('revoked')]
    roles = {(r['role']['installation_id'], r['role']['subject_id'], r['selector']['bot_id']) for r in records}
    assert len(roles) == 1, 'resolve the active role before changing preferences'
    install, role, bot = roles.pop()
    assert install == installation
    runtime = StorageRuntime.open(data_root=root, installation_id=installation)
    target = ConfigTarget(install, ConfigLayer.ROLE, SubjectRef(install, SubjectKind.BOT, role), bot_id=bot)
    print(json.dumps(apply(runtime, target=target), ensure_ascii=False))
