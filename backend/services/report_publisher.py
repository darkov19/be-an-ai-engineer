import binascii
import json
import struct
import zlib
from dataclasses import dataclass
from datetime import date, datetime, timezone
from html import escape
from pathlib import Path
from typing import Any

from psycopg.rows import dict_row


PNG_WIDTH = 1200
PNG_HEIGHT = 630


def build_report_slug(run_date: date | datetime | str) -> str:
    if isinstance(run_date, str):
        parsed = date.fromisoformat(run_date[:10])
    elif isinstance(run_date, datetime):
        parsed = run_date.date()
    else:
        parsed = run_date
    iso_year, iso_week, _ = parsed.isocalendar()
    return f"{iso_year}-W{iso_week:02d}"


def _json_value(value: Any, default: Any) -> Any:
    if value is None:
        return default
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return default
    return value


def _date_value(value: Any) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value)[:10])


def _normalize_snapshot(row: dict[str, Any]) -> dict[str, Any]:
    snapshot = _json_value(row.get("snapshot"), {})
    run_date = _date_value(row.get("run_date") or snapshot.get("run_date"))
    geo_us_eu = _json_value(row.get("geo_us_eu"), snapshot.get("geo_us_eu", {}))
    geo_india = _json_value(row.get("geo_india"), snapshot.get("geo_india", {}))
    experience_distribution = _json_value(row.get("experience_distribution"), snapshot.get("experience_distribution", {}))
    profile_fit_deltas = _json_value(row.get("profile_fit_deltas"), snapshot.get("profile_fit_deltas", {}))

    return {
        **snapshot,
        "run_date": run_date,
        "report_slug": row.get("report_slug") or snapshot.get("report_slug") or build_report_slug(run_date),
        "report_path": row.get("report_path") or snapshot.get("report_path"),
        "og_image_path": row.get("og_image_path") or snapshot.get("og_image_path"),
        "commit_sha": row.get("commit_sha") or snapshot.get("commit_sha"),
        "deployment_url": row.get("deployment_url") or snapshot.get("deployment_url"),
        "published_at": row.get("published_at") or snapshot.get("published_at"),
        "corpus_size": int(row.get("corpus_size") or snapshot.get("corpus_size") or 0),
        "per_source_counts": _json_value(row.get("per_source_counts"), snapshot.get("per_source_counts", {})),
        "eval_accuracy": row.get("eval_accuracy", snapshot.get("eval_accuracy")),
        "geo_us_eu": geo_us_eu,
        "geo_india": geo_india,
        "experience_distribution": experience_distribution,
        "profile_fit_deltas": profile_fit_deltas,
        "coverage_diagnostics": _json_value(row.get("coverage_diagnostics"), snapshot.get("coverage_diagnostics", {})),
        "accountability_summary": _json_value(row.get("accountability_summary"), snapshot.get("accountability_summary", {})),
        "profile_freshness": _json_value(row.get("profile_freshness"), snapshot.get("profile_freshness", {})),
        "report_html": row.get("report_html") or snapshot.get("report_html"),
    }


async def load_weekly_report_snapshot(conn, run_date: date) -> dict[str, Any]:
    async with conn.cursor(row_factory=dict_row) as cur:
        await cur.execute(
            """
            SELECT run_date, corpus_size, per_source_counts, eval_accuracy, report_html,
                   geo_us_eu, geo_india, report_slug, report_path, og_image_path,
                   commit_sha, deployment_url, published_at, experience_distribution,
                   profile_fit_deltas, coverage_diagnostics, accountability_summary,
                   profile_freshness, snapshot
            FROM weekly_reports
            WHERE run_date = %s
            """,
            (run_date,),
        )
        row = await cur.fetchone()
    if row is None:
        raise ValueError(f"No weekly report found for {run_date.isoformat()}")
    return _normalize_snapshot(dict(row))


async def load_latest_weekly_report_snapshot(conn) -> dict[str, Any]:
    async with conn.cursor(row_factory=dict_row) as cur:
        await cur.execute(
            """
            SELECT run_date, corpus_size, per_source_counts, eval_accuracy, report_html,
                   geo_us_eu, geo_india, report_slug, report_path, og_image_path,
                   commit_sha, deployment_url, published_at, experience_distribution,
                   profile_fit_deltas, coverage_diagnostics, accountability_summary,
                   profile_freshness, snapshot
            FROM weekly_reports
            ORDER BY run_date DESC
            LIMIT 1
            """
        )
        row = await cur.fetchone()
    if row is None:
        raise ValueError("No weekly reports are available to publish")
    return _normalize_snapshot(dict(row))


async def load_archive_rows(conn) -> list[dict[str, Any]]:
    async with conn.cursor(row_factory=dict_row) as cur:
        await cur.execute(
            """
            SELECT run_date, corpus_size, per_source_counts, eval_accuracy, report_slug,
                   report_path, og_image_path, commit_sha, deployment_url, published_at,
                   geo_us_eu, geo_india, experience_distribution, profile_fit_deltas,
                   coverage_diagnostics, accountability_summary, profile_freshness, snapshot
            FROM weekly_reports
            ORDER BY run_date DESC
            """
        )
        rows = await cur.fetchall()
    return [_normalize_snapshot(dict(row)) for row in rows]


def _fmt_date(value: Any) -> str:
    if value is None:
        return "not published"
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return escape(str(value))


def _fmt_percent(value: Any) -> str:
    if value is None:
        return "n/a"
    try:
        return f"{float(value) * 100:.1f}%"
    except (TypeError, ValueError):
        return "n/a"


def _top_skills(segment: dict[str, Any]) -> list[dict[str, Any]]:
    skills = segment.get("top_skills") or segment.get("skills") or []
    normalized = []
    for item in skills[:10]:
        if isinstance(item, str):
            normalized.append({"skill": item, "frequency": None})
        elif isinstance(item, dict):
            normalized.append({"skill": item.get("skill") or item.get("name") or "Unknown", "frequency": item.get("frequency") or item.get("count")})
    return normalized


def _skill_list_html(skills: list[dict[str, Any]]) -> str:
    if not skills:
        return '<li class="empty">No stored skills for this segment.</li>'
    items = []
    for idx, item in enumerate(skills, start=1):
        skill = escape(str(item["skill"]))
        freq = "" if item.get("frequency") is None else f'<span class="count">{escape(str(item["frequency"]))}</span>'
        items.append(f"<li><span>{idx:02d}. {skill}</span>{freq}</li>")
    return "\n".join(items)


def _source_rows(source_counts: dict[str, Any]) -> str:
    if not source_counts:
        return '<div class="metric-row"><span>No source breakdown stored</span><strong>n/a</strong></div>'
    rows = []
    for source, count in sorted(source_counts.items()):
        rows.append(f'<div class="metric-row"><span>{escape(str(source))}</span><strong>{escape(str(count))}</strong></div>')
    return "\n".join(rows)


def _experience_distribution(snapshot: dict[str, Any], segment_key: str) -> dict[str, float]:
    segment = snapshot.get(segment_key, {}) or {}
    dist = segment.get("experience_distribution") or snapshot.get("experience_distribution", {}).get(segment_key, {})
    return {
        "no_minimum": float(dist.get("no_minimum", 0) or 0),
        "three_plus": float(dist.get("three_plus", 0) or 0),
        "five_plus": float(dist.get("five_plus", 0) or 0),
        "senior_only": float(dist.get("senior_only", 0) or 0),
    }


def _experience_strip(snapshot: dict[str, Any], segment_key: str, label: str) -> str:
    dist = _experience_distribution(snapshot, segment_key)
    labels = [
        ("no_minimum", "No minimum"),
        ("three_plus", "3+ yrs"),
        ("five_plus", "5+ yrs"),
        ("senior_only", "Senior only"),
    ]
    bars = []
    for key, text in labels:
        value = max(0.0, min(1.0, dist[key]))
        width = max(4, round(value * 100))
        bars.append(f'<span class="strip-segment {key}" style="width:{width}%">{escape(text)} {_fmt_percent(value)}</span>')
    return f'<div class="strip-label">{escape(label)}</div><div class="experience-strip">{"".join(bars)}</div>'


def _fit_delta(snapshot: dict[str, Any], segment_key: str) -> str:
    segment = snapshot.get(segment_key, {}) or {}
    value = segment.get("profile_fit_delta", snapshot.get("profile_fit_deltas", {}).get(segment_key))
    if value is None:
        return "n/a"
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return "n/a"
    sign = "+" if numeric >= 0 else ""
    return f"{sign}{numeric:.2f}"


def _notes_html(notes: Any) -> str:
    if isinstance(notes, dict):
        notes = notes.get("notes") or notes.get("known_gaps") or notes.get("summary") or []
    if isinstance(notes, str):
        notes = [notes]
    if not notes:
        return "<li>No known corpus or coverage notes stored.</li>"
    return "\n".join(f"<li>{escape(str(note))}</li>" for note in notes)


def _archive_href(value: Any, fallback: str) -> str:
    href = str(value or fallback)
    if href.startswith(("http://", "https://", "/")):
        return href
    if href.startswith("reports/"):
        return f"/{href}"
    return "#"


def render_weekly_report_html(snapshot: dict[str, Any]) -> str:
    slug = escape(str(snapshot.get("report_slug") or build_report_slug(snapshot["run_date"])))
    run_date = _fmt_date(snapshot.get("run_date"))
    corpus_size = escape(str(snapshot.get("corpus_size", 0)))
    eval_accuracy = _fmt_percent(snapshot.get("eval_accuracy"))
    us_eu = snapshot.get("geo_us_eu", {}) or {}
    india = snapshot.get("geo_india", {}) or {}
    source_counts = snapshot.get("per_source_counts", {}) or {}
    og_image_path = escape(str(snapshot.get("og_image_path") or f"/reports/{slug}/og.png"))
    deployment_url = snapshot.get("deployment_url")
    canonical_url = escape(str(deployment_url or f"/reports/{slug}/"))
    commit_sha = snapshot.get("commit_sha") or "not recorded"
    accountability = snapshot.get("accountability_summary") or {}
    freshness = snapshot.get("profile_freshness") or {}
    freshness_label = freshness.get("message") or ("Profile freshness nudge: review profile before sharing." if freshness.get("is_stale") else "Profile freshness: no stale profile nudge stored.")

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Weekly AI Engineer Market Report {slug}</title>
  <meta name="description" content="Public weekly AI engineer market report for {run_date}.">
  <meta property="og:title" content="Weekly AI Engineer Market Report {slug}">
  <meta property="og:description" content="Corpus {corpus_size}, eval accuracy {eval_accuracy}, top geo-segment skills.">
  <meta property="og:type" content="article">
  <meta property="og:url" content="{canonical_url}">
  <meta property="og:image" content="{og_image_path}">
  <style>
    :root {{ color-scheme: dark; --bg:#050812; --panel:#101827; --line:#25445d; --cyan:#57d9ff; --magenta:#ff5cb8; --green:#70f2a4; --text:#f5fbff; --muted:#b8c7d9; }}
    * {{ box-sizing: border-box; }}
    body {{ margin:0; font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; background:var(--bg); color:var(--text); line-height:1.5; }}
    main {{ max-width: 1040px; margin: 0 auto; padding: 32px 20px 48px; }}
    a {{ color: var(--cyan); }}
    header {{ border-bottom:1px solid var(--line); padding-bottom:24px; margin-bottom:24px; }}
    h1 {{ font-size: clamp(2rem, 5vw, 4rem); margin: 0 0 12px; letter-spacing:0; }}
    h2 {{ font-size: 1.15rem; margin:0 0 14px; color:var(--cyan); }}
    .kicker, .muted {{ color: var(--muted); }}
    .metrics, .grid {{ display:grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); gap: 16px; }}
    .panel {{ border:1px solid var(--line); border-radius:8px; background:var(--panel); padding:18px; }}
    .metric strong {{ display:block; font-size:2rem; color:var(--green); }}
    ol {{ padding-left: 0; list-style: none; margin:0; }}
    li {{ display:flex; justify-content:space-between; gap:12px; border-bottom:1px solid rgba(255,255,255,.08); padding:8px 0; }}
    li:last-child {{ border-bottom:0; }}
    .count {{ color:var(--green); font-weight:700; }}
    .metric-row {{ display:flex; justify-content:space-between; gap:12px; padding:7px 0; border-bottom:1px solid rgba(255,255,255,.08); }}
    .metric-row:last-child {{ border-bottom:0; }}
    .experience-strip {{ display:flex; width:100%; min-height:34px; overflow:hidden; border-radius:6px; border:1px solid var(--line); margin-bottom:12px; }}
    .strip-segment {{ display:flex; align-items:center; justify-content:center; min-width:74px; padding:4px; color:#041018; font-size:.78rem; font-weight:700; text-align:center; }}
    .no_minimum {{ background:var(--green); }} .three_plus {{ background:var(--cyan); }} .five_plus {{ background:#f5d76e; }} .senior_only {{ background:var(--magenta); }}
    .strip-label {{ margin:12px 0 6px; color:var(--muted); }}
    .demo-close {{ display:none; position:fixed; top:12px; right:12px; border:1px solid var(--cyan); background:#06111d; color:var(--text); border-radius:6px; padding:10px 14px; cursor:pointer; }}
    body.demo .demo-close {{ display:block; }}
    footer {{ margin-top:28px; color:var(--muted); font-size:.92rem; }}
  </style>
</head>
<body>
  <button class="demo-close" type="button" onclick="window.history.replaceState(null, '', window.location.pathname); document.body.classList.remove('demo');">Close Demo</button>
  <main>
    <header>
      <p class="kicker">PUBLIC PORTFOLIO REPORT // {slug}</p>
      <h1>Weekly AI Engineer Market Report</h1>
      <p class="muted">Run date {run_date}. Static snapshot rendered from persisted weekly report data, not recomputed live analytics.</p>
    </header>
    <section class="metrics">
      <div class="panel metric"><span>Corpus Size</span><strong>{corpus_size}</strong></div>
      <div class="panel metric"><span>Latest Eval Accuracy</span><strong>{eval_accuracy}</strong></div>
      <div class="panel metric"><span>Commit</span><strong>{escape(str(commit_sha))}</strong></div>
    </section>
    <section class="grid" aria-label="Geo rankings">
      <div class="panel"><h2>Top 10 US/EU Remote Skills</h2><ol>{_skill_list_html(_top_skills(us_eu))}</ol></div>
      <div class="panel"><h2>Top 10 India AI Product Skills</h2><ol>{_skill_list_html(_top_skills(india))}</ol></div>
    </section>
    <section class="panel">
      <h2>Minimum Experience Thresholds</h2>
      {_experience_strip(snapshot, "geo_us_eu", "US/EU Remote")}
      {_experience_strip(snapshot, "geo_india", "India AI Product")}
    </section>
    <section class="grid">
      <div class="panel"><h2>Per-Source Breakdown</h2>{_source_rows(source_counts)}</div>
      <div class="panel"><h2>Profile Fit Delta</h2><div class="metric-row"><span>US/EU Remote</span><strong>{_fit_delta(snapshot, "geo_us_eu")}</strong></div><div class="metric-row"><span>India AI Product</span><strong>{_fit_delta(snapshot, "geo_india")}</strong></div></div>
      <div class="panel"><h2>Accountability / Loop B</h2><p>{escape(str(accountability.get("summary") or "No durable Loop B summary stored for this report."))}</p></div>
      <div class="panel"><h2>Profile Freshness</h2><p>{escape(str(freshness_label))}</p></div>
    </section>
    <section class="panel"><h2>Known Corpus / Coverage Notes</h2><ul>{_notes_html(snapshot.get("coverage_diagnostics"))}</ul></section>
    <footer>Public unauthenticated static artifact. Report URL: {canonical_url}</footer>
  </main>
  <script>if (new URLSearchParams(window.location.search).get('demo') === 'true') document.body.classList.add('demo');</script>
</body>
</html>
"""


def render_archive_html(rows: list[dict[str, Any]]) -> str:
    normalized = sorted((_normalize_snapshot(row) for row in rows), key=lambda row: row["run_date"], reverse=True)
    if not normalized:
        list_html = '<p class="empty">No weekly reports have been published yet.</p>'
    else:
        items = []
        for row in normalized:
            slug = row["report_slug"]
            href = _archive_href(row.get("report_path"), f"/reports/{slug}/")
            commit = row.get("commit_sha") or "not recorded"
            deployment = row.get("deployment_url")
            deploy_link = f'<a href="{escape(str(deployment))}">deployment</a>' if deployment else "deployment not recorded"
            items.append(
                f"""<article>
  <h2><a href="{escape(str(href))}">{escape(str(slug))}</a></h2>
  <p>Run date: {escape(_fmt_date(row.get("run_date")))} | Corpus: {escape(str(row.get("corpus_size", 0)))} | Eval accuracy: {_fmt_percent(row.get("eval_accuracy"))}</p>
  <p>Commit: {escape(str(commit))} | {deploy_link}</p>
</article>"""
            )
        list_html = "\n".join(items)

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Weekly AI Engineer Report Archive</title>
  <style>
    body {{ margin:0; font-family: Inter, ui-sans-serif, system-ui, sans-serif; background:#050812; color:#f5fbff; }}
    main {{ max-width: 920px; margin: 0 auto; padding: 32px 20px 48px; }}
    a {{ color:#57d9ff; }}
    h1 {{ font-size: clamp(2rem, 5vw, 3.5rem); margin-bottom: 8px; letter-spacing:0; }}
    article, .empty {{ border:1px solid #25445d; border-radius:8px; background:#101827; padding:18px; margin:16px 0; }}
    p {{ color:#b8c7d9; }}
  </style>
</head>
<body>
  <main>
    <h1>Weekly Report Archive</h1>
    <p>Public unauthenticated portfolio snapshots, sorted newest first.</p>
    {list_html}
  </main>
</body>
</html>
"""


@dataclass
class _Canvas:
    width: int
    height: int
    color: tuple[int, int, int]

    def __post_init__(self) -> None:
        self.pixels = bytearray(self.color * self.width * self.height)

    def rect(self, x: int, y: int, width: int, height: int, color: tuple[int, int, int]) -> None:
        for py in range(max(0, y), min(self.height, y + height)):
            for px in range(max(0, x), min(self.width, x + width)):
                idx = (py * self.width + px) * 3
                self.pixels[idx:idx + 3] = bytes(color)

    def text(self, text: str, x: int, y: int, scale: int, color: tuple[int, int, int]) -> None:
        cx = x
        for char in text.upper():
            pattern = FONT.get(char, FONT[" "])
            for row_idx, row in enumerate(pattern):
                for col_idx, bit in enumerate(row):
                    if bit == "1":
                        self.rect(cx + col_idx * scale, y + row_idx * scale, scale, scale, color)
            cx += 6 * scale

    def png(self) -> bytes:
        raw = bytearray()
        stride = self.width * 3
        for y in range(self.height):
            raw.append(0)
            start = y * stride
            raw.extend(self.pixels[start:start + stride])
        return _png_chunk(b"IHDR", struct.pack(">IIBBBBB", self.width, self.height, 8, 2, 0, 0, 0)) + _png_chunk(b"IDAT", zlib.compress(bytes(raw), 9)) + _png_chunk(b"IEND", b"")


def _png_chunk(kind: bytes, data: bytes) -> bytes:
    return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", binascii.crc32(kind + data) & 0xFFFFFFFF)


FONT = {
    " ": ["00000"] * 7,
    "A": ["01110", "10001", "10001", "11111", "10001", "10001", "10001"],
    "B": ["11110", "10001", "10001", "11110", "10001", "10001", "11110"],
    "C": ["01111", "10000", "10000", "10000", "10000", "10000", "01111"],
    "D": ["11110", "10001", "10001", "10001", "10001", "10001", "11110"],
    "E": ["11111", "10000", "10000", "11110", "10000", "10000", "11111"],
    "F": ["11111", "10000", "10000", "11110", "10000", "10000", "10000"],
    "G": ["01111", "10000", "10000", "10011", "10001", "10001", "01111"],
    "H": ["10001", "10001", "10001", "11111", "10001", "10001", "10001"],
    "I": ["11111", "00100", "00100", "00100", "00100", "00100", "11111"],
    "J": ["00111", "00010", "00010", "00010", "00010", "10010", "01100"],
    "K": ["10001", "10010", "10100", "11000", "10100", "10010", "10001"],
    "L": ["10000", "10000", "10000", "10000", "10000", "10000", "11111"],
    "M": ["10001", "11011", "10101", "10101", "10001", "10001", "10001"],
    "N": ["10001", "11001", "10101", "10011", "10001", "10001", "10001"],
    "O": ["01110", "10001", "10001", "10001", "10001", "10001", "01110"],
    "P": ["11110", "10001", "10001", "11110", "10000", "10000", "10000"],
    "Q": ["01110", "10001", "10001", "10001", "10101", "10010", "01101"],
    "R": ["11110", "10001", "10001", "11110", "10100", "10010", "10001"],
    "S": ["01111", "10000", "10000", "01110", "00001", "00001", "11110"],
    "T": ["11111", "00100", "00100", "00100", "00100", "00100", "00100"],
    "U": ["10001", "10001", "10001", "10001", "10001", "10001", "01110"],
    "V": ["10001", "10001", "10001", "10001", "10001", "01010", "00100"],
    "W": ["10001", "10001", "10001", "10101", "10101", "10101", "01010"],
    "X": ["10001", "10001", "01010", "00100", "01010", "10001", "10001"],
    "Y": ["10001", "10001", "01010", "00100", "00100", "00100", "00100"],
    "Z": ["11111", "00001", "00010", "00100", "01000", "10000", "11111"],
    "0": ["01110", "10001", "10011", "10101", "11001", "10001", "01110"],
    "1": ["00100", "01100", "00100", "00100", "00100", "00100", "01110"],
    "2": ["01110", "10001", "00001", "00010", "00100", "01000", "11111"],
    "3": ["11110", "00001", "00001", "01110", "00001", "00001", "11110"],
    "4": ["10010", "10010", "10010", "11111", "00010", "00010", "00010"],
    "5": ["11111", "10000", "10000", "11110", "00001", "00001", "11110"],
    "6": ["01110", "10000", "10000", "11110", "10001", "10001", "01110"],
    "7": ["11111", "00001", "00010", "00100", "01000", "01000", "01000"],
    "8": ["01110", "10001", "10001", "01110", "10001", "10001", "01110"],
    "9": ["01110", "10001", "10001", "01111", "00001", "00001", "01110"],
    "-": ["00000", "00000", "00000", "11111", "00000", "00000", "00000"],
    "/": ["00001", "00001", "00010", "00100", "01000", "10000", "10000"],
    ".": ["00000", "00000", "00000", "00000", "00000", "01100", "01100"],
    "%": ["11001", "11010", "00100", "01000", "10110", "00110", "00000"],
    ":": ["00000", "01100", "01100", "00000", "01100", "01100", "00000"],
}


def _headline(snapshot: dict[str, Any]) -> str:
    corpus = snapshot.get("corpus_size", 0)
    return f"{corpus} JOB SIGNALS"


def _skill_line(snapshot: dict[str, Any], key: str) -> str:
    names = [str(item["skill"]) for item in _top_skills(snapshot.get(key, {}) or {})[:3]]
    return " / ".join(names)[:34] if names else "NO STORED SKILLS"


def generate_og_image_png(snapshot: dict[str, Any]) -> bytes:
    canvas = _Canvas(PNG_WIDTH, PNG_HEIGHT, (5, 8, 18))
    canvas.rect(0, 0, PNG_WIDTH, 12, (87, 217, 255))
    canvas.rect(0, PNG_HEIGHT - 14, PNG_WIDTH, 14, (255, 92, 184))
    canvas.rect(42, 48, 1116, 534, (16, 24, 39))
    canvas.rect(42, 48, 1116, 4, (37, 68, 93))
    canvas.text("WEEKLY AI ENGINEER REPORT", 78, 86, 8, (87, 217, 255))
    canvas.text(str(snapshot.get("report_slug") or build_report_slug(snapshot["run_date"])), 78, 146, 6, (184, 199, 217))
    canvas.text(_headline(snapshot), 78, 218, 15, (112, 242, 164))
    canvas.text(f"EVAL {_fmt_percent(snapshot.get('eval_accuracy'))}", 78, 346, 7, (245, 215, 110))
    canvas.text("US/EU " + _skill_line(snapshot, "geo_us_eu"), 78, 430, 6, (245, 251, 255))
    canvas.text("INDIA " + _skill_line(snapshot, "geo_india"), 78, 486, 6, (245, 251, 255))
    return b"\x89PNG\r\n\x1a\n" + canvas.png()


def write_report_assets(snapshot: dict[str, Any], output_root: Path | str, archive_rows: list[dict[str, Any]] | None = None) -> dict[str, Path]:
    root = Path(output_root)
    slug = str(snapshot.get("report_slug") or build_report_slug(snapshot["run_date"]))
    report_dir = root / "reports" / slug
    archive_dir = root / "archive"
    report_dir.mkdir(parents=True, exist_ok=True)
    archive_dir.mkdir(parents=True, exist_ok=True)

    enriched = {**snapshot, "report_slug": slug, "report_path": f"/reports/{slug}/index.html", "og_image_path": f"/reports/{slug}/og.png"}
    report_path = report_dir / "index.html"
    og_path = report_dir / "og.png"
    archive_path = archive_dir / "index.html"
    rows_for_archive = [enriched]
    if archive_rows is not None:
        rows_for_archive = []
        replaced = False
        for row in archive_rows:
            if _date_value(row.get("run_date")) == _date_value(enriched.get("run_date")):
                rows_for_archive.append({**row, **enriched})
                replaced = True
            else:
                rows_for_archive.append(row)
        if not replaced:
            rows_for_archive.append(enriched)

    report_path.write_text(render_weekly_report_html(enriched), encoding="utf-8")
    og_path.write_bytes(generate_og_image_png(enriched))
    archive_path.write_text(render_archive_html(rows_for_archive), encoding="utf-8")
    return {"report_html": report_path, "og_image": og_path, "archive_html": archive_path}


def build_scheduler_snapshot(
    run_date: date,
    corpus_size: int,
    source_counts: dict[str, Any],
    eval_accuracy: float | None,
    summary: dict[str, Any],
) -> dict[str, Any]:
    slug = build_report_slug(run_date)
    return {
        "run_date": run_date.isoformat(),
        "report_slug": slug,
        "corpus_size": corpus_size,
        "per_source_counts": source_counts,
        "eval_accuracy": eval_accuracy,
        "geo_us_eu": summary.get("geo_us_eu", {}),
        "geo_india": summary.get("geo_india", {}),
        "experience_distribution": summary.get("experience_distribution", {}),
        "profile_fit_deltas": summary.get("profile_fit_deltas", {}),
        "coverage_diagnostics": summary.get("coverage_diagnostics", {"notes": ["Coverage diagnostics unavailable for this scheduler run."]}),
        "accountability_summary": summary.get("accountability_summary", {"summary": "No durable Loop B ledger summary stored for this report."}),
        "profile_freshness": summary.get("profile_freshness", {}),
        "published_at": datetime.now(timezone.utc).isoformat(),
    }
