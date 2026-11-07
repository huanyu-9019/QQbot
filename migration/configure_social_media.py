"""Native Jiangsheng engagement settings and existing curated reaction import.

Run on the QQ host. Existing dialogue, learned-media ownership and private
profiles are not bulk-imported into the public reaction catalogue.
"""
import hashlib,io,json,runpy
from datetime import datetime,timezone
from pathlib import Path
from types import SimpleNamespace as NS

from companion_v2.conversation.reply_settings import ReplyConfigurationOwner,configuration_fields
from companion_v2.conversation.segmentation import SegmentationPolicy
from companion_v2.conversation.participation import GroupParticipationConfigurationOwner,configuration_fields as participation_fields
from companion_v2.expression.configuration import ExpressionConfigurationOwner,configuration_fields as learning_fields
from companion_v2.expression.reactions import ReactionLibrary
from companion_v2.storage.semantic import SemanticStore
from companion_v2.foundation.refs import RoleOwnerRef
from companion_v2.execution.models import digest
from companion_v2.conversation.media.models import CapturedImage,ImageDescriptor
from PIL import Image


def write(owner,target,fields,changes):
    known={f.field_id:f for f in fields}
    for k,v in changes.items():known[k].validate(v)
    before=owner.read(target,fields)
    result=owner.write(target,fields,changes=changes,reset=(),expected_revision=before.revision,observed_at=datetime.now(timezone.utc))
    after=owner.read(target,fields)
    assert all(after.fields[k].value==v for k,v in changes.items())
    return list(result.changed_fields)


def configure(runtime,target,root,asset_dir,entries):
    changes={}
    changes['private']=write(ReplyConfigurationOwner(runtime),target,configuration_fields(SegmentationPolicy(),False,0),{'conversation.presentation.private_closing_guard_enabled':False})
    changes['participation']=write(GroupParticipationConfigurationOwner(runtime),target,participation_fields(),{
      'conversation.group_participation.enable_group_social_context':True,
      'conversation.group_participation.enable_group_mood_detection':True,
      'conversation.group_participation.enable_group_interjection':True,
      'conversation.group_participation.group_interject_min_interval_minutes':0,
      'conversation.group_participation.group_interject_max_daily':20})
    changes['learning']=write(ExpressionConfigurationOwner(runtime),target,learning_fields(),{'expression.learning.learning_mode':'light'})
    store=SemanticStore(root)
    owner=digest(['semantic-reaction-role.v1',RoleOwnerRef(runtime.installation_id,target.bot_id,target.role.subject_id)])
    library=ReactionLibrary(NS(store=store,app=NS(messages=None)))
    created=0
    for entry in entries:
        name=entry['file'];assert Path(name).name==name
        path=(asset_dir/name).resolve();assert path.parent==asset_dir.resolve() and not (asset_dir/name).is_symlink()
        data=path.read_bytes()
        with Image.open(io.BytesIO(data)) as image:
            assert image.format=='PNG';image.verify()
        with Image.open(io.BytesIO(data)) as image:w,h=image.size
        captured=CapturedImage(ImageDescriptor(0,'image/png',w,h,len(data),hashlib.sha256(data).hexdigest()),data)
        item,new=library.import_image_with_status(owner,captured,{'name':entry['id'],'description':entry['description'],'visible_text':entry['caption'],'tags':entry['description'].replace('、','；')},collection_source='legacy_migration',enabled=True)
        assert library.captured(item).content==data
        created+=new
    settings=store.settings()
    store.configure({'reactions_enabled':True,'reactions_private_enabled':True,'reactions_group_enabled':True,'reactions_trigger_probability':0.12,'reactions_cooldown_seconds':180,'reactions_collection_private_enabled':False,'reactions_collection_group_enabled':False},settings['revision'])
    assert len(store.list(owner,'reaction',limit=64))>=len(entries)
    return {'changed':changes,'reactionsCreated':created,'reactionsAvailable':len(store.list(owner,'reaction',limit=64))}

if __name__=='__main__':
    values=runpy.run_path('/home/hermes/migration/set_social_preferences.py',run_name='__main__')
    result=configure(values['runtime'],values['target'],values['root'],Path('/var/lib/qq-hermes-media/stickers'),json.loads(Path('/home/hermes/qq-stickers.json').read_text()))
    print(json.dumps(result,ensure_ascii=False))
