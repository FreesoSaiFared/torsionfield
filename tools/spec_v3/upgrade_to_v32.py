from pathlib import Path
import shutil, json, subprocess, sys

ROOT = Path(r"E:\Transductive_MCP_Work\torsionfield-site")
base_source = ROOT / "source-spec-v3.1.txt"
source_v32 = ROOT / "source-spec-v3.2.txt"
section_path = ROOT / "forksense-section.txt"
gen = ROOT / "tools" / "spec_v3" / "generate_spec.py"
val = ROOT / "tools" / "spec_v3" / "validate_spec.py"

for path, backup_name in [
    (gen, "generate_spec.v3.1.py"),
    (val, "validate_spec.v3.1.py"),
]:
    backup = path.with_name(backup_name)
    if not backup.exists():
        shutil.copy2(path, backup)

text = base_source.read_text(encoding="utf-8-sig")
section = section_path.read_text(encoding="utf-8").strip()
if "38. REFERENCES" not in text:
    raise RuntimeError("References marker not found in v3.1 source")
text = text.replace("38. REFERENCES", section + "\n\n39. REFERENCES", 1)
source_v32.write_text(text, encoding="utf-8")

g = gen.read_text(encoding="utf-8")
g = g.replace('SOURCE = ROOT / "source-spec-v3.1.txt"', 'SOURCE = ROOT / "source-spec-v3.2.txt"')
g = g.replace('VERSION = "3.1"', 'VERSION = "3.2"')
g = g.replace('("V", "Participatory work, verification, and governance", range(30, 38)),\n    ("VI", "References", range(38, 39)),', '("V", "Participatory work, verification, and governance", range(30, 39)),\n    ("VI", "References", range(39, 40)),')
g = g.replace('38: "Lists the primary documentation and source projects used as implementation and interoperability references.",', '38: "Defines adaptive repository intelligence, rejected-proposal and fork analysis, temporal graph memory, and evidence-backed external-code selection.",\n    39: "Lists the primary documentation and source projects used as implementation and interoperability references.",')
g = g.replace('number in {34, 35, 37}', 'number in {34, 35, 37, 38}')
g = g.replace('list(range(1, 39))', 'list(range(1, 40))')
g = g.replace('torsionfield-runtime-spec-v3.1', 'torsionfield-runtime-spec-v3.2')
g = g.replace('<a href="/spec/torsionfield-runtime-spec-v3.0-print.pdf">PDF</a>\n    ', '')
g = g.replace('All 38 sections are retained and mapped.', 'All 39 sections are retained and mapped.')
g = g.replace('All 38 sections are retained and mapped.', 'All 39 sections are retained and mapped.')
g = g.replace('Source sections retained: {section_count}/38', 'Source sections retained: {section_count}/39')
g = g.replace('Source sections retained: {section_count}/38', 'Source sections retained: {section_count}/39')
g = g.replace('38 complete sections', '39 complete sections')

g = g.replace('"version": "2.4+participant-edge",', '"version": "2.4+participant-edge+forksense",')
g = g.replace('This edition rewrites the complete v2.4 specification plus the Participant Edge amendment plus the Participant Edge amendment plus the Participant Edge amendment', 'This edition rewrites the complete v2.4 specification plus the Participant Edge Plane and ForkSense amendments')
g = g.replace('Complete v2.4 specification</dd>', 'Complete v2.4 specification plus Participant Edge Plane and ForkSense amendments</dd>')
g = g.replace('all 37 sections.', 'all 39 sections.')
g = g.replace('all 38 sections.', 'all 39 sections.')
g = g.replace('for all 37 sections.', 'for all 39 sections.')
g = gen.write_text(g, encoding="utf-8")

v = val.read_text(encoding="utf-8")
v = v.replace('torsionfield-runtime-spec-v3.1.md', 'torsionfield-runtime-spec-v3.2.md')
v = v.replace('"hasSection38": \'id="section-38"\' in html,', '"hasSection38": \'id="section-38"\' in html,\n    "hasSection39": \'id="section-39"\' in html,', 1)
while v.count('"hasSection38"') > 1:
    pos = v.rfind('    "hasSection38"')
    end = v.find('\n', pos) + 1
    v = v[:pos] + v[end:]
v = v.replace('assert result["sectionElements"] == 38', 'assert result["sectionElements"] == 39')
v = v.replace('assert len(source_map) == 38', 'assert len(source_map) == 39')
v = v.replace('assert len(requirements) >= 118', 'assert len(requirements) >= 140')
v = v.replace('result["hasSection38"]', 'result["hasSection38"] and result["hasSection39"]', 1)
val.write_text(v, encoding="utf-8")

subprocess.run([sys.executable, str(gen)], check=True, cwd=ROOT)
subprocess.run([sys.executable, str(val)], check=True, cwd=ROOT)
req_path = ROOT / "public" / "spec" / "requirements.json"
reqs = json.loads(req_path.read_text(encoding="utf-8"))
forksense = [r for r in reqs if r.get("section") == 38]
evidence = {
    "schema": "torsionfield.forksense-integration/1",
    "version": "3.2",
    "sections": 39,
    "requirements": len(reqs),
    "forksenseRequirements": len(forksense),
    "firstForkSenseRequirement": forksense[0]["requirementId"] if forksense else None,
    "lastForkSenseRequirement": forksense[-1]["requirementId"] if forksense else None,
    "outputContract": "IntegrationIntelligencePacket/1",
    "graphStoreContract": "RepositoryGraphStore/1",
    "referenceGraphProvider": "cozo-local/1",
    "status": "staged-external-code-integration-gate",
    "generalAvailability": False,
    "scriptCatFirstCriticalPathPreserved": True,
    "publicSurface": "https://forksense.torsionfield.de/",
}
(ROOT / "public" / "spec" / "forksense-integration.json").write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
print(json.dumps(evidence, indent=2))
