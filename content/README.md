# Briefing content source

This directory is the canonical source for the published GitHub Pages briefing site.

## Article format

Write dated articles as Markdown files:

```text
content/<topic>/<YYYY-MM-DD>.md
```

Each article needs front matter:

```md
---
topic: "india"
date: "2026-06-23"
title: "🇮🇳 India Daily — Tue Jun 23, 2026"
lede: "One-sentence page lede."
archiveTitle: "Short archive/homepage title"
summary: "One-sentence archive/homepage summary."
---

## Section heading

- **Signal:** Briefing bullet.

## Sources

- [Source title](https://example.com/)
```

## Topics

Topic metadata lives in `content/topics.json`.

## Build

Run from the repo root:

```bash
python3 scripts/build-site.py
```

The script regenerates:

- `index.html`
- `briefings/<topic>.html`
- `briefings/<topic>/<YYYY-MM-DD>.html`

Do not hand-edit generated HTML unless you also backport the change to `content/` or `scripts/build-site.py`.
