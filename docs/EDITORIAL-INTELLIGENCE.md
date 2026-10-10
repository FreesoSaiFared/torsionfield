# Torsionfield research editorial protocol

Torsionfield presents its **own plain-language interpretations**, not copied
headlines. The source title always appears smaller immediately below ours.
A short "why this matters to Torsionfield" explanation follows each title.

## Review gate
- Curated interpretations: public/research/editorial.json.
- New or changed source titles go to tools/editorial_backlog.py.
- Every source is attributed and linked. No silent auto-publication of drafts.
- Review the article before stating a specific result; indicate uncertainty.
- Torsionfield authors may correct mistaken public research constructively:
  verify the primary source, locate the error, check existing reports, propose
  a precise correction, and attribute the original author. No promotional spam.
- Initial correction: steveash/hitchhikers-guide-to-ai-native-engineering#4049.
- The site reads RSS and editorial manifests from our public GitHub repository
  through a cached Cloudflare Worker endpoint, so GitHub updates need no deploy.

## Opportunistic browser-local WebLLM
The owner wants local WebLLM models prewarmed while other work continues,
then available for quick editorial suggestions and reader personalization.
Do not block the page, send private inputs to external inference servers,
or present generated suggestions as verified claims.

The experimental **owner-side** i9ES lane is:
- Run: bash tools/webllm-personalizer/prewarm-i9es.sh
- Dedicated Brave X11 profile on i9ES, using NVIDIA Vulkan/ANGLE; model runs in a Web Worker.
- Private HTTP on 127.0.0.1:8989; CDP on 127.0.0.1:9235.
- Default model: Qwen3.5-2B-q4f32_1-MLC (WebLLM 0.2.85); this works without shader-f16.
- First session downloads model files; later sessions reuse the browser cache.
- Local workbench input may be a source headline and a short verified excerpt.
- Generated output is a candidate; humans/independent evidence must approve it.
- Public visitors do not silently download hundreds of MB of model weights.
- If no local WebGPU adapter, leave already-reviewed content available.

This is a separate local model workflow, not a claim that every browser has
working WebGPU acceleration. Verify runtime readiness and generation explicitly.

## Verified owner-side local drafting fallback (10 October 2026)
Browser WebLLM weights cache successfully and a simple WebGPU compute test succeeds,
but the initial SmolLM2 WebLLM generation attempts lost their GPU device. A separate
NVIDIA PRIME browser probe proved the RTX 3060 as its primary GPU, though the
larger browser model inference still failed. Model initialization is not generation proof.

For practical editorial drafting use the already-installed, local Ollama model:
`python3 tools/editorial_draft_local.py --limit 4` on i9ES.
`tf-qwen25-7b:latest` was verified as 100% GPU on the RTX 3060 and generated
122 tokens in 2.52 seconds. The tool reads publisher introductions over HTTPS,
creates a local source-hashed JSON draft under `.runtime/`, and **never publishes**.
The generated suggestions must be rewritten and checked against the publisher's
text before modifying `public/research/editorial.json`. The Qwen output often
summarizes events rather than explaining what our engineering stack can learn.
Preserve first-party relevance, publisher provenance, cautious attribution and
explicit uncertainty. `tools/editorial_backlog.py` identifies remaining gaps.

## Correction: browser GPU identity is not WebGPU adapter identity
A later, stricter adapter probe on 10 October 2026 established that the X11
Brave profile can list NVIDIA RTX 3060 (vendor ID 4318) as its **primary browser
GPU**, while `navigator.gpu.requestAdapter({powerPreference:'high-performance'})`
selected **Google SwiftShader**, architecture `swiftshader`. The WebGPU compute
result 42 therefore did NOT prove NVIDIA acceleration. After device loss the
adapter may instead be null. A separate SmolLM2-135M/f16 test could not load
because SwiftShader did not expose `shader-f16`. No WebLLM text generation has
passed acceptance. The test browser/server were stopped; cached profiles kept.

The workbench now refuses model initialization when the selected adapter is
software or unverified. The readiness checker records browser-primary NVIDIA
separately from actual WebGPU vendor/architecture and marks production inference
ready only after hardware selection **and** a verified text-generation result.
The native Ollama Qwen 7B fallback remains independently proven at 100% NVIDIA
GPU. Do not confuse `gpu.devices[0].vendorId` with the selected WebGPU adapter.

## Accepted NVIDIA WebGPU in Brave — 10 October 2026 (supersedes historical failure)

The earlier SwiftShader findings above describe the **old browser configuration**.
They are preserved as negative controls, not the current i9ES status.

**Verified positive path:** Brave 155, Ubuntu 24.04 X11, NVIDIA RTX 3060,
driver 580.178.04, isolated model profile, NVIDIA PRIME offload and:

- --enable-unsafe-webgpu
- --ozone-platform=x11
- --use-angle=vulkan
- --enable-features=Vulkan,VulkanFromANGLE

These X11 flags match the GPUWeb implementation notes. Crucially,
navigator.gpu.requestAdapter({powerPreference:'high-performance'}).info
reports **vendor nvidia, architecture ampere**. Browser SystemInfo
reporting NVIDIA as primary GPU was insufficient and previously misleading.
The browser executes a WebGPU compute shader returning 42 from input 41.

**Model:** Qwen3.5-2B-q4f32_1-MLC, WebLLM 0.2.85. The adapter does not expose
shader-f16; use the q4f32 model (not q4f16). The local workbench now requests
the no-thinking response mode, removes thought delimiters from its draft,
requires explicit TITLE and RELEVANCE fields, and does not publish any output.

**Acceptance:** Restarted the isolated browser through its canonical
prewarm-i9es.sh script. The script identified and closed exactly one idle
duplicate tab. After cached model load, the source-controlled accept-i9es.mjs
passed both a literal TF_READY smoke and a complete editorial draft.

Restart-run timings: 1.284 s for smoke, 2.261 s for editorial draft.
Three additional warm trials: 3/3 passed; smoke median 0.320 s,
editorial median 3.017 s. These are observed on i9ES, not general benchmarks.
Evidence: docs/evidence/webllm-nvidia-x11-2026-10-10.json

**Runbook, on the authorized i9ES desktop:**
1. bash tools/webllm-personalizer/prewarm-i9es.sh
2. node tools/webllm-personalizer/check-gpu.mjs 9235
3. node tools/webllm-personalizer/accept-i9es.mjs

Local HTTP server 127.0.0.1:8989 and CDP 127.0.0.1:9235 are private
to i9ES; the public site NEVER automatically downloads model weights.
The prewarm script skips startup if NVIDIA X11 cannot be proven or less
than 4.5 GB free GPU memory is available. Running inference may still
consume significant GPU memory; the existing Ollama Qwen 7B remains a
separately verified fallback.

**Publication is independently gated:** acceptance checks that the response
has the requested format. It does not certify that generated scientific or
security claims are true. First-party blog interpretations require source
review before moving from private drafts to curated editorial JSON.
