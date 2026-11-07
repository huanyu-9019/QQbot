"""High group engagement via native owners; no provider/persona/account changes."""
import runpy,json
from datetime import datetime,timezone
from companion_v2.conversation.participation import GroupParticipationConfigurationOwner,configuration_fields

if __name__=='__main__':
 values=runpy.run_path('/home/hermes/migration/set_social_preferences.py',run_name='__main__')
 runtime,target=values['runtime'],values['target'];owner=GroupParticipationConfigurationOwner(runtime);fields=configuration_fields();before=owner.read(target,fields)
 changes={'conversation.group_participation.enable_group_interjection':True,
          'conversation.group_participation.group_interject_min_interval_minutes':0,
          'conversation.group_participation.group_interject_max_daily':20}
 result=owner.write(target,fields,changes=changes,reset=(),expected_revision=before.revision,observed_at=datetime.now(timezone.utc))
 after=owner.read(target,fields);assert all(after.fields[k].value==v for k,v in changes.items())
 print(json.dumps({'groupParticipation':{'changed':list(result.changed_fields),'before':{k:before.fields[k].value for k in changes},'after':{k:after.fields[k].value for k in changes}}}))
