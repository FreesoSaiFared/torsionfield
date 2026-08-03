from pathlib import Path

p = Path(r"E:\Transductive_MCP_Work\torsionfield-site\tools\spec_v3\generate_spec.py")
s = p.read_text(encoding="utf-8")
old = '</a>`n    <a href="/spec/torsionfield-runtime-spec-v3.0.md"'
new = '</a>\n    <a href="/spec/torsionfield-runtime-spec-v3.0.md"'
if old not in s:
    raise SystemExit("literal navigation separator not found")
p.write_text(s.replace(old, new, 1), encoding="utf-8")
print("fixed")
