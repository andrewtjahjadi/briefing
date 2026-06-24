#!/usr/bin/env python3
"""Build the GitHub Pages briefing site from Markdown content.

Canonical inputs:
  content/topics.json
  content/<topic>/<YYYY-MM-DD>.md

Generated outputs:
  index.html
  briefings/<topic>.html
  briefings/<topic>/<YYYY-MM-DD>.html
"""
from __future__ import annotations

import html
import json
import re
import shutil
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CONTENT = ROOT / "content"
BRIEFINGS = ROOT / "briefings"


@dataclass(frozen=True)
class Article:
    topic: str
    date: str
    title: str
    lede: str
    archive_title: str
    summary: str
    body_html: str
    source_path: Path

    @property
    def href(self) -> str:
        return f"briefings/{self.topic}/{self.date}.html"

    @property
    def topic_href(self) -> str:
        return f"{self.topic}/{self.date}.html"


def esc(value: Any) -> str:
    return html.escape(str(value), quote=True)


def pretty_date(iso_date: str) -> str:
    dt = datetime.strptime(iso_date, "%Y-%m-%d")
    # Linux supports %-d; if this ever moves to Windows, lstrip the zero instead.
    return dt.strftime("%a, %b %-d, %Y")


def parse_frontmatter(text: str) -> tuple[dict[str, str], str]:
    if not text.startswith("---\n"):
        return {}, text
    end = text.find("\n---\n", 4)
    if end == -1:
        raise ValueError("front matter starts but never ends")
    raw = text[4:end]
    body = text[end + 5 :]
    meta: dict[str, str] = {}
    for line in raw.splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        key, sep, value = line.partition(":")
        if not sep:
            raise ValueError(f"bad front matter line: {line!r}")
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] == '"':
            value = value[1:-1].replace('\\"', '"').replace('\\\\', '\\')
        meta[key.strip()] = value
    return meta, body.strip()


def render_inline(text: str) -> str:
    placeholders: list[str] = []

    def stash(rendered: str) -> str:
        placeholders.append(rendered)
        return f"\u0000{len(placeholders) - 1}\u0000"

    def link_repl(match: re.Match[str]) -> str:
        label = render_inline(match.group(1))
        url = esc(match.group(2))
        return stash(f'<a href="{url}">{label}</a>')

    text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", link_repl, text)
    rendered = esc(text)
    rendered = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", rendered)
    rendered = re.sub(r"_(.+?)_", r"<em>\1</em>", rendered)
    rendered = re.sub(r"`(.+?)`", r"<code>\1</code>", rendered)
    for i, value in enumerate(placeholders):
        rendered = rendered.replace(f"\u0000{i}\u0000", value)
    return rendered


def render_markdown(md: str) -> str:
    lines = md.splitlines()
    out: list[str] = []
    paragraph: list[str] = []
    in_ul = False

    def close_paragraph() -> None:
        nonlocal paragraph
        if paragraph:
            out.append(f"      <p>{render_inline(' '.join(paragraph))}</p>")
            paragraph = []

    def close_ul() -> None:
        nonlocal in_ul
        if in_ul:
            out.append("      </ul>")
            in_ul = False

    for line in lines:
        stripped = line.strip()
        if not stripped:
            close_paragraph()
            continue
        if stripped.startswith("## "):
            close_paragraph(); close_ul()
            out.append(f"      <h2>{render_inline(stripped[3:].strip())}</h2>")
            continue
        if stripped.startswith("# "):
            # Article title is rendered by the template from front matter.
            continue
        if stripped.startswith("- "):
            close_paragraph()
            if not in_ul:
                out.append('      <ul class="meta-list">')
                in_ul = True
            out.append(f"        <li>{render_inline(stripped[2:].strip())}</li>")
            continue
        close_ul()
        paragraph.append(stripped)

    close_paragraph(); close_ul()
    return "\n".join(out)


def load_topics() -> dict[str, dict[str, Any]]:
    return json.loads((CONTENT / "topics.json").read_text())


def load_articles() -> list[Article]:
    articles: list[Article] = []
    for path in sorted(CONTENT.glob("*/*.md")):
        meta, body = parse_frontmatter(path.read_text())
        required = ["topic", "date", "title", "lede", "archiveTitle", "summary"]
        missing = [key for key in required if key not in meta]
        if missing:
            raise ValueError(f"{path} missing front matter: {', '.join(missing)}")
        articles.append(
            Article(
                topic=meta["topic"],
                date=meta["date"],
                title=meta["title"],
                lede=meta["lede"],
                archive_title=meta["archiveTitle"],
                summary=meta["summary"],
                body_html=render_markdown(body),
                source_path=path,
            )
        )
    return sorted(articles, key=lambda a: (a.topic, a.date))


def page_shell(title: str, stylesheet_prefix: str, body: str, description: str | None = None) -> str:
    desc = f'\n  <meta name="description" content="{esc(description)}" />' if description else ""
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <link rel="icon" href="{stylesheet_prefix}favicon.svg" type="image/svg+xml" />
  <title>{esc(title)}</title>{desc}
  <link rel="stylesheet" href="{stylesheet_prefix}styles.css" />
</head>
<body>
{body}
</body>
</html>
"""


def render_article(article: Article, topic: dict[str, Any]) -> str:
    body = f"""  <main class="shell page">
    <a class="back" href="../{esc(article.topic)}.html">← Back to {esc(topic['title'])}</a>
    <section class="content-card">
      <span class="date-badge large">{pretty_date(article.date)}</span>
      <h1>{esc(article.title)}</h1>
      <p class="lede">{esc(article.lede)}</p>
{article.body_html}
    </section>
  </main>"""
    return page_shell(f"{article.title} · My Interests", "../../", body)


def schedule_items(topic: dict[str, Any]) -> str:
    schedule = topic.get("schedule") or []
    if not schedule:
        return ""
    lines = ['      <h2>Schedule</h2>', '      <ul class="meta-list">']
    for item in schedule:
        lines.append(f"        <li>{render_inline(item)}</li>")
    lines.append("      </ul>")
    return "\n".join(lines) + "\n"


def render_topic_index(slug: str, topic: dict[str, Any], articles: list[Article]) -> str:
    latest = articles[0] if articles else None
    latest_label = topic.get("latestLabel") or (f"Latest: {pretty_date(latest.date)}" if latest else "No stories yet")
    archive_items: list[str]
    if articles:
        archive_items = []
        for article in articles:
            archive_items.append(f"""        <li class="archive-item">
          <a href="{esc(article.topic_href)}">
            <span class="date-badge">{pretty_date(article.date)}</span>
            <span class="archive-title">{esc(article.archive_title)}</span>
            <span class="archive-desc">{esc(article.summary)}</span>
          </a>
        </li>""")
    else:
        archive_items = ['        <li class="archive-empty">No dated stories published yet.</li>']
    body = f"""  <main class="shell page">
    <a class="back" href="../index.html">← Back to major topics</a>
    <section class="content-card {esc(topic.get('topicClass', ''))}">
      <span class="date-badge large">{esc(latest_label)}</span>
      <h1>{esc(topic['title'])}</h1>
      <p class="lede">{esc(topic['lede'])}</p>
{schedule_items(topic)}      <h2>Published stories</h2>
      <ul class="archive-list">
{chr(10).join(archive_items)}
      </ul>
    </section>
  </main>"""
    return page_shell(f"{topic['title']} · My Interests", "../", body)


def plural_story(count: int) -> str:
    return "story" if count == 1 else "stories"


def render_home(topics: dict[str, dict[str, Any]], by_topic_desc: dict[str, list[Article]]) -> str:
    # Show newest individual daily articles first for high-cadence topics, then topic archive cards.
    cards: list[str] = []
    for slug in ["india", "indonesia", "ram-market"]:
        articles = by_topic_desc.get(slug, [])
        if not articles:
            continue
        topic = topics[slug]
        article = articles[0]
        cards.append(f"""      <a class="briefing-card {esc(topic['color'])}" href="{esc(article.href)}" data-briefing="{esc(slug)}" data-date="{esc(article.date)}">
        <span class="date-badge">{pretty_date(article.date)}</span>
        <span class="icon">{esc(topic['icon'])}</span>
        <span class="label">{esc(topic['title'])} — {esc(article.archive_title)}</span>
        <span class="desc">{esc(article.summary)}</span>
      </a>""")

    for slug, topic in topics.items():
        articles = by_topic_desc.get(slug, [])
        latest_label = topic.get("latestLabel") or (f"Latest: {pretty_date(articles[0].date)}" if articles else "No stories yet")
        story_suffix = f" {len(articles)} published {plural_story(len(articles))}." if articles else ""
        cards.append(f"""      <a class="briefing-card {esc(topic['color'])}" href="briefings/{esc(slug)}.html">
        <span class="date-badge">{esc(latest_label)}</span>
        <span class="icon">{esc(topic['icon'])}</span>
        <span class="label">{esc(topic['title'])}</span>
        <span class="desc">{esc(topic['lede'])}{esc(story_suffix)}</span>
      </a>""")

    body = f"""  <main class="shell">
    <section class="hero">
      <h1>My Interests</h1>
      <p class="subtitle">Launchpad of data for my interests</p>
      <div class="status-row" aria-label="dashboard status">
        <span class="pulse"></span>
        <span>Topic pages contain the dated story archive</span>
      </div>
    </section>

    <section class="grid" aria-label="major briefing topics">
      <!-- generated from content/ by scripts/build-site.py -->
{chr(10).join(cards)}
    </section>
  </main>"""
    return page_shell("My Interests", "", body, "Launchpad of data for my interests")


def main() -> None:
    topics = load_topics()
    articles = load_articles()
    by_topic: dict[str, list[Article]] = {slug: [] for slug in topics}
    for article in articles:
        if article.topic not in topics:
            raise ValueError(f"{article.source_path} has unknown topic {article.topic!r}")
        by_topic[article.topic].append(article)
    by_topic_desc = {slug: sorted(items, key=lambda a: a.date, reverse=True) for slug, items in by_topic.items()}

    # Remove generated article pages so deleted Markdown does not leave stale HTML.
    for path in BRIEFINGS.glob("*/*.html"):
        path.unlink()
    for child in BRIEFINGS.iterdir() if BRIEFINGS.exists() else []:
        if child.is_dir() and not any(child.iterdir()):
            child.rmdir()

    BRIEFINGS.mkdir(exist_ok=True)
    (ROOT / "index.html").write_text(render_home(topics, by_topic_desc))
    for slug, topic in topics.items():
        topic_articles = by_topic_desc.get(slug, [])
        (BRIEFINGS / f"{slug}.html").write_text(render_topic_index(slug, topic, topic_articles))
        if topic_articles:
            outdir = BRIEFINGS / slug
            outdir.mkdir(exist_ok=True)
            for article in topic_articles:
                (outdir / f"{article.date}.html").write_text(render_article(article, topic))

    print(f"Built {len(articles)} articles across {len(topics)} topics")


if __name__ == "__main__":
    main()
