"""Builds the site from content/*.yml + templates/ into dist/.

    python build.py            preview build (noindex, for *.workers.dev)
    python build.py --prod     production build for thechiropractor.at (indexable, sitemap)

Content is edited in Pages CMS (.pages.yml) or directly in content/*.yml.
Needs: pip install -r requirements.txt, npm ci (Tailwind).
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from datetime import date
from urllib.parse import quote_plus

import yaml
from jinja2 import Environment, FileSystemLoader, ChainableUndefined, pass_context
from markupsafe import Markup
from PIL import Image

ROOT = Path(__file__).resolve().parent
CONTENT = ROOT / "content"
DIST = ROOT / "dist"
ORIGIN = "https://thechiropractor.at"
MAX_IMG = 2560  # px, longest side; larger CMS uploads (e.g. straight from a phone) get scaled down in dist/
WEBP_WIDTHS = (480, 800, 1200, 1600, 2000, 2560)  # srcset steps; only those below the image width are made

# name -> template, content file, full-bleed hero (transparent header), nav key for aria-current
PAGES = {
    "index":              ("pages/index.html", "home", True, "home"),
    "chiropraktik":       ("pages/chiropraktik.html", "chiropraktik", True, "chiropraktik"),
    "uber-uns":           ("pages/uber-uns.html", "uber-uns", True, "uber-uns"),
    "erfahrungsberichte": ("pages/erfahrungsberichte.html", "erfahrungsberichte", True, "erfahrungsberichte"),
    "kontakt":            ("pages/kontakt.html", "kontakt", True, "kontakt"),
    "impressum":          ("pages/legal.html", "impressum", False, "impressum"),
    "datenschutz":        ("pages/legal.html", "datenschutz", False, "datenschutz"),
    "404":                ("pages/404.html", "404", False, ""),
}
THEME_COLOR = {"sand": "#F9F8F2", "sky": "#FFFFFF", "rose": "#FFFFFF"}

# Line icons for "Folgendes wird durch Chiropraktik positiv beeinflusst" (select field in the CMS)
ICONS = {
    "stimmung": '<circle cx="16" cy="16" r="11"/><path d="M11.5 19c1.2 1.6 2.7 2.4 4.5 2.4s3.3-.8 4.5-2.4"/><path d="M12.3 13h.01M19.7 13h.01"/>',
    "haltung": '<path d="M16 3c-2 4 2 6 0 10s-2 6 0 10 2 4 0 6"/><path d="M12.5 6h7M12 11h8M12 16h8M12 21h8M12.5 26h7"/>',
    "immunsystem": '<path d="M16 3.5l9.5 3.8v7.5c0 6.8-4.3 10.7-9.5 13.7-5.2-3-9.5-6.9-9.5-13.7V7.3z"/><path d="M12 16l3 3 5.2-6"/>',
    "energie": '<path d="M18 3.5L7.5 18h8l-2 10.5L24.5 14h-8z"/>',
    "stress": '<path d="M3 16h5l3-7 4 14 4-10 3 5h7"/>',
    "beweglichkeit": '<circle cx="18.5" cy="5.5" r="2.5"/><path d="M9 13l6-3 4 3 5-1M15 10l-2 8 5 4-1 7M13 18l-5 5"/>',
    "verdauung": '<path d="M9 5h14c2 0 3 1.5 3 3.2S25 11.5 23 11.5H10c-2 0-3 1.5-3 3.3S8 18 10 18h12c2 0 3 1.5 3 3.2S24 24.5 22 24.5h-8v3"/>',
    "herz": '<path d="M16 27S4 19.5 4 11.5A6 6 0 0 1 16 9a6 6 0 0 1 12 2.5C28 19.5 16 27 16 27z"/><path d="M8.5 15h3.5l2-3 3 6 2-3h4.5"/>',
    "schlaf": '<path d="M24 20.5A10 10 0 0 1 12.5 6 10 10 0 1 0 24 20.5z"/><path d="M20 5h4l-4 4h4"/>',
}


def load(name):
    with open(CONTENT / f"{name}.yml", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


# ---- template helpers -------------------------------------------------------

def _secs(i, step):
    return f"{i * step:.2f}".rstrip("0").lstrip("0") + "s"


def delay(i, step):
    """Stagger for scroll reveals: ' style="--d:.1s"' (nothing for the first item)."""
    return Markup(f' style="--d:{_secs(i, step)}"') if i else ""


def delay_css(i, step):
    return f"; --d:{_secs(i, step)}" if i else ""


@pass_context
def current(ctx, key):
    return Markup(' aria-current="page"') if key and key == ctx["active"] else ""


def rich(html, p_class=""):
    """Rich-text from the CMS (trusted editors): drop empty paragraphs, optionally style every <p>."""
    html = re.sub(r"<p>(\s|&nbsp;)*</p>", "", (html or "").strip())
    if p_class:
        html = re.sub(r"<p>", f'<p class="{p_class}">', html)
    return Markup(html)


def count_up(text):
    """The first number in the text counts up on scroll (site.js [data-count])."""
    esc = str(Markup.escape(text))
    return Markup(re.sub(r"\b(\d+)\b", r'<span class="num" data-count="\1">\1</span>', esc, count=1))


def tel(phone):
    return re.sub(r"[^\d+]", "", phone)


# ---- structured data ----------------------------------------------------------

def _plain(text):
    return (text or "").replace("\u00ad", "").strip()


def _person_name(full):
    """'Mgr. Marek Sukenik, MSc.' -> ('Marek Sukenik', 'Mgr.', 'MSc.')"""
    name, _, suffix = _plain(full).partition(",")
    m = re.match(r"((?:[A-Za-z]+\.\s*)+)(.*)", name.strip())
    prefix, name = (m.group(1).strip(), m.group(2).strip()) if m else ("", name.strip())
    return name, prefix, suffix.strip()


def json_ld(name, page, site, team):
    """schema.org graph, built only from facts that are already on the site (plus the GBR number)."""
    biz_id, site_id = f"{ORIGIN}/#praxis", f"{ORIGIN}/#website"
    street, _, rest = site["address"].partition(",")
    plz, _, city = rest.strip().partition(" ")
    people = []
    for i, m in enumerate(team):
        pname, prefix, suffix = _person_name(m.get("name"))
        person = {"@type": "Person", "@id": f"{ORIGIN}/uber-uns#person-{i + 1}", "name": pname,
                  "url": f"{ORIGIN}/uber-uns", "worksFor": {"@id": biz_id}}
        if prefix:
            person["honorificPrefix"] = prefix
        if suffix:
            person["honorificSuffix"] = suffix
        if m.get("image"):
            person["image"] = ORIGIN + m["image"]
        if m.get("titles"):
            person["jobTitle"] = [_plain(x) for x in m["titles"]]
        if i == 0 and site.get("gbr_number"):
            person["hasCredential"] = {
                "@type": "EducationalOccupationalCredential",
                "credentialCategory": "Berufsberechtigung",
                "name": "Physiotherapeut",
                "identifier": site["gbr_number"],
                "recognizedBy": {"@type": "GovernmentOrganization", "name": "Gesundheitsberuferegister",
                                 "url": "https://gbr-public.ehealth.gv.at/"},
            }
        people.append(person)
    biz = {
        "@type": ["MedicalBusiness", "Physiotherapy"], "@id": biz_id, "name": site["name"],
        "url": ORIGIN + "/", "logo": ORIGIN + site["logo"], "image": ORIGIN + site["og_image"],
        "telephone": site["phone"], "email": site["email"],
        "address": {"@type": "PostalAddress", "streetAddress": street.strip(), "postalCode": plz,
                    "addressLocality": city, "addressCountry": "AT"},
        "areaServed": {"@type": "City", "name": city},
    }
    if people:
        biz["employee"] = [{"@id": x["@id"]} for x in people]
    if any(site.get("same_as") or []):
        biz["sameAs"] = [u for u in site["same_as"] if u]
    graph = [biz, {"@type": "WebSite", "@id": site_id, "url": ORIGIN + "/", "name": site["name"],
                   "inLanguage": "de-AT", "publisher": {"@id": biz_id}}] + people
    if name != "index":
        graph.append({"@type": "BreadcrumbList", "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "Startseite", "item": ORIGIN + "/"},
            {"@type": "ListItem", "position": 2, "name": _plain(page["title"]), "item": f"{ORIGIN}/{name}"},
        ]})
    data = json.dumps({"@context": "https://schema.org", "@graph": graph}, ensure_ascii=False, separators=(",", ":"))
    return Markup(data.replace("</", "<\\/"))


def lastmod(name):
    """Date of the last commit that touched the page's content or template (for the sitemap)."""
    tpl, content, *_ = PAGES[name]
    try:
        out = subprocess.run(["git", "log", "-1", "--format=%cs", "--", f"content/{content}.yml", f"templates/{tpl}"],
                             cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        out = ""
    return out or date.today().isoformat()


# ---- build ------------------------------------------------------------------

def render_pages(prod):
    env = Environment(loader=FileSystemLoader(ROOT / "templates"), autoescape=True,
                      undefined=ChainableUndefined, trim_blocks=True, keep_trailing_newline=True)
    env.filters.update(rich=rich, count_up=count_up, tel=tel, urlq=quote_plus)
    site, consent = load("site"), load("consent")
    env.globals.update(site=site, consent=consent, icons=ICONS, delay=delay, delay_css=delay_css,
                       current=current, origin=ORIGIN)
    if site.get("theme", "sand") not in THEME_COLOR:
        sys.exit(f"content/site.yml: unknown theme {site['theme']!r}")

    team = load("uber-uns").get("people") or []
    unlisted = set()  # pages kept out of the sitemap
    for name, (tpl, content, hero, active) in PAGES.items():
        page = load(content)
        url = "/" if name == "index" else f"/{name}"
        is_404 = name == "404"
        # a testimonials page without testimonials stays out of Google until the first real one is added
        empty = name == "erfahrungsberichte" and not page.get("reviews")
        if empty or is_404:
            unlisted.add(name)
        if is_404:
            noindex = "noindex"
        elif not prod:
            noindex = "noindex, nofollow, noarchive"
        else:
            noindex = "noindex, follow" if empty else None
        og_image = team[0]["image"] if name == "uber-uns" and team and team[0].get("image") else site["og_image"]
        html = env.get_template(tpl).render(
            page=page, hero=hero, active=active,
            full_title=page["title"] if page["title"] == site["name"] else f'{page["title"]} – {site["name"]}',
            canonical=None if is_404 else ORIGIN + url,
            noindex=noindex, og_image=og_image,
            json_ld=None if is_404 else json_ld(name, page, site, team),
            theme_color=THEME_COLOR[site.get("theme", "sand")],
        )
        (DIST / f"{name}.html").write_text(html, encoding="utf-8", newline="\n")
        print("page ", f"{name}.html")
    return unlisted


def copy_media():
    shutil.copytree(ROOT / "assets", DIST / "assets", ignore=shutil.ignore_patterns("tw-config.js"))
    used = " ".join(p.read_text(encoding="utf-8") for p in DIST.rglob("*") if p.suffix in (".html", ".css", ".js"))
    # every referenced image must exist (e.g. a file deleted in the CMS media library)
    missing = sorted({m for m in re.findall(r"/img/([^\"')\s]+)", used) if not (ROOT / "img" / m).is_file()})
    if missing:
        sys.exit(f"missing images in img/: {', '.join(missing)}")
    (DIST / "img").mkdir()
    for src in sorted((ROOT / "img").iterdir()):
        if not src.is_file() or f"/img/{src.name}" not in used:
            continue  # only ship what the pages use
        dst = DIST / "img" / src.name
        shutil.copy2(src, dst)
        if src.suffix.lower() in (".jpg", ".jpeg", ".png", ".webp"):
            with Image.open(src) as im:
                if max(im.size) > MAX_IMG:
                    im.thumbnail((MAX_IMG, MAX_IMG), Image.LANCZOS)
                    opts = {"quality": 82, "optimize": True, "progressive": True} if src.suffix.lower() in (".jpg", ".jpeg") else {"optimize": True}
                    im.save(dst, **opts)
                    if dst.stat().st_size >= src.stat().st_size:
                        shutil.copy2(src, dst)  # re-encoding did not help, keep the original
                    else:
                        print("image", src.name, "scaled to", im.size)


def fit_sizes(tag, ratio):
    """object-fit: cover shows a wide image wider than its box. The templates give the box shape
    (data-box = width/height, data-hero = height in vh of a full-width hero); scale `sizes` to match."""
    hero = re.search(r'\sdata-hero="([\d.]+)"', tag)
    box = re.search(r'\sdata-box="([\d.]+)"', tag)
    tag = re.sub(r'\sdata-(hero|box)="[^"]*"', "", tag)
    if hero:
        return re.sub(r'\ssizes="[^"]*"', "", tag).replace("<img", f'<img sizes="max(100vw, {float(hero.group(1)) * ratio:.0f}vh)"', 1)
    if box and ratio > float(box.group(1)):
        k = ratio / float(box.group(1))
        def scale(m):
            parts = []
            for entry in m.group(1).split(","):
                media, _, length = entry.strip().rpartition(" ")
                parts.append(f"{media} calc({length} * {k:.2f})".strip())
            return f' sizes="{", ".join(parts)}"'
        tag = re.sub(r'\ssizes="([^"]*)"', scale, tag)
    return tag


def responsive_images():
    """WebP copies in several widths for every JPEG/PNG in dist/img, then srcset + width/height on the <img>
    tags and a preload for the hero image. The original file stays as src (fallback)."""
    variants = {}
    count = 0
    for img in sorted((DIST / "img").iterdir()):
        if img.suffix.lower() not in (".jpg", ".jpeg", ".png"):
            continue
        with Image.open(img) as im:
            size = im.size
            if im.mode not in ("RGB", "RGBA"):
                im = im.convert("RGBA" if im.mode in ("P", "LA", "PA") or "transparency" in im.info else "RGB")
            entries = []
            for w in [w for w in WEBP_WIDTHS if w < size[0]] + [size[0]]:
                out = img.with_name(f"{img.stem}-{w}.webp")
                (im if w == size[0] else im.resize((w, round(size[1] * w / size[0])), Image.LANCZOS)).save(
                    out, "WEBP", quality=80, method=6)
                if w == size[0] and out.stat().st_size >= img.stat().st_size:
                    out.unlink()  # a full-size WebP that is not smaller: the original covers that width
                    entries.append(f"/img/{img.name} {w}w")
                    continue
                entries.append(f"/img/{out.name} {w}w")
                count += 1
        variants[f"/img/{img.name}"] = (size, ", ".join(entries))

    def tag(m):
        t = m.group(0)
        src = re.search(r'\ssrc="([^"]+)"', t)
        if not src or src.group(1) not in variants or "srcset=" in t:
            return t
        (w, h), srcset = variants[src.group(1)]
        t = fit_sizes(t, w / h)
        extra = f' srcset="{srcset}"' + ("" if "sizes=" in t else ' sizes="100vw"')
        if "width=" not in t:
            extra += f' width="{w}" height="{h}"'
        return t[:4] + extra + t[4:]

    for page in DIST.glob("*.html"):
        html = re.sub(r"<img\s[^>]*>", tag, page.read_text(encoding="utf-8"))
        hero = re.search(r'<img\s[^>]*fetchpriority="high"[^>]*>', html)
        s = hero and re.search(r'srcset="([^"]+)"', hero.group(0))
        if s:
            z = re.search(r'sizes="([^"]+)"', hero.group(0))
            link = (f'<link rel="preload" as="image" imagesrcset="{s.group(1)}" '
                    f'imagesizes="{z.group(1) if z else "100vw"}" fetchpriority="high">\n')
            anchor = '<link rel="stylesheet" href="/assets/fonts.css">'
            html = html.replace(anchor, link + anchor, 1)
        page.write_text(html, encoding="utf-8", newline="\n")
    print("image", count, "webp variants")


def build_css():
    npx = "npx.cmd" if os.name == "nt" else "npx"
    subprocess.run([npx, "--no-install", "tailwindcss", "-c", str(ROOT / "tailwind.config.js"),
                    "-i", str(ROOT / "tools/tw-input.css"), "-o", str(DIST / "assets/tw.css"), "--minify"],
                   check=True)


def write_meta(prod, unlisted):
    if prod:
        (DIST / "robots.txt").write_text(f"User-agent: *\nAllow: /\n\nSitemap: {ORIGIN}/sitemap.xml\n", encoding="utf-8")
        urls = [("/" if n == "index" else f"/{n}", lastmod(n)) for n in PAGES if n not in unlisted]
        (DIST / "sitemap.xml").write_text(
            '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
            + "".join(f"  <url><loc>{ORIGIN}{u}</loc><lastmod>{d}</lastmod></url>\n" for u, d in urls)
            + "</urlset>\n", encoding="utf-8")
    else:
        (DIST / "robots.txt").write_text("User-agent: *\nDisallow: /\n", encoding="utf-8")

    # Old WordPress URLs (first match wins, so specific rules come before the catch-all)
    (DIST / "_redirects").write_text("""/wp-content/privacy-policy-2 /datenschutz 301
/wp-content/privacy-policy-2/ /datenschutz 301
/privacy-policy-2 /datenschutz 301
/privacy-policy-2/ /datenschutz 301
/wp-content/uploads/* / 301
/wp-admin/* / 301
/wp-login.php / 301
/feed / 301
/feed/ / 301
/wp-content/:page /:page 301
/wp-content/:page/ /:page 301
""", encoding="utf-8")

    (DIST / "_headers").write_text("""/*
  Strict-Transport-Security: max-age=31536000
  X-Content-Type-Options: nosniff
  X-Frame-Options: DENY
  Referrer-Policy: strict-origin-when-cross-origin
  Permissions-Policy: camera=(), microphone=(), geolocation=(), interest-cohort=()
""" + ("" if prod else "  X-Robots-Tag: noindex, nofollow, noarchive\n") + """
/assets/fonts/*
  Cache-Control: public, max-age=31536000, immutable

/img/*
  Cache-Control: public, max-age=2592000
""", encoding="utf-8")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--prod", action="store_true", help="indexable build for thechiropractor.at")
    prod = ap.parse_args().prod or os.environ.get("SITE_ENV") == "production"

    # empty dist/ instead of deleting it, so a running `wrangler dev` keeps watching the folder
    DIST.mkdir(exist_ok=True)
    for p in DIST.iterdir():
        shutil.rmtree(p) if p.is_dir() else p.unlink()
    unlisted = render_pages(prod)
    copy_media()
    responsive_images()
    build_css()
    write_meta(prod, unlisted)
    print("done ->", DIST, "(production)" if prod else "(preview, noindex)")


if __name__ == "__main__":
    main()
