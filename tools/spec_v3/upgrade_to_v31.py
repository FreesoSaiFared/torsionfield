from pathlib import Path
import shutil, json, subprocess, sys

ROOT = Path(r"E:\Transductive_MCP_Work\torsionfield-site")
source = ROOT / "source-spec-v2.4.txt"
source_v31 = ROOT / "source-spec-v3.1.txt"
section_path = ROOT / "participant-edge-plane-section.txt"
gen = ROOT / "tools" / "spec_v3" / "generate_spec.py"
val = ROOT / "tools" / "spec_v3" / "validate_spec.py"

for path, backup_name in [
    (source, "source-spec-v2.4.pre-edge.txt"),
    (gen, "generate_spec.v3.0.py"),
    (val, "validate_spec.v3.0.py"),
]:
    backup = path.with_name(backup_name)
    if not backup.exists():
        shutil.copy2(path, backup)

base_source = source.with_name("source-spec-v2.4.pre-edge.txt")
if not base_source.exists():
    raise RuntimeError("Immutable v3.0 source backup not found")
text = base_source.read_text(encoding="utf-8-sig")
section = section_path.read_text(encoding="utf-8").strip()
if "37. REFERENCES" not in text:
    raise RuntimeError("References marker not found in v3.0 baseline")
text = text.replace("37. REFERENCES", section + "\n\n38. REFERENCES", 1)
source_v31.write_text(text, encoding="utf-8")

g = gen.read_text(encoding="utf-8")
g = g.replace('SOURCE = ROOT / "source-spec-v2.4.txt"', 'SOURCE = ROOT / "source-spec-v3.1.txt"')
g = g.replace('VERSION = "3.0"', 'VERSION = "3.1"')
g = g.replace('DATE = "1 August 2026"', 'DATE = "2 August 2026"')
g = g.replace('("V", "Participatory work, verification, and governance", range(30, 37)),\n    ("VI", "References", range(37, 38)),', '("V", "Participatory work, verification, and governance", range(30, 38)),\n    ("VI", "References", range(38, 39)),')
g = g.replace('37: "Lists the primary documentation and source projects used as implementation and interoperability references.",', '37: "Defines persistent participant-owned edge cells, separated authority, encrypted state, portable capabilities, and governed deployment.",\n    38: "Lists the primary documentation and source projects used as implementation and interoperability references.",')
g = g.replace('if 25 <= number <= 32 or number in {34, 35}:', 'if 25 <= number <= 32 or number in {34, 35, 37}:')
g = g.replace('list(range(1, 38))', 'list(range(1, 39))')
g = g.replace('torsionfield-runtime-spec-v3.0', 'torsionfield-runtime-spec-v3.1')
g = g.replace('All 37 source sections are retained and mapped.', 'All 38 sections are retained and mapped.')
g = g.replace('complete v2.4 specification', 'complete v2.4 specification plus the Participant Edge amendment')
g = g.replace('"version": "2.4",', '"version": "2.4+participant-edge",')
g = g.replace('Source sections retained: {section_count}/37', 'Source sections retained: {section_count}/38')
g = g.replace('Source sections retained: {section_count}/37', 'Source sections retained: {section_count}/38')
g = g.replace('37 complete source sections', '38 complete sections')
gen.write_text(g, encoding="utf-8")
v = val.read_text(encoding="utf-8")
v = v.replace('torsionfield-runtime-spec-v3.0.md', 'torsionfield-runtime-spec-v3.1.md')
v = v.replace('"hasSection37": \'id="section-37"\' in html,', '"hasSection37": \'id="section-37"\' in html,\n    "hasSection38": \'id="section-38"\' in html,')
v = v.replace('assert result["sectionElements"] == 37', 'assert result["sectionElements"] == 38')
v = v.replace('assert len(source_map) == 37', 'assert len(source_map) == 38')
v = v.replace('assert len(requirements) > 0', 'assert len(requirements) >= 118')
v = v.replace('assert result["hasSection36"] and result["hasSection37"]', 'assert result["hasSection36"] and result["hasSection37"] and result["hasSection38"]')
val.write_text(v, encoding="utf-8")

subprocess.run([sys.executable, str(gen)], check=True, cwd=ROOT)
subprocess.run([sys.executable, str(val)], check=True, cwd=ROOT)
req_path = ROOT / "public" / "spec" / "requirements.json"
reqs = json.loads(req_path.read_text(encoding="utf-8"))
edge = [r for r in reqs if r.get("section") == 37]
evidence = {
    "schema": "torsionfield.participant-edge-integration/1",
    "version": "3.1",
    "sections": 38,
    "requirements": len(reqs),
    "edgeRequirements": len(edge),
    "firstEdgeRequirement": edge[0]["requirementId"] if edge else None,
    "lastEdgeRequirement": edge[-1]["requirementId"] if edge else None,
    "providerBinding": "cloudflare-oauth-cell/1",
    "status": "normative-staged-target",
    "generalAvailability": False,
    "scriptCatFirstCriticalPathPreserved": True,
}
(ROOT / "public" / "spec" / "participant-edge-integration.json").write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
print(json.dumps(evidence, indent=2))