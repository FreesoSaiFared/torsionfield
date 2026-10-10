"""Offline checks for local-only proposal generation and source extraction."""
import io
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parent.parent/"tools"))
import editorial_draft_local as draft

class FakeResponse:
 def __init__(self,url,body):self.url=url;self.body=body
 def __enter__(self):return self
 def __exit__(self,*args):return False
 def geturl(self):return self.url
 def read(self,limit):return self.body[:limit]

class EditorialDraftTests(unittest.TestCase):
 def test_extracts_only_source_intro(self):
  url="https://example.org/research/item"
  html=("<html><head><meta name='description' content='Original research with a narrowly scoped example.'></head>"
        "<body><p>Researchers observed a problem with how agent workflows treated external instructions. "
        "They documented the exact point where the tool accepted the input.</p></body></html>").encode()
  with patch.object(draft,"urlopen",return_value=FakeResponse(url,html)):
   excerpt,digest=draft.source_excerpt(url)
  self.assertIn("Original research",excerpt)
  self.assertIn("agent workflows",excerpt)
  self.assertEqual(len(digest),64)
 def test_rejects_cross_publisher_redirect(self):
  with patch.object(draft,"urlopen",return_value=FakeResponse("https://unrelated.org/",b"x")):
   with self.assertRaisesRegex(ValueError,"redirected"):
    draft.source_excerpt("https://example.org/research/item")
 def test_drafts_cannot_publish_directly(self):
  self.assertNotEqual(draft.DEFAULT_OUTPUT,draft.EDITORIAL)
  self.assertIn("/.runtime/",str(draft.DEFAULT_OUTPUT))
  self.assertEqual(draft.MODEL,"tf-qwen25-7b:latest")
if __name__=="__main__":unittest.main()
