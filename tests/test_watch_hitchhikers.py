"""Offline contract tests for upstream change detection and source-audit safety."""
import json
from pathlib import Path
import sys
import tempfile
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
from tools import watch_hitchhikers as watch
A="a"*40
B="b"*40

def commit(sha):
    return {"sha":sha,"commit":{"committer":{"date":"2026-10-10T07:00:00Z"}}}
def compare(sha,files):
    return {"status":"ahead","total_commits":1,"head_commit":{"sha":sha},
            "files":files}

class SourceWatchTests(unittest.TestCase):
    def test_initial_ingestion_is_idempotent(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/"watch.json"
            api=lambda url: commit(A)
            self.assertEqual(watch.run(path,api)["status"],"bootstrapped")
            raw=path.read_bytes()
            self.assertEqual(watch.run(path,api)["status"],"unchanged")
            self.assertEqual(raw,path.read_bytes())
            self.assertEqual(json.loads(raw)["trackedNote"]["path"],watch.NOTE)
    def test_changed_file_ranking_and_provenance(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/"watch.json"
            watch.run(path,lambda _:commit(A))
            def api(url):
                if url.endswith("/commits/main"):return commit(B)
                return compare(B,[{"filename":watch.NOTE,"status":"modified"},
                                  {"filename":"agents/ASSAYER.md","status":"modified"},
                                  {"filename":"source-notes/gardening-flowers.md","status":"added"}])
            status=watch.run(path,api)
            record=json.loads(path.read_text())
            self.assertEqual(status["relevantCount"],2)
            self.assertTrue(record["reviewNeeded"])
            self.assertEqual(record["previousSha"],A)
            self.assertTrue(all("content" not in e for e in record["events"]))
    def test_incomplete_compare_cannot_advance_cursor(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/"watch.json"
            watch.run(path,lambda _:commit(A))
            before=path.read_bytes()
            def api(url):
                return commit(B) if url.endswith("/commits/main") else {"status":"behind","files":[]}
            with self.assertRaises(ValueError):watch.run(path,api)
            self.assertEqual(before,path.read_bytes())
    def test_selective_relevance(self):
        self.assertEqual(watch.priority(watch.NOTE),100)
        self.assertGreater(watch.priority("source-notes/blog-agent-evaluation.md"),0)
        self.assertEqual(watch.priority("source-notes/flowers.md"),0)

if __name__=="__main__":unittest.main()
