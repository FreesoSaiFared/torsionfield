import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import mesh

spec = importlib.util.spec_from_file_location("mesh_worker", ROOT / "worker.py")
worker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(worker)


class WorkerTest(unittest.TestCase):
    def test_claim_execute_publish(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            spool = root / "spool"
            cas = mesh.CAS(root / "coord-cas")
            cxx = "/usr/bin/clang++" if Path("/usr/bin/clang++").exists() else "/usr/bin/g++"
            bid = mesh.build_id("src", "deps", "tool", "sysroot", "gn")
            source = b'int main(){return 0;}\n'
            action = mesh.action(
                bid,
                [cxx, "-x", "c++", "a.cc", "-c", "-o", "a.o"],
                {"a.cc": cas.put(source)},
                ["a.o"],
            )
            worker.ensure_dirs(spool)
            bundle = spool / "incoming" / "a.tgz"
            mesh.make_bundle(action, cas, bundle)
            receipt = worker.process_one(
                spool, "vm-test", bid, root / "worker-root"
            )
            self.assertEqual(receipt["status"], "DONE")
            self.assertTrue((spool / "results" / "a.result.tgz").exists())
            self.assertFalse(bundle.exists())

    def test_wrong_build_identity_is_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            spool = root / "spool"
            cas = mesh.CAS(root / "coord-cas")
            bid = mesh.build_id("src", "deps", "tool", "sysroot", "gn")
            action = mesh.action(bid, ["/bin/true"], {}, [])
            worker.ensure_dirs(spool)
            bundle = spool / "incoming" / "bad.tgz"
            mesh.make_bundle(action, cas, bundle)
            receipt = worker.process_one(
                spool, "vm-test", "different-build", root / "worker-root"
            )
            self.assertEqual(receipt["status"], "FAILED")
            self.assertIn("BUILD_ID_MISMATCH", receipt["error"])
            self.assertTrue((spool / "failed" / "vm-test--bad.tgz").exists())


if __name__ == "__main__":
    unittest.main()
