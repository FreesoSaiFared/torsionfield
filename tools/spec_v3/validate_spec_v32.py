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
    "spec.css",
    "spec.js",
    "torsionfield-runtime-spec-v3.2.md",
    "manifest.json",
    "source-map.json",
    "requirements.json",
    "editorial-loop.html",
    "editorial-loop.md",
]
missing = [name for name in required_files if not (root / name).exists()]
forksense = [item for item in requirements if item.get("section") == 38]
result = {
    "htmlBytes": len(html.encode("utf-8")),
    "sectionElements": html.count('class="spec-section"'),
    "partOpeners": html.count('class="part-opener"'),
    "ids": len(ids),
    "duplicateIds": duplicates,
    "sourceMap": len(source_map),
    "requirements": len(requirements),
    "forksenseRequirements": len(forksense),
    "missing": missing,
    "hasSection38": 'id="section-38"' in html,
    "hasSection39": 'id="section-39"' in html,
}
print(json.dumps(result, indent=2))
assert result["sectionElements"] == 39
assert result["partOpeners"] == 6
assert not duplicates
assert len(source_map) == 39
assert len(requirements) >= 140
assert len(forksense) >= 22
assert not missing
assert result["hasSection38"] and result["hasSection39"]
