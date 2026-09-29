# The Chiropractor Wien – Website mit Pages CMS

Statische Seite (HTML + Tailwind + Vanilla JS). Alle Texte, Bilder, FAQ, Zitate, Kontaktdaten, Rechtstexte und Bewertungen liegen in `content/*.yml` und sind in [Pages CMS](https://pagescms.org) bearbeitbar.
Design und Texte entsprechen 1:1 `../html_4` (Produktions-Build). html_4 bleibt als Backup unverändert.

## Aufbau

| Pfad | Inhalt |
|---|---|
| `content/*.yml` | Inhalte (eine Datei pro Seite + `site.yml` für Allgemeines + `consent.yml` für den Cookie-Banner) |
| `.pages.yml` | Pages-CMS-Konfiguration (Formulare, Medienordner `img/`) |
| `templates/` | Jinja2-Templates (`base.html`, `partials/`, `pages/`) |
| `assets/` | CSS, JS, lokale Schriften (`tw-config.js` = Tailwind-Theme) |
| `img/` | Bilder (= Medienbibliothek im CMS) |
| `build.py` | baut `dist/`: Seiten, Tailwind-CSS, nur verwendete Bilder (zu große Uploads werden auf 2560 px verkleinert), `_headers`, `_redirects`, robots/sitemap |

## Lokal

```bash
pip install -r requirements.txt
npm ci
python build.py           # Vorschau-Build (noindex)
npx wrangler dev          # http://localhost:8787
python build.py --prod    # Produktions-Build (indexierbar, sitemap.xml)
```

Der Build bricht ab, wenn ein referenziertes Bild in `img/` fehlt (z. B. im CMS gelöscht).

## Deploy (Push → workers.dev)

`.github/workflows/deploy.yml` baut bei jedem Push auf `main` und deployt nach Worker `tcw-cms-ac3d4184` (Konfiguration `wrangler.jsonc`, noindex, eigener Worker – die alte v1–v4-Vorschau wird nicht überschrieben).

Einmalig einrichten:
1. GitHub-Repo anlegen, `git remote add origin …`, `git push -u origin main`.
2. Cloudflare → *My Profile → API Tokens → Create Token* → Vorlage **Edit Cloudflare Workers**, nur für dieses eine Konto, ohne Zonen.
3. GitHub → *Settings → Secrets and variables → Actions*: `CLOUDFLARE_API_TOKEN` und `CLOUDFLARE_ACCOUNT_ID` anlegen.
4. *Actions → Deploy preview → Run workflow* (oder einfach pushen). URL: `https://tcw-cms-ac3d4184.<account-subdomain>.workers.dev`.

Alternative ohne Token: Cloudflare *Workers Builds* (Repo im Cloudflare-Dashboard verbinden, Build-Befehl `pip install -r requirements.txt && python build.py`, Deploy-Befehl `npx wrangler deploy`). **Nur eine der beiden Varianten aktivieren**, sonst wird doppelt deployt.

## Pages CMS verbinden

1. https://app.pagescms.org → mit GitHub anmelden.
2. Die Pages-CMS-GitHub-App **nur für dieses Repository** installieren (nicht „All repositories“).
3. Repo + Branch `main` wählen – die Formulare kommen aus `.pages.yml`.
4. Jedes Speichern = ein Commit → GitHub Action → nach ca. 1 Minute online.
5. Weitere Bearbeiter (z. B. der Cousin) über *Settings → Collaborators* in Pages CMS einladen (Login per E-Mail, kein GitHub-Konto nötig).

Hinweise:
- Rich-Text-Felder (FAQ-Antworten, Bio, Impressum, Datenschutz) werden als HTML gespeichert und ungefiltert ausgegeben – nur vertrauenswürdige Personen als Bearbeiter einladen.
- Bewertungen (`Erfahrungsberichte`) nur echte, mit Einverständnis der Person. Leere Liste = Bereich wird ausgeblendet.
- Farbschema: *Allgemein → Farbschema* (Sand/Blau/Rosé). Einen Theme-Umschalter für Besucher gibt es in dieser Version nicht.

## Produktion (thechiropractor.at) – noch NICHT deployt

```bash
python build.py --prod
npx wrangler deploy -c wrangler.prod.jsonc   # erst wenn die Domain auf Cloudflare liegt
```

Für Auto-Deploy in Produktion später im Workflow `python build.py --prod` + `npx wrangler deploy -c wrangler.prod.jsonc` verwenden.

## Offen

- Datenschutzerklärung erwähnt noch Google Analytics / Facebook / AdWords, die Seite nutzt diese nicht → rechtlich prüfen lassen.
- Cookie-Banner: Skripte mit Einwilligung als `<script type="text/plain" data-consent="statistics" …>` einbinden; nach neuem Dienst `CONSENT_VERSION` in `assets/consent.js` erhöhen.
