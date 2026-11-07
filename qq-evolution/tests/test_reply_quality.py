
import json,sys,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).parents[1]))
from metrics import aggregate,reply_quality_issue,overdue_turns
from collector import sanitize_record
import agent,supervisor
class ReplyQualityTests(unittest.TestCase):
 def test_habitual_acknowledgement_metric_counts_ellipsis_and_question_openings(self):
  events=[]
  for i,text in enumerate(['嗯……我在呢。','嗯？怎么啦。','嗯，在。','嗯……知道了。','嗯，好。']):
   events.extend([dict(direction='incoming',kind='private',sessionHash='a'*64,turnId=str(i),timestamp=i*2,text='你好'),
                  dict(direction='delivered',kind='private',sessionHash='a'*64,turnId=str(i),timestamp=i*2+1,text=text)])
  self.assertEqual(aggregate(events)['habitualAcknowledgementSessions'],1)
 def test_identity_conflict_survives_collection_and_is_counted(self):
  row=sanitize_record(dict(timestamp=1,direction='quality',kind='group',sessionHash='a'*64,text='secret name',outcome='sender_identity_mismatch',turnId='x'))
  self.assertIsNotNone(row)
  self.assertEqual(row['text'],'')
  report=aggregate([row])
  self.assertEqual(report['blockedIdentityReplies'],1)
  self.assertEqual(report['blockedQualityReplies'],1)
 def test_habitual_acknowledgement_counts_private_turns_not_split_or_voice_duplicates(self):
  events=[dict(direction='delivered',kind='private',sessionHash='person-a',turnId=str(i),text=text)
          for i,text in enumerate(['嗯，在。','嗯，知道了。','嗯嗯，明天见。','嗯，好呀。','今天怎么样？'])]
  self.assertEqual(aggregate(events)['habitualAcknowledgementSessions'],1)
  self.assertEqual(aggregate(events[:2]*4)['habitualAcknowledgementSessions'],0)
  self.assertEqual(aggregate([{**e,'sessionHash':str(i)} for i,e in enumerate(events)])['habitualAcknowledgementSessions'],0)
  self.assertEqual(aggregate([{**e,'kind':'group'} for e in events])['habitualAcknowledgementSessions'],0)
 def test_queued_learning_notice_stays_unacknowledged_without_error(self):
  import tempfile
  from daemon import StateStore
  with tempfile.TemporaryDirectory() as d:
   state=Path(d)/'state.json'
   (Path(d)/'learning-records.jsonl').write_text(json.dumps({'iteration':1,'reason':'保留经过验证的回复边界并继续观察','updated':'learning_record'}),encoding='utf-8')
   with patch.object(supervisor,'STATE',state),patch.object(supervisor,'publish_event',return_value=False):
    supervisor.flush_learning_notices()
   self.assertEqual(StateStore(Path(d)/'learning-notice-receipts.json').load(),{})

 def test_counts_unpaired_split_and_voice_leaks_and_blocked_attempts(self):
  events=[{'direction':'delivered','turnId':'x','text':'Initial assessment: The user expresses aimlessness.'},
    {'direction':'delivered','turnId':'x','media':'voice','text':'The interaction involves a direct question.'},
    {'direction':'quality','turnId':'y','outcome':'analysis_leak'}]
  q=aggregate(events);self.assertEqual(q['analysisLeaks'],2);self.assertEqual(q['blockedQualityReplies'],1)
 def test_english_context_and_short_words(self):
  paragraph='A lovely day with friends and family walking in a park beside the river. '*4
  self.assertEqual(reply_quality_issue(paragraph,'你好'),'unexpected_english')
  self.assertIsNone(reply_quality_issue(paragraph,'请用英文回答'))
  self.assertIsNone(reply_quality_issue('OK MyGO HTTP 503'))
 def test_collector_preserves_safe_quality_metadata(self):
  row=sanitize_record(dict(timestamp=1,direction='quality',kind='group',sessionHash='a'*64,text='internal',outcome='analysis_leak',turnId='x'))
  self.assertEqual(row['outcome'],'analysis_leak');self.assertEqual(row['text'],'')
 def test_quality_does_not_complete_pending_turn(self):
  events=[dict(version=2,direction='incoming',turnId='x',timestamp=0),dict(version=2,direction='quality',turnId='x',timestamp=1,outcome='analysis_leak')]
  self.assertEqual(overdue_turns(events,now_ms=200000),1)
 def test_single_critical_reply_reaches_evaluator(self):
  calls=[]
  self.assertEqual(supervisor.assess_events([dict(direction='delivered',turnId='x',text='Initial assessment: bad')],Path('/repo'),lambda *a,**kw:(calls.append(a) or {'category':'error'},'patch')),'patch')
  self.assertEqual(len(calls),1)
 def test_critical_leak_cannot_be_marked_no_change(self):
  with self.assertRaises(ValueError):agent.evaluate_and_propose([dict(direction='delivered',turnId='x',text='Initial assessment: bad')],runner=lambda *a:json.dumps(dict(finding=None,diff='')))
 def test_prompt_contains_quality_evidence(self):
  calls=[]
  def runner(args,prompt,cwd):calls.append(prompt);return json.dumps(dict(finding=None,diff=''))
  agent.evaluate_and_propose([dict(direction='quality',turnId='x',outcome='analysis_leak')],runner=runner)
  self.assertIn('"blockedQualityReplies": 1',calls[0])
 def test_monitor_detects_during_cooldown_before_notice_publication(self):
  import tempfile,os
  from daemon import StateStore
  import time
  with tempfile.TemporaryDirectory() as d:
   state=Path(d)/'state.json';StateStore(state).save({'lastRun':int(time.time())})
   events=[dict(direction='delivered',turnId='x',timestamp=int(time.time()*1000),text='Initial assessment: bad')]
   with patch.multiple(supervisor,STATE=state,LOCK=Path(d)/'lock'),patch.object(supervisor,'fetch_remote_events',return_value=events),patch.object(supervisor,'record_monitor_health') as report,patch.object(supervisor,'push_archive'),patch.object(supervisor,'flush_learning_notices'),patch.object(supervisor,'iteration_due',return_value=False),patch.object(supervisor,'assess_events',return_value=''):
    supervisor.run_cycle()
    self.assertEqual(report.call_args_list[0].kwargs['quality']['analysisLeaks'],1)
    self.assertEqual(report.call_args_list[0].kwargs['qualityStatus'],'degraded')
 def test_failed_notice_does_not_block_a_full_backlog(self):
  import tempfile
  with tempfile.TemporaryDirectory() as d:
   state=Path(d)/'state.json'
   rows=[dict(iteration=i,reason='这次复盘识别到了需要改进的问题',updated=False) for i in range(10)]
   (Path(d)/'learning-records.jsonl').write_text('\n'.join(json.dumps(x) for x in rows),encoding='utf-8')
   with patch.object(supervisor,'STATE',state),patch.object(supervisor,'publish_event',side_effect=RuntimeError('offline')) as publish:
    supervisor.flush_learning_notices();self.assertEqual(publish.call_count,1)
if __name__=='__main__':unittest.main()
