from pathlib import Path
import json
import re

root = Path(r"E:\Transductive_MCP_Work\torsionfield-site\public\spec")
html = (root / "index.html").read_text(encoding="utf-8")
ids = re.findall(r'\bid="([^"]+)"', html)
duplicates = sorted({value for value in ids if ids.count(value) > 1})
source_map = json.loads((root / "source-map.json").read_text(encoding="utf-8"))
requirements = json.loads((root / "requirements.json").read_text(encoding="utf-8"))
required_files = [
    "spec.css", "spec.js", "torsionfield-runtime-spec-v3.1.md",
    "manifest.json", "source-map.json", "requirements.json",
    "editorial-loop.html", "editorial-loop.md",
]
missing = [name for name in required_files if not (root / name).exists()]
result = {
    "htmlBytes": len(html.encode("utf-8")),
    "sectionElements": html.count('class="spec-section"'),
    "partOpeners": html.count('class="part-opener"'),
    "ids": len(ids),
    "duplicateIds": duplicates,
    "sourceMap": len(source_map),
    "requirements": len(requirements),
    "missing": missing,
    "hasSection36": 'id="section-36"' in html,
    "hasSection37": 'id="section-37"' in html,
    "hasSection38": 'id="section-38"' in html,
    "hasSection38": 'id="section-38"' in html,
    "hasSection38": 'id="section-38"' in html,
}
print(json.dumps(result, indent=2))
assert result["sectionElements"] == 38
assert result["partOpeners"] == 6
assert not duplicates
assert len(source_map) == 38
assert len(requirements) >= 118
assert not missing
assert result["hasSection36"] and result["hasSection37"] and result["hasSection38"] and result["hasSection38"] and result["hasSection38"]
