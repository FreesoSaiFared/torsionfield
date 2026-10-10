"""Static and evidence-level checks for owner-local hardware-backed WebLLM."""
from pathlib import Path
import json
import unittest

ROOT=Path(__file__).resolve().parent.parent
LOCAL=ROOT/'tools/webllm-personalizer'

class BrowserModelContractTests(unittest.TestCase):
    def test_launcher_pins_verified_vulkan_route(self):
        s=(LOCAL/'prewarm-i9es.sh').read_text()
        self.assertIn('--ozone-platform=x11',s)
        self.assertIn('--use-angle=vulkan',s)
        self.assertIn('Vulkan,VulkanFromANGLE',s)
        self.assertIn('memory.free',s)
        self.assertIn('127.0.0.1',s)
        self.assertIn('normalize-tabs.mjs',s)
    def test_model_is_gpu_gated_and_outputs_remain_drafts(self):
        s=(LOCAL/'src/app.js').read_text()
        self.assertIn("Qwen3.5-2B-q4f32_1-MLC",s)
        self.assertIn("vendor",s)
        self.assertIn("swiftshader",s)
        self.assertIn("TF_READY",s)
        self.assertIn("/no_think",s)
        self.assertIn("DRAFT_FORMAT_INCOMPLETE",s)
        self.assertNotIn("api.openai.com",s)
        self.assertNotIn("public/research/editorial.json",s)
    def test_acceptance_proves_actual_adapter_and_model_text(self):
        s=(LOCAL/'accept-i9es.mjs').read_text()
        self.assertIn("requestAdapter",s)
        self.assertIn("vendor.toLowerCase()!=='nvidia'",s)
        self.assertIn("TF_READY",s)
        self.assertIn("DRAFT_SUBMITTED",s)
        self.assertIn("EDITORIAL_DRAFT_NOT_VERIFIED",s)
    def test_report_distinguishes_warm_and_inference(self):
        report=json.loads((ROOT/'docs/evidence/webllm-nvidia-x11-2026-10-10.json').read_text())
        self.assertEqual(report['actualWebGPU']['vendor'],'nvidia')
        self.assertEqual(report['actualWebGPU']['architecture'],'ampere')
        self.assertEqual(report['actualWebGPU']['computeOutput'],42)
        self.assertFalse(report['actualWebGPU']['shaderF16'])
        self.assertEqual(report['repeatedAcceptance']['passes'],3)
        self.assertTrue(report['coldRestart']['accepted'])
        self.assertIn('not',report['modelOutput'].lower())
    def test_duplicate_close_requires_idle_state(self):
        s=(LOCAL/'normalize-tabs.mjs').read_text()
        self.assertIn("hidden.length===1&&active.length===1",s)
        self.assertIn("t.disabled===false",s)
        self.assertIn("refusing to close unknown model state",s)

if __name__=="__main__":unittest.main()
