import sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1])); import mesh
class T(unittest.TestCase):
 def test_demo(self):
  with tempfile.TemporaryDirectory() as d:
   x=mesh.demo(Path(d)); self.assertEqual(x["final_stdout"],"42"); self.assertIn("worker-b",x["compile_workers"])
 def test_identity(self):
  self.assertNotEqual(mesh.build_id("a","b","c","d","e"),mesh.build_id("x","b","c","d","e"))
if __name__=="__main__": unittest.main()
