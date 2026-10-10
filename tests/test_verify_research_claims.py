"""Offline evidence-audit regression tests: never promote retrieval to truth."""
from datetime import datetime, timezone, timedelta
import json
from pathlib import Path
import sys
import tempfile
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parent.parent/'tools'))
import verify_research_claims as audit

SHA='a'*40
PRIMARY='''<html><body><p>GPT-5.5 achieves 71.4% (±8.0%, 1 standard error of the mean), compared to 68.6%</p>
<p>GPT-5.5 completed TLO end-to-end in 2 of 10 attempts.</p>
<p>GPT-5.5 solved the challenge at a cost of $1.73.</p>
<p>GPT-5.5 got stuck on the IT sections rather than the OT-specific steps, so its failure does not tell us how capable it would be.</p></body></html>'''
NOTE='''# Secondary evaluation
95% CI (±1 SE)
The source says ICS/OT attack
 requires different domain knowledge.
71.4% 68.6% 2 of 10 attempts $1.73
'''+''.join(f'### Claim {i}: Test {i}\n- **Quote**: "GPT-5.5 completed TLO\n end-to-end in 2 of 10 attempts."\n\n' for i in range(1,7))
WILLISON='<html>Independent observation.</html>'
def fake_loader(url):
 if url==audit.PRIMARY: return PRIMARY,'p'*64
 if url==audit.WILLISON: return WILLISON,'w'*64
 return NOTE,'n'*64

class EvidenceTests(unittest.TestCase):
 def test_specific_conflicts_are_not_promoted_to_verified(self):
  x=audit.build(SHA,NOTE,PRIMARY,WILLISON,'n'*64,'p'*64,'w'*64,'2026-10-10T08:00:00+00:00')
  self.assertEqual(x['summary']['potentialConflicts'],2)
  self.assertEqual(x['summary']['independentlyVerifiedClaims'],0)
  self.assertEqual(x['summary']['locatedQuotes'],6)
  self.assertEqual(x['publicationState'],'review-required')
  self.assertEqual({c['status'] for c in x['literalAnchors']},{'literal-match-only'})
 def test_no_false_conflict_if_note_avoids_inference(self):
  updated=NOTE.replace('95% CI (±1 SE)','1 standard error').replace('ICS/OT attack\n requires different domain knowledge.','OT capability remains unmeasured.')
  x=audit.build(SHA,updated,PRIMARY,WILLISON,'n','p','w','2026-10-10T08:00:00+00:00')
  self.assertEqual(x['summary']['potentialConflicts'],0)
 def test_stale_and_idempotent_and_failed_network_keeps_report(self):
  with tempfile.TemporaryDirectory() as temp:
   d=Path(temp);watch=d/'watch.json';out=d/'audit.json'
   watch.write_text(json.dumps({'upstreamSha':SHA,'changed':[{'path':audit.NOTE}]}))
   now=datetime(2026,10,10,8,tzinfo=timezone.utc)
   self.assertEqual(audit.run(watch,out,now,fake_loader)['status'],'updated')
   original=out.read_bytes()
   def no_network(url): raise AssertionError('Should skip network on unchanged revision')
   self.assertEqual(audit.run(watch,out,now+timedelta(hours=1),no_network)['status'],'unchanged')
   self.assertEqual(original,out.read_bytes())
   def failure(url):raise OSError('Offline primary source')
   with self.assertRaises(OSError):audit.run(watch,out,now+timedelta(hours=25),failure)
   self.assertEqual(original,out.read_bytes())
 def test_upstream_unrelated_revision_skips_unneeded_audit(self):
  with tempfile.TemporaryDirectory() as temp:
   d=Path(temp);watch=d/'watch.json';out=d/'audit.json';now=datetime(2026,10,10,8,tzinfo=timezone.utc)
   watch.write_text(json.dumps({'upstreamSha':SHA,'changed':[{'path':audit.NOTE}]}))
   audit.run(watch,out,now,fake_loader)
   watch.write_text(json.dumps({'upstreamSha':'b'*40,'changed':[{'path':'source-notes/else.md'}]}))
   self.assertEqual(audit.run(watch,out,now+timedelta(hours=2),lambda _:None)['status'],'unchanged')
 def test_method_revision_invalidates_cached_audit(self):
  with tempfile.TemporaryDirectory() as temp:
   d=Path(temp);watch=d/'watch.json';out=d/'audit.json'
   now=datetime(2026,10,10,8,tzinfo=timezone.utc)
   watch.write_text(json.dumps({'upstreamSha':SHA,'changed':[{'path':audit.NOTE}]}))
   audit.run(watch,out,now,fake_loader)
   stale=json.loads(out.read_text());stale.pop('auditMethodRevision')
   out.write_text(json.dumps(stale))
   self.assertEqual(audit.run(watch,out,now+timedelta(minutes=10),fake_loader)['status'],'updated')
   self.assertEqual(json.loads(out.read_text())['auditMethodRevision'],audit.METHOD_REVISION)
if __name__=='__main__':unittest.main()
