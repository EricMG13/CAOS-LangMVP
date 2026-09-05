"""Render frontend-a0-code-audit.md as the artifact page (scratch; not part of the tree)."""
import html
import re
import sys
from pathlib import Path

src = Path(sys.argv[1]).read_text()
out = Path(sys.argv[2])

def inline(text: str) -> str:
    text = html.escape(text, quote=False)
    text = re.sub(r"`([^`]+)`", r"<code>\1</code>", text)
    text = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2">\1</a>', text)
    return text

lines = src.split("\n")
body: list[str] = []
sections: list[tuple[str, str]] = []
findings: list[tuple[str, str, str]] = []
i = 0
in_list = False
para: list[str] = []

def flush_para():
    global para
    if para:
        body.append(f"<p>{inline(' '.join(para))}</p>")
        para = []

def close_list():
    global in_list
    if in_list:
        body.append("</ul>")
        in_list = False

while i < len(lines):
    line = lines[i]
    if line.startswith("```"):
        flush_para(); close_list()
        block = []
        i += 1
        while i < len(lines) and not lines[i].startswith("```"):
            block.append(lines[i]); i += 1
        body.append(f"<pre><code>{html.escape(chr(10).join(block))}</code></pre>")
        i += 1
        continue
    if line.startswith("| "):
        flush_para(); close_list()
        rows = []
        while i < len(lines) and lines[i].startswith("|"):
            rows.append(lines[i]); i += 1
        cells = [[c.strip() for c in r.strip().strip("|").split("|")] for r in rows]
        head = cells[0]
        rest = [r for r in cells[2:]] if len(cells) > 1 and set(cells[1][0]) <= set("-: ") else cells[1:]
        thead = "".join(f"<th>{inline(c)}</th>" for c in head)
        tbody = "".join("<tr>" + "".join(f"<td>{inline(c)}</td>" for c in r) + "</tr>" for r in rest)
        body.append(f'<div class="table-wrap"><table><thead><tr>{thead}</tr></thead><tbody>{tbody}</tbody></table></div>')
        continue
    if line.startswith("# "):
        i += 1; continue  # page title is rendered by the shell
    m = re.match(r"^## (\d+)\. (.*)$", line)
    if m:
        flush_para(); close_list()
        sid = f"s{m.group(1)}"
        sections.append((sid, m.group(2)))
        body.append(f'<h2 id="{sid}"><span class="num">{m.group(1)}</span>{inline(m.group(2))}</h2>')
        i += 1; continue
    m = re.match(r"^### (F\d+) — (High|Medium|Low|Test)\. (.*)$", line)
    if m:
        flush_para(); close_list()
        fid, sev, title = m.groups()
        findings.append((fid, sev, title))
        body.append(f'<h3 id="{fid.lower()}"><span class="sev sev-{sev.lower()}">{sev}</span><span class="fid">{fid}</span>{inline(title)}</h3>')
        i += 1; continue
    if line.startswith("### "):
        flush_para(); close_list()
        body.append(f"<h3>{inline(line[4:])}</h3>")
        i += 1; continue
    if line.startswith("- "):
        flush_para()
        if not in_list:
            body.append("<ul>"); in_list = True
        item = line[2:]
        # continuation lines indented by two spaces
        while i + 1 < len(lines) and lines[i + 1].startswith("  ") and not lines[i + 1].startswith("  -"):
            i += 1; item += " " + lines[i].strip()
        body.append(f"<li>{inline(item)}</li>")
        i += 1; continue
    if not line.strip():
        flush_para(); close_list()
        i += 1; continue
    para.append(line.strip())
    i += 1
flush_para(); close_list()

sev_rank = {"High": 0, "Medium": 1, "Low": 2, "Test": 3}
findings_index = "".join(
    f'<a class="fx" href="#{fid.lower()}"><span class="sev sev-{sev.lower()}">{sev}</span><span class="fid">{fid}</span><span class="ft">{inline(title)}</span></a>'
    for fid, sev, title in findings
)
toc = "".join(f'<a href="#{sid}"><span class="num">{sid[1:]}</span>{inline(title)}</a>' for sid, title in sections)
counts = {k: sum(1 for _, s, _ in findings if s == k) for k in sev_rank}

gates = [
    ("Lint", "0 issues"), ("tsc", "clean"), ("Unit", "130 / 130"), ("Build", "exit 0"),
    ("Smoke · Chromium", "passed · 133.8 s"), ("a11y", "75 comb. · 0 violations"),
    ("CI main", "3 engines × 3 runs green"), ("Focus harness", "24 / 24 · 3 engines"),
    ("Unit mutations", "12 / 12 survive"), ("Sweep vs dead backend", "54 / 54 scans pass"),
]
gate_html = "".join(f'<div class="gate"><span class="gl">{html.escape(l)}</span><span class="gv">{html.escape(v)}</span></div>' for l, v in gates)

page = f"""<title>FE-A0 Frontend Code Audit</title>
<style>
:root {{
  --bg: #f7f4ec; --panel: #fbf9f3; --ink: #191922; --muted: #5d5d68; --soft: #6a6a72;
  --rule: #a8a498; --rule-strong: #6f6c62; --accent: #2f54c9; --accent-soft: rgba(47, 84, 201, .09);
  --critical: #b91c1c; --warning: #a24310; --success: #166534; --idle: #5d5d68;
  --code-bg: rgba(25, 25, 34, .06); --sel: rgba(47, 84, 201, .18);
  --font-display: "Avenir Next", "Segoe UI", system-ui, sans-serif;
  --font-sans: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
  --font-mono: ui-monospace, "SFMono-Regular", Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace;
  color-scheme: light;
}}
@media (prefers-color-scheme: dark) {{
  :root:not([data-theme="light"]) {{
    --bg: #0a0c10; --panel: #101319; --ink: #e9edf4; --muted: #99a3b4; --soft: #99a3b4;
    --rule: #242b38; --rule-strong: #606b7e; --accent: #8b93f8; --accent-soft: rgba(139, 147, 248, .12);
    --critical: #f87171; --warning: #fbbf24; --success: #34d399; --idle: #99a3b4;
    --code-bg: rgba(233, 237, 244, .08); --sel: rgba(139, 147, 248, .25);
    color-scheme: dark;
  }}
}}
:root[data-theme="dark"] {{
  --bg: #0a0c10; --panel: #101319; --ink: #e9edf4; --muted: #99a3b4; --soft: #99a3b4;
  --rule: #242b38; --rule-strong: #606b7e; --accent: #8b93f8; --accent-soft: rgba(139, 147, 248, .12);
  --critical: #f87171; --warning: #fbbf24; --success: #34d399; --idle: #99a3b4;
  --code-bg: rgba(233, 237, 244, .08); --sel: rgba(139, 147, 248, .25);
  color-scheme: dark;
}}
* {{ box-sizing: border-box; }}
body {{ margin: 0; background: var(--bg); color: var(--ink); font: 15px/1.55 var(--font-sans); -webkit-font-smoothing: antialiased; }}
::selection {{ background: var(--sel); }}
a {{ color: var(--accent); text-decoration: none; }}
a:hover, a:focus-visible {{ text-decoration: underline; text-underline-offset: 2px; }}
:focus-visible {{ outline: 2px solid var(--accent); outline-offset: 2px; }}
.page {{ max-width: 1120px; margin: 0 auto; padding: 40px 28px 72px; }}
.mast {{ display: grid; gap: 14px; border-bottom: 1px solid var(--rule-strong); padding-bottom: 22px; }}
.eyebrow {{ display: flex; flex-wrap: wrap; gap: 8px 18px; font: 500 11px/1.4 var(--font-mono); letter-spacing: .08em; text-transform: uppercase; color: var(--muted); }}
.mast h1 {{ margin: 0; font: 600 34px/1.1 var(--font-display); letter-spacing: -.01em; text-wrap: balance; max-width: 22ch; }}
.mast p {{ margin: 0; max-width: 72ch; color: var(--muted); }}
.gates {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(190px, 1fr)); gap: 1px; margin-top: 24px; background: var(--rule); border: 1px solid var(--rule); }}
.gate {{ display: grid; gap: 4px; padding: 12px 14px; background: var(--panel); }}
.gl {{ font: 500 10.5px/1.3 var(--font-mono); letter-spacing: .08em; text-transform: uppercase; color: var(--muted); }}
.gv {{ font: 600 14px/1.3 var(--font-mono); font-variant-numeric: tabular-nums; }}
.toc {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(230px, 1fr)); gap: 6px 22px; margin: 26px 0 0; padding: 0; }}
.toc a {{ display: flex; gap: 10px; align-items: baseline; padding: 4px 0; color: var(--ink); border-bottom: 1px dotted var(--rule); }}
.toc a:hover {{ color: var(--accent); text-decoration: none; }}
.num {{ font: 600 11px/1 var(--font-mono); color: var(--accent); letter-spacing: .06em; }}
.index {{ margin-top: 30px; }}
.index h2 {{ margin: 0 0 4px; }}
.tally {{ display: flex; flex-wrap: wrap; gap: 8px 16px; margin: 6px 0 14px; color: var(--muted); font-size: 13px; }}
.fgrid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(320px, 1fr)); gap: 1px; background: var(--rule); border: 1px solid var(--rule); }}
.fx {{ display: grid; grid-template-columns: auto auto 1fr; align-items: baseline; gap: 10px; padding: 10px 12px; background: var(--panel); color: var(--ink); font-size: 13.5px; line-height: 1.35; }}
.fx:hover {{ background: var(--accent-soft); text-decoration: none; }}
.sev {{ display: inline-flex; align-items: center; gap: 6px; font: 700 10.5px/1 var(--font-mono); letter-spacing: .08em; text-transform: uppercase; white-space: nowrap; }}
.sev::before {{ content: ""; width: 7px; height: 7px; border-radius: 50%; background: currentColor; }}
.sev-high {{ color: var(--critical); }}
.sev-high::before {{ border-radius: 2px; }}
.sev-medium {{ color: var(--warning); }}
.sev-medium::before {{ width: 0; height: 0; border-radius: 0; background: none; border-left: 4.5px solid transparent; border-right: 4.5px solid transparent; border-bottom: 8px solid currentColor; }}
.sev-low {{ color: var(--idle); }}
.sev-low::before {{ width: 8px; height: 3px; border-radius: 999px; }}
.sev-test {{ color: var(--accent); }}
.fid {{ font: 700 12px/1 var(--font-mono); color: var(--muted); }}
main {{ margin-top: 40px; }}
main h2 {{ display: flex; gap: 14px; align-items: baseline; margin: 56px 0 14px; padding-top: 22px; border-top: 1px solid var(--rule-strong); font: 600 24px/1.15 var(--font-display); letter-spacing: -.01em; text-wrap: balance; }}
main h2:first-child {{ margin-top: 0; border-top: 0; padding-top: 0; }}
main h3 {{ display: flex; flex-wrap: wrap; gap: 10px; align-items: baseline; margin: 30px 0 8px; font: 600 17px/1.3 var(--font-display); text-wrap: balance; scroll-margin-top: 16px; }}
main p {{ max-width: 76ch; margin: 0 0 12px; }}
main ul {{ max-width: 80ch; margin: 0 0 14px; padding-left: 20px; }}
main li {{ margin: 0 0 8px; }}
main li::marker {{ color: var(--rule-strong); }}
code {{ font: 500 .92em/1.4 var(--font-mono); background: var(--code-bg); padding: 1px 4px; border-radius: 3px; overflow-wrap: anywhere; }}
pre {{ margin: 0 0 16px; padding: 14px 16px; overflow-x: auto; border: 1px solid var(--rule); background: var(--panel); font: 12.5px/1.5 var(--font-mono); }}
pre code {{ background: none; padding: 0; font-size: inherit; }}
.table-wrap {{ overflow-x: auto; margin: 0 0 18px; border: 1px solid var(--rule); }}
table {{ border-collapse: collapse; width: 100%; min-width: 720px; font-size: 13.5px; line-height: 1.45; }}
th, td {{ padding: 8px 10px; vertical-align: top; text-align: left; border-bottom: 1px solid var(--rule); }}
th {{ font: 500 10.5px/1.4 var(--font-mono); letter-spacing: .08em; text-transform: uppercase; color: var(--muted); background: var(--panel); position: sticky; top: 0; }}
tbody tr:last-child td {{ border-bottom: 0; }}
td {{ font-variant-numeric: tabular-nums; }}
td:first-child {{ white-space: normal; min-width: 180px; }}
strong {{ font-weight: 650; }}
.foot {{ margin-top: 56px; padding-top: 16px; border-top: 1px solid var(--rule); color: var(--muted); font: 500 11px/1.5 var(--font-mono); letter-spacing: .06em; text-transform: uppercase; }}
@media (max-width: 720px) {{ .page {{ padding: 24px 16px 48px; }} .mast h1 {{ font-size: 27px; }} }}
@media (prefers-reduced-motion: reduce) {{ * {{ scroll-behavior: auto !important; }} }}
</style>
<div class="page">
  <header class="mast">
    <div class="eyebrow"><span>CAOS · Credit Agent OS</span><span>caos/frontend</span><span>main @ ea42a2d</span><span>2026-09-05</span><span>assessment · no source changed</span></div>
    <h1>FE-A0 adversarial code audit of the frontend</h1>
    <p>What is wrong with the code as it stands, separately from what is wrong with its structure: the implementer's brief for FE-G1 and the risk register for FE-G2 and FE-G3. Every finding carries a file and line, a reproduction and the contract clause it violates.</p>
    <div class="gates">{gate_html}</div>
    <nav class="toc" aria-label="Sections">{toc}</nav>
  </header>
  <section class="index" aria-labelledby="findings-index">
    <h2 id="findings-index" style="font: 600 13px/1.4 var(--font-mono); letter-spacing: .08em; text-transform: uppercase; color: var(--muted); margin-top: 30px;">Findings index</h2>
    <div class="tally"><span>{counts['High']} high</span><span>{counts['Medium']} medium</span><span>{counts['Low']} low</span><span>{counts['Test']} test-layer</span></div>
    <div class="fgrid">{findings_index}</div>
  </section>
  <main>
    {chr(10).join(body)}
  </main>
  <footer class="foot">Source: .superpowers/sdd/frontend/frontend-a0-code-audit.md · evidence under .superpowers/sdd/frontend/evidence/</footer>
</div>
"""
out.write_text(page)
print(f"wrote {out} ({len(page):,} bytes); sections {len(sections)}; findings {len(findings)}; {counts}")
