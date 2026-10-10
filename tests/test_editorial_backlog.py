"""Publication gating: unreviewed or changed source titles must stay in queue."""
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parent.parent/'tools'))
from editorial_backlog import candidates

class EditorialBacklogTests(unittest.TestCase):
    def test_review_gate_and_source_title_changes(self):
        url='https://blog.example.com/topic'
        feed={'items':[{'source':'Lab','url':url,'title':'New title'},
                       {'source':'Lab','url':'https://blog.example.com/new','title':'Another article'}]}
        editor={'entries':{url:{'sourceTitleAtReview':'Old title','editorialStatus':'reviewed','headline':'Our title','relevance':'Why it matters'}}}
        pending=candidates(feed,editor)
        self.assertEqual(len(pending),2)
        self.assertEqual(pending[0]['reason'],'source-updated')
        editor['entries'][url]['sourceTitleAtReview']='New title'
        self.assertEqual(len(candidates(feed,editor)),1)
        self.assertEqual(candidates(feed,editor)[0]['reason'],'new-source')
    def test_untrusted_url_is_not_queued(self):
        self.assertEqual(candidates({'items':[{'url':'javascript:alert(1)','title':'X'}]},{}),[])
if __name__=='__main__':unittest.main()
