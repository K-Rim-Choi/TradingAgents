"""The report as one self-contained HTML page (#1419).

The page reads well in a browser, on a phone and in print. It loads nothing and
runs nothing: styles are inline, there is no script, and a Content-Security-Policy
forbids any fetch. Report text is rendered as CommonMark with raw HTML and images
off, so nothing a model wrote can inject markup or load a remote asset.
"""

from datetime import datetime
from html import escape
from importlib.resources import files

from markdown_it import MarkdownIt

from tradingagents.agents.rating import run_rating
from tradingagents.reporting import analyst_names

# Ratings by direction, so the page can show which way the call leans.
_TONE = {"Buy": "up", "Overweight": "up", "Hold": "level", "Underweight": "down", "Sell": "down"}

# The Tauric Research logo as published (tauric.ai/brand/tauric-logo.svg), drawn
# in the page so it loads nothing.
_LOGO = files("tradingagents").joinpath("assets/tauric-logo.svg").read_text(encoding="utf-8").strip()
_COMPANY = "https://tauric.ai"
_ORG = "https://github.com/TauricResearch"
_PROJECT = f"{_ORG}/TradingAgents"

_CSS = """
:root {
  --paper: #fbfbfa; --ink: #1c2126; --muted: #5d6670; --rule: #e2e5e8; --wash: #f2f4f5;
  --accent: #087a59; --up: #087a59; --down: #b4372f; --level: #5d6670; --edge: #d3d8dc; --mark: #878f97;
  --serif: Charter, "Bitstream Charter", "Sitka Text", Cambria, Georgia, serif;
  --sans: system-ui, -apple-system, "Apple SD Gothic Neo", "Malgun Gothic", "Segoe UI", Roboto, Arial, sans-serif;
  color-scheme: light dark;
}
@media (prefers-color-scheme: dark) {
  :root {
    --paper: #131a1f; --ink: #e4e8eb; --muted: #9aa6af; --rule: #263239; --wash: #1a242a;
    --accent: #14c290; --up: #14c290; --down: #ef6f63; --level: #9aa6af; --edge: #3d4c55; --mark: #66737c;
  }
}
@media (prefers-color-scheme: dark) {
  .masthead .logo [stroke="#363636"] { stroke: var(--muted); }
}
* { box-sizing: border-box; }
html { -webkit-text-size-adjust: 100%; }
body {
  margin: 0; background: var(--paper); color: var(--ink);
  font: 17px/1.85 var(--sans); font-kerning: normal;
  overflow-wrap: anywhere;
}
.page { max-width: 52rem; margin: 0 auto; padding: 3.5rem 1.5rem 6rem; }
html[lang="ko"] main { word-break: keep-all; }
.run-details { margin-top: 1.5rem; }
.run-details summary { cursor: pointer; color: var(--muted); font-size: 0.9rem; }
.run-details[open] summary { margin-bottom: 1rem; }
.decision { margin-top: 2rem; padding: 1.5rem; background: var(--wash);
  border: 1px solid var(--edge); border-left: 4px solid var(--accent); border-radius: 10px; }
.decision h2 { margin: 0 0 1rem; padding: 0; border: 0; font-size: 1.3rem; }
.decision > :last-child { margin-bottom: 0; }
.decision-note { color: var(--muted); font-size: 0.8rem; }
main h2, main h3 { scroll-margin-top: 1rem; }
a { color: var(--accent); text-underline-offset: 0.15em; }
h1, h2, h3, h4 { text-wrap: balance; }
a:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; }

.masthead { padding-bottom: 1.75rem; border-bottom: 1px solid var(--rule); }
/* The logo leads at the top left, where readers look for it, 24px tall (the usual
   on-screen floor for a wordmark) with at least its height clear below. */
.masthead .logo { display: block; width: fit-content; margin: 0 0 2.25rem; }
.masthead .logo svg { display: block; height: 1.5rem; width: auto; }
.masthead h1 {
  margin: 0; font: 600 2.6rem/1.1 var(--sans); letter-spacing: -0.02em;
  display: flex; flex-wrap: wrap; align-items: baseline; gap: 0.2em 0.5em;
}
.masthead .rating { font-weight: 500; }
.rating.up { color: var(--up); } .rating.down { color: var(--down); } .rating.level { color: var(--level); }
.rating.review { color: var(--muted); font-style: italic; }
.masthead .date { margin: 0.55rem 0 1.5rem; font: 1rem/1.4 var(--sans); color: var(--muted); }
.run { margin: 0; display: grid; grid-template-columns: max-content 1fr; gap: 0.45rem 1.25rem;
  font: 0.85rem/1.5 var(--sans); }
.run > div { display: contents; }
.run dt { color: var(--muted); }
.run dd { margin: 0; overflow-wrap: anywhere; }
.run .note dd { color: var(--down); }
.field { display: inline-block; margin: 0 0.15rem 0.15rem 0; padding: 0 0.4rem; border: 1px solid var(--edge);
  border-radius: 4px; background: var(--wash); font: 0.8rem/1.6 ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; }
.run .group { display: inline-block; margin-right: 0.9rem; white-space: nowrap; }
.run .group > .name { color: var(--muted); margin-right: 0.3rem; }
.run .then { color: var(--muted); margin: 0 0.2rem; }

/* The sections: listed under the header on narrow screens. On wide ones, a
   quiet rail centred on the left edge (numerals for the sections, short bars
   for their agents) that opens into the full list when pointed at or focused. */
.contents { margin: 2.25rem 0 0; font: 0.9rem/1.45 var(--sans); }
.contents ul { margin: 0; padding: 0; list-style: none; }
.contents > ul > li { margin: 0 0 0.75rem; }
.contents ul ul { margin-top: 0.2rem; padding-left: 1.6rem; font-size: 0.85rem; }
.contents ul ul li { margin: 0.1rem 0; }
.contents a { display: flex; align-items: center; gap: 0.6rem; color: var(--muted); text-decoration: none; }
.contents > ul > li > a { color: var(--ink); }
.contents .num { min-width: 1.6rem; color: var(--muted); font-variant-numeric: tabular-nums; }
.contents .bar { display: none; }
.contents a:hover .label, .contents a:focus-visible .label { color: var(--accent); text-decoration: underline; }
.to-top { position: fixed; right: 1rem; bottom: calc(1rem + env(safe-area-inset-bottom));
  padding: 0.25rem 0.6rem; border: 1px solid var(--edge); border-radius: 4px; background: var(--paper);
  color: var(--muted); font: 0.8rem/1.4 var(--sans); text-decoration: none; }

@media (min-width: 72rem) {
  .contents { position: fixed; left: 1rem; top: 50%; transform: translateY(-50%); z-index: 1;
    max-height: 86vh; overflow-y: auto; overscroll-behavior: contain; margin: 0;
    padding: 0.7rem 0.9rem; border: 1px solid transparent; border-radius: 6px;
    transition: background-color 0.15s, border-color 0.15s, box-shadow 0.15s; }
  .contents > ul > li { margin: 0 0 0.35rem; }
  .contents ul ul { margin-top: 0; padding-left: 0; }
  .contents ul ul li { margin: 0; }
  /* Marks reach 3:1 contrast and rows 24px, the WCAG 2.2 floors for a control's
     visual cue and its pointer target. */
  .contents a { min-height: 1.5rem; }
  .contents .num { min-width: 1.4rem; }
  .contents .bar { display: block; flex: none; width: 1.25rem; height: 2px; margin-left: 0.2rem;
    border-radius: 1px; background: var(--mark); }
  .contents .label { max-width: 0; opacity: 0; overflow: hidden; white-space: nowrap;
    transition: opacity 0.15s, max-width 0.2s; }
  .contents:hover, .contents:focus-within { background: var(--paper); border-color: var(--rule);
    box-shadow: 0 6px 24px rgb(0 0 0 / 0.08); }
  .contents:hover .label, .contents:focus-within .label { max-width: 18rem; opacity: 1; }
  .contents a:hover .bar, .contents a:focus-visible .bar { background: var(--accent); }
  .to-top { display: none; }
}
@media (prefers-reduced-motion: reduce) {
  .contents, .contents .label { transition: none; }
}

/* The maker's credit: one quiet line at the foot. */
.credit { margin-top: 4.5rem; padding-top: 1.25rem; border-top: 1px solid var(--rule);
  color: var(--muted); font: 0.8rem/1.4 var(--sans); }
.credit a { color: inherit; text-decoration: none; }
.credit a.brand { color: var(--accent); }
.credit a:hover, .credit a:focus-visible { text-decoration: underline; }

/* Three levels of separation: the five groups, the agents within a group, and
   breaks an agent draws inside its own text. */
main h2 {
  margin: 4.5rem 0 0.25rem; padding-top: 1.5rem; border-top: 2px solid var(--ink);
  font: 600 1.45rem/1.3 var(--sans); letter-spacing: -0.01em;
}
main section:first-child h2 { margin-top: 3rem; }
main h3 { margin: 2.75rem 0 0.75rem; padding-top: 1.1rem; border-top: 1px solid var(--rule);
  font: 600 1.15rem/1.35 var(--sans); color: var(--accent); }
main h2 + h3 { margin-top: 1.25rem; padding-top: 0; border-top: 0; }
main h4, main h5, main h6 { margin: 1.75rem 0 0.5rem; font: 600 1rem/1.4 var(--sans); }
main h5, main h6 { color: var(--muted); }
main p, main ul, main ol { margin: 0 0 1rem; }
main li { margin: 0.25rem 0; }
main strong { font-weight: 650; }
main blockquote { margin: 1.25rem 0; padding: 0.1rem 0 0.1rem 1rem; border-left: 3px solid var(--rule);
  color: var(--muted); }
main code { font: 0.88em/1.4 ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  background: var(--wash); padding: 0.1em 0.3em; border-radius: 3px; }
main pre { background: var(--wash); padding: 0.9rem 1rem; border-radius: 4px; overflow-x: auto; }
main pre code { background: none; padding: 0; }
main hr { width: 3rem; margin: 2rem auto; border: 0; border-top: 1px solid var(--rule); }

.table { overflow-x: auto; margin: 0 0 1.25rem; }
table { border-collapse: collapse; width: 100%; font: 0.86rem/1.45 var(--sans);
  font-variant-numeric: tabular-nums; }
th, td { padding: 0.45rem 0.7rem; text-align: left; vertical-align: top; border-bottom: 1px solid var(--rule); }
th { font-weight: 600; border-bottom-color: var(--muted); }
thead { background: var(--wash); }
tbody tr:nth-child(even) { background: var(--wash); }
td, th { min-width: 6rem; }
tbody tr:last-child td { border-bottom: 0; }

@media (max-width: 34rem) {
  body { font-size: 16px; }
  .page { padding: 2rem 1rem 3rem; }
  .masthead h1 { font-size: 2rem; }
  .masthead .logo svg { height: 1.25rem; }
  .run { grid-template-columns: 1fr; gap: 0 0; }
  .run dd { margin-bottom: 0.45rem; }
  .run .group { white-space: normal; }
}
@media print {
  :root { --paper: #fff; --ink: #000; --muted: #444; --rule: #bbb; --accent: #000; --wash: #f2f2f2;
    --edge: #bbb; --up: #087a59; --down: #b4372f; --level: #444; }
  body { font-size: 11pt; }
  .table { overflow: visible; }
  .page { max-width: none; padding: 0; }
  .contents, .to-top { display: none; }
  .run-details { display: none; }
  .decision { padding: 1rem; }
  .decision h2 { break-before: auto; }
  main h2 { break-before: page; border-top: 0; margin-top: 0; }
  main section:first-child h2 { break-before: auto; }
  main h3, main h4 { break-after: avoid; }
  a { color: inherit; text-decoration: none; }
  table { break-inside: avoid; }
}
"""


def _markdown() -> MarkdownIt:
    md = MarkdownIt("commonmark", {"html": False}).enable("table").disable("image")
    md.add_render_rule("table_open", lambda *a: '<div class="table"><table>\n')
    md.add_render_rule("table_close", lambda *a: "</table></div>\n")
    return md


def _render_agent_text(md: MarkdownIt, text: str) -> str:
    """An agent's text, its own headings placed below the agent's heading (h3)."""
    tokens = md.parse(text)
    for token in tokens:
        if token.type in ("heading_open", "heading_close"):
            token.tag = f"h{min(int(token.tag[1]) + 3, 6)}"
    return md.renderer.render(tokens, md.options, {})


# What each data category serves, as a reader would name it.
_CATEGORY = {
    "core_stock_apis": "Prices", "technical_indicators": "Indicators", "fundamental_data": "Fundamentals",
    "news_data": "News", "macro_data": "Macro", "prediction_markets": "Prediction markets",
}


def _fields(values) -> str:
    return " ".join(f'<span class="field">{escape(str(v))}</span>' for v in values)


def _chain(vendors: str) -> str:
    """A vendor chain in the order it is tried: ``a,b`` reads a, then b."""
    names = [v.strip() for v in str(vendors).split(",") if v.strip()]
    return ' <span class="then">\u2192</span> '.join(_fields([n]) for n in names)


def _group(name: str, values_html: str) -> str:
    return f'<span class="group"><span class="name">{escape(name)}</span>{values_html}</span>'


def _run_details(final_state: dict, settings: dict | None) -> list[tuple[str, str]]:
    """The run details as (label, value HTML); every value from the run is escaped."""
    details = [("Generated", escape(datetime.now().strftime("%Y-%m-%d %H:%M")))]
    if settings:
        s = settings.get
        for tier in ("deep", "quick"):
            provider = s(f"{tier}_think_provider") or s("llm_provider", "?")
            details.append((f"{tier.capitalize()} model", _fields([provider, s(f"{tier}_think_llm", "?")])))
        details.append(("Analysts", _fields(analyst_names(s("analysts")))))
        details.append(("Debate rounds", " ".join((
            _group("research", _fields([s("max_debate_rounds", "?")])),
            _group("risk", _fields([s("max_risk_discuss_rounds", "?")])),
        ))))
        vendors = {**(s("data_vendors") or {}), **(s("tool_vendors") or {})}
        if vendors:
            details.append(("Data vendors", " ".join(
                _group(_CATEGORY.get(k, k), _chain(v)) for k, v in vendors.items()
            )))
        details.append(("Version", escape(f"TradingAgents {s('version', '?')}")))
    if final_state.get("memory_note"):
        details.append(("Memory log", escape(final_state["memory_note"])))
    return details


def render_report(ticker: str, final_state: dict, settings: dict | None, parts) -> str:
    """The report page: title and rating, what produced the run, contents, sections."""
    korean = str((settings or {}).get("output_language", "")).strip().lower() in {"korean", "ko", "한국어"}
    labels = {
        "Generated": "생성 시각", "Deep model": "심층 분석 모델", "Quick model": "일반 분석 모델",
        "Analysts": "분석팀", "Debate rounds": "토론 횟수", "Data vendors": "데이터 제공자",
        "Version": "버전", "Memory log": "이전 판단 기록",
        "Analyst Team Reports": "분석팀 보고서", "Research Team Decision": "투자 논거 검토",
        "Trading Team Plan": "매매 계획", "Risk Management Team Decision": "위험관리 검토",
        "Portfolio Manager Decision": "최종 투자 판단", "Market Analyst": "기술적 분석",
        "Sentiment Analyst": "시장 심리 분석", "News Analyst": "뉴스 분석",
        "Fundamentals Analyst": "기업 재무 분석", "Bull Researcher": "상승 논거",
        "Bear Researcher": "하락 논거", "Research Manager": "투자 논거 종합",
        "Trader": "트레이더", "Aggressive Analyst": "적극적 관점", "Conservative Analyst": "보수적 관점",
        "Neutral Analyst": "중립적 관점", "Portfolio Manager": "포트폴리오 관리자",
        "Buy": "매수", "Overweight": "비중 확대", "Hold": "보유", "Underweight": "비중 축소",
        "Sell": "매도", "REVIEW": "검토 필요",
    }

    def label(value):
        return labels.get(value, value) if korean else value

    md = _markdown()
    rating = run_rating(final_state) if final_state.get("final_trade_decision") else ""
    tone = _TONE.get(rating, "review")
    date = final_state.get("trade_date", "")

    title = f'<span class="ticker">{escape(ticker)}</span>'
    if rating:
        title += f' <span class="rating {tone}">{escape(label(rating))}</span>'
    details = "".join(
        f'<div class="{"note" if key == "Memory log" else "detail"}">'
        f"<dt>{escape(label(key))}</dt><dd>{value}</dd></div>"
        for key, value in _run_details(final_state, settings)
    )

    contents, body = [], []
    for n, (heading, _folder, written) in enumerate(parts, 1):
        agents = "".join(
            f'<li><a href="#s{n}-{m}"><span class="bar"></span> <span class="label">{escape(label(agent))}</span></a></li>'
            for m, (agent, _f, _t) in enumerate(written, 1)
        )
        numeral, _, name = heading.partition(". ")
        contents.append(f'<li><a href="#s{n}"><span class="num">{escape(numeral)}</span> '
                        f'<span class="label">{escape(label(name))}</span></a><ul>{agents}</ul></li>')
        body.append(f'<section id="s{n}"><h2>{escape(numeral + ". " + label(name))}</h2>')
        for m, (agent, _filename, text) in enumerate(written, 1):
            body.append(f'<h3 id="s{n}-{m}">{escape(label(agent))}</h3>\n{_render_agent_text(md, text)}')
        body.append("</section>")

    decision = ""
    if final_state.get("final_trade_decision"):
        decision_title = "최종 투자 판단" if korean else "Final investment decision"
        note = ("포트폴리오 관리자의 원문입니다. 아래에서 분석 근거와 위험 검토를 확인하세요."
                if korean else "Portfolio manager's original decision. Supporting analysis and risk reviews follow below.")
        decision = (f'<article class="decision" aria-labelledby="decision-title">'
                    f'<h2 id="decision-title">{decision_title}</h2>'
                    f'<p class="decision-note">{note}</p>'
                    f'{_render_agent_text(md, final_state["final_trade_decision"])}</article>')
    analysis_date = f"분석 기준일: {date}" if korean else f"Analysis of {date}"
    details_title = "분석 실행 정보" if korean else "Run details"
    page_title = " ".join(x for x in (ticker, date, rating) if x)
    return f"""<!doctype html>
<html lang="{'ko' if korean else 'en'}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'">
<title>{escape(page_title)}: TradingAgents report</title>
<style>{_CSS}</style>
</head>
<body>
<div class="page" id="top">
<header class="masthead">
<a class="logo" href="{_COMPANY}" rel="noopener" aria-label="Tauric Research">{_LOGO}</a>
<h1>{title}</h1>
<p class="date">{escape(analysis_date if date else ('투자 분석 보고서' if korean else 'Analysis'))}</p>
<details class="run-details"><summary>{details_title}</summary><dl class="run">{details}</dl></details>
</header>
<main>
{decision}
<nav class="contents" aria-label="{'목차' if korean else 'Sections'}"><ul>{"".join(contents)}</ul></nav>
{"".join(body)}
</main>
<footer class="credit"><a href="{_PROJECT}" rel="noopener">TradingAgents</a> powered by <a class="brand" href="{_ORG}" rel="noopener">Tauric Research</a></footer>
</div>
<a class="to-top" href="#top">{'맨 위로' if korean else 'Top'}</a>
</body>
</html>
"""
