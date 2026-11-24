"""Testprotokoll.md -> PDF (einfacher Markdown-Umsetzer + Edge headless, wie tools/plot_episode.py).

Kann: Ueberschriften, Absaetze, Listen, Tabellen, Codebloecke, **fett**, *kursiv*, `code`, Bilder, ---.
    python skripte/md_zu_pdf.py Testprotokoll.md ../2026-11-10_Modellpruefung_Checkpoint_2026-11-09.pdf
"""
import html
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

EDGE = [Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"),
        Path(r"C:\Program Files\Microsoft\Edge\Application\msedge.exe")]

CSS = """
body{font-family:'Segoe UI',Arial,sans-serif;font-size:10pt;line-height:1.4;margin:0 6mm;color:#222}
h1{font-size:17pt;border-bottom:2px solid #444;padding-bottom:4px}
h2{font-size:13pt;margin-top:18px;border-bottom:1px solid #bbb;page-break-after:avoid}
table{border-collapse:collapse;margin:6px 0;font-size:8.5pt;page-break-inside:avoid}
th,td{border:1px solid #bbb;padding:2px 5px;vertical-align:top}
th{background:#eee}
code{font-family:Consolas,monospace;font-size:8.5pt;background:#f3f3f3;padding:0 2px}
pre{background:#f3f3f3;padding:6px;font-size:8pt;white-space:pre-wrap}
pre code{background:none}
img{max-width:100%;page-break-inside:avoid}
hr{border:none;border-top:1px solid #ccc;margin:14px 0}
"""


def inline(t):
    t = html.escape(t, quote=False)
    t = re.sub(r"!\[([^\]]*)\]\(([^)]+)\)", r'<img alt="\1" src="\2">', t)
    t = re.sub(r"`([^`]+)`", r"<code>\1</code>", t)
    t = re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", t)
    t = re.sub(r"(?<![\w*])\*([^*\n]+)\*(?![\w*])", r"<i>\1</i>", t)
    return t


def convert(md):
    out, lines, i = [], md.splitlines(), 0
    para = []

    def flush():
        if para:
            out.append("<p>%s</p>" % inline(" ".join(para)))
            para.clear()

    while i < len(lines):
        ln = lines[i]
        if ln.startswith("```"):
            flush()
            j = i + 1
            while j < len(lines) and not lines[j].startswith("```"):
                j += 1
            out.append("<pre><code>%s</code></pre>" % html.escape("\n".join(lines[i + 1:j])))
            i = j + 1
            continue
        m = re.match(r"^(#{1,4})\s+(.*)", ln)
        if m:
            flush()
            n = len(m.group(1))
            out.append("<h%d>%s</h%d>" % (n, inline(m.group(2)), n))
        elif ln.strip() == "---":
            flush()
            out.append("<hr>")
        elif ln.startswith("|"):
            flush()
            rows = []
            while i < len(lines) and lines[i].startswith("|"):
                rows.append([c.strip() for c in lines[i].strip().strip("|").split("|")])
                i += 1
            body = [r for r in rows if not all(re.match(r"^:?-+:?$", c) for c in r)]
            h = "".join("<th>%s</th>" % inline(c) for c in body[0])
            b = "".join("<tr>%s</tr>" % "".join("<td>%s</td>" % inline(c) for c in r) for r in body[1:])
            out.append("<table><tr>%s</tr>%s</table>" % (h, b))
            continue
        elif re.match(r"^\s*(\*|-|\d+\.)\s+", ln):
            flush()
            ordered = bool(re.match(r"^\s*\d+\.", ln))
            items = []
            while i < len(lines) and (re.match(r"^\s*(\*|-|\d+\.)\s+", lines[i])
                                      or (lines[i].startswith("  ") and lines[i].strip())):
                if re.match(r"^\s*(\*|-|\d+\.)\s+", lines[i]):
                    items.append(re.sub(r"^\s*(\*|-|\d+\.)\s+", "", lines[i]))
                else:
                    items[-1] += " " + lines[i].strip()
                i += 1
            tag = "ol" if ordered else "ul"
            out.append("<%s>%s</%s>" % (tag, "".join("<li>%s</li>" % inline(x) for x in items), tag))
            continue
        elif not ln.strip():
            flush()
        else:
            para.append(ln.strip())
        i += 1
    flush()
    return "\n".join(out)


def main():
    src, dst = Path(sys.argv[1]).resolve(), Path(sys.argv[2]).resolve()
    page = "<!doctype html><html><head><meta charset='utf-8'><style>%s</style></head><body>%s</body></html>" % (
        CSS, convert(src.read_text(encoding="utf-8")))
    tmp_html = src.parent / "_druck.html"   # neben dem MD, damit relative Bildpfade stimmen
    tmp_html.write_text(page, encoding="utf-8")
    edge = next((p for p in EDGE if p.is_file()), None) or shutil.which("msedge")
    tmp = Path(tempfile.mkdtemp())
    try:
        subprocess.run([str(edge), "--headless=new", "--disable-gpu", "--no-pdf-header-footer",
                        "--user-data-dir=%s" % (tmp / "profile"), "--print-to-pdf=%s" % dst,
                        tmp_html.as_uri()], check=True, timeout=120)
    finally:
        tmp_html.unlink()
        shutil.rmtree(str(tmp), ignore_errors=True)
    if not dst.is_file():
        raise SystemExit("PDF wurde nicht erzeugt: %s" % dst)
    print(dst)


if __name__ == "__main__":
    main()
