"""One-off: download the web fonts once and serve them from our own server.

Loading fonts from fonts.googleapis.com sends every visitor's IP address to Google;
in Austria/Germany that has led to GDPR claims (LG München, 20.01.2022, 3 O 17493/20).
Result: assets/fonts/*.woff2 + assets/fonts.css (latin + latin-ext only).

Run:  python _src/fetch_fonts.py      (only needed again if the font selection changes)
"""
import re
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "assets" / "fonts"
CSS_URL = ("https://fonts.googleapis.com/css2?family=Archivo:wdth,wght@62..125,300..700"
           "&family=Newsreader:ital,opsz,wght@1,6..72,300;1,6..72,400&display=swap")
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36"
KEEP = ("latin", "latin-ext")


def get(url):
    return urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": UA}), timeout=30).read()


css = get(CSS_URL).decode("utf-8")
OUT.mkdir(parents=True, exist_ok=True)
blocks, seen = [], set()
for subset, body in re.findall(r"/\* ([a-z-]+) \*/\s*@font-face \{(.*?)\}", css, re.S):
    if subset not in KEEP:
        continue
    url = re.search(r"url\((https://[^)]+\.woff2)\)", body).group(1)
    family = re.search(r"font-family: '([^']+)'", body).group(1)
    style = re.search(r"font-style: (\w+)", body).group(1)
    name = f"{family.lower()}-{style}-{subset}.woff2"
    if name in seen:  # same variable file, listed once per requested weight: widen the range instead
        i = next(k for k, blk in enumerate(blocks) if f"fonts/{name}" in blk)
        lo = re.search(r"font-weight: (\d+)", blocks[i]).group(1)
        hi = re.search(r"font-weight: (\d+)", body).group(1)
        blocks[i] = re.sub(r"font-weight: [\d ]+;", f"font-weight: {lo} {hi};", blocks[i])
        continue
    seen.add(name)
    (OUT / name).write_bytes(get(url))
    blocks.append("/* %s */\n@font-face {%s}" % (subset, body.replace(url, f"fonts/{name}")))
    print("saved", name, (OUT / name).stat().st_size, "bytes")

(ROOT / "assets" / "fonts.css").write_text(
    "/* Self-hosted copies of Archivo and Newsreader (SIL Open Font License), see _src/fetch_fonts.py */\n"
    + "\n".join(blocks) + "\n", encoding="utf-8")
print("wrote assets/fonts.css")
