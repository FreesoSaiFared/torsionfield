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
- Dedicated Brave headless profile on i9ES; WebGPU model runs in a Web Worker.
- Private HTTP on 127.0.0.1:8989; CDP on 127.0.0.1:9235.
- Model: SmolLM2-360M-Instruct-q4f32_1-MLC, from WebLLM official config.
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
