"""Build the self-contained CampusLoop report from saved evidence."""
import base64
import json
from pathlib import Path
from string import Template

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "report.html"
SHOTS = ROOT / "output" / "screenshots"


def embedded(filename: str, alt: str, cls: str = "") -> str:
    data = base64.b64encode((SHOTS / filename).read_bytes()).decode("ascii")
    css = f' class="{cls}"' if cls else ""
    return f'<img{css} src="data:image/png;base64,{data}" alt="{alt}">'


home = embedded("refined-home-final.png", "CampusLoop home page with the moving-in and moving-out entry cards")
find = embedded("refined-filter-results-final.png", "Find Items page filtering down to one clearly labeled demonstration item")
plan = embedded("report-plan-detail.png", "Saved real gpt-6-luna plan showing a validated Floor lamp and Lamp match")
handoff = embedded("focused-reservation-no-appointment-card.png", "Accepted fictional reservation showing its general meeting area, unagreed pickup time, available listing window, and role-specific confirmation action")
date_failure = embedded("report-date-check.png", "Historical Browser QA form screenshot with a clear no-overlapping-dates warning")
donation = embedded("focused-donation-guide-yale-swap-room-card.png", "Yale Graduate Housing Swap Room card showing its source-linked location, commonly exchanged examples, contact, schedule note, eligibility caveat, and acceptance warning")

cost = json.loads((ROOT / "output" / "cost_calculations.json").read_text())
comparison = json.loads((ROOT / "output" / "baseline_efficient_comparison.json").read_text())
verification = json.loads((ROOT / "output" / "refinement_verification.json").read_text())
workflow = json.loads((ROOT / "output" / "workflow_results.json").read_text())
safety = json.loads((ROOT / "output" / "safety_tests.json").read_text())

plan_use = cost["measured_tool_using_plan"]
price_range = cost["public_rate_reference_cost_usd"]
monthly = cost["monthly_scenarios"]
base, efficient = comparison["runs"]

request_rows = [
    ("1", "retrieve_selected_needs", "640", "0", "106", "3,372", "1"),
    ("2", "retrieve_available_listings", "905", "0", "71", "1,826", "1"),
    ("3", "check_match", "1,147", "0", "82", "2,779", "1"),
    ("4", "validate_proposed_plan", "1,249", "1,144", "117", "2,305", "1"),
    ("5", "final response", "1,495", "1,174", "224", "3,749", "0"),
]
request_table = "\n".join(
    f"<tr><td>{n}</td><td><code>{tool}</code></td><td>{inp}</td><td>{cached}</td><td>{out}</td><td>{latency}</td><td>{calls}</td></tr>"
    for n, tool, inp, cached, out, latency, calls in request_rows
)

html = Template(r'''<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>CampusLoop — Final Project Report</title>
<style>
  @page { size: letter; margin: .42in .53in .48in; }
  * { box-sizing: border-box; }
  :root { --ink:#263b31; --green:#496f55; --leaf:#91b183; --cream:#f4f1e7; --paper:#fffefa; --line:#d8dfd2; --muted:#64746a; --warn:#8e641e; }
  html { background:#ecefe9; color:var(--ink); }
  body { margin:0; font:10.5pt/1.4 -apple-system,BlinkMacSystemFont,"Segoe UI",Arial,sans-serif; background:#ecefe9; }
  .page { width:8.5in; min-height:10.05in; margin:.28in auto; padding:.42in .48in .46in; background:var(--paper); box-shadow:0 2px 18px #17251a18; position:relative; break-after:page; page-break-after:always; }
  .page:last-child { break-after:auto; page-break-after:auto; }
  .pagehead { display:flex; justify-content:space-between; align-items:center; border-bottom:1px solid var(--line); padding-bottom:.12in; margin-bottom:.22in; color:var(--muted); font:8pt/1.2 ui-monospace,SFMono-Regular,Menlo,monospace; letter-spacing:.08em; text-transform:uppercase; }
  h1,h2,h3 { font-family:Georgia,"Times New Roman",serif; font-weight:500; line-height:1.05; color:var(--ink); }
  h1 { font-size:37pt; margin:0 0 .18in; letter-spacing:-.035em; }
  h2 { font-size:25pt; margin:0 0 .15in; letter-spacing:-.02em; }
  h3 { font-size:15pt; margin:.15in 0 .07in; }
  p { margin:.06in 0 .13in; }
  .lead { font-size:14pt; line-height:1.4; max-width:6.7in; color:#43574b; }
  .kicker { color:var(--green); font:8pt/1.4 ui-monospace,SFMono-Regular,Menlo,monospace; letter-spacing:.14em; text-transform:uppercase; margin:0 0 .11in; }
  .folio { position:absolute; bottom:.17in; left:.48in; right:.48in; display:flex; justify-content:space-between; border-top:1px solid var(--line); padding-top:.08in; color:#718074; font:7.5pt ui-monospace,SFMono-Regular,Menlo,monospace; }
  .pill { display:inline-block; background:#e7eee2; color:#3b6045; border-radius:30px; padding:.06in .11in; font-size:8.5pt; }
  .warn { background:#f5f0df; border-left:3px solid #b78a31; padding:.11in .14in; color:#674c1a; }
  .callout { border:1px solid var(--line); border-radius:7px; background:#f4f7f0; padding:.14in .17in; }
  .grid2 { display:grid; grid-template-columns:1fr 1fr; gap:.15in; }
  .grid3 { display:grid; grid-template-columns:repeat(3,1fr); gap:.12in; }
  .stat { background:#eff3eb; border:1px solid var(--line); border-radius:7px; padding:.14in; min-height:.86in; }
  .stat b { display:block; font:22pt/1 Georgia,"Times New Roman",serif; color:var(--green); margin-bottom:.04in; }
  .stat span { color:var(--muted); font-size:8.6pt; }
  table { width:100%; border-collapse:collapse; margin:.12in 0 .16in; font-size:8.7pt; line-height:1.28; }
  th { background:#eaf0e5; color:#344a3c; text-align:left; font-size:8pt; text-transform:uppercase; letter-spacing:.04em; }
  th,td { border:1px solid var(--line); padding:.075in .085in; vertical-align:top; }
  td code { font-size:8pt; overflow-wrap:anywhere; }
  .small { font-size:8.5pt; color:var(--muted); }
  .tiny { font-size:7.7pt; color:var(--muted); }
  .figure { margin:.1in 0 .14in; break-inside:avoid; page-break-inside:avoid; }
  .figure img { width:100%; max-height:4.3in; object-fit:contain; display:block; border:1px solid #d9ded6; border-radius:5px; background:#f4f5f1; }
  .figure img.short { max-height:3.5in; }
  .figure img.tall { max-height:4.15in; }
  figcaption { margin-top:.05in; color:#66736a; font-size:8pt; line-height:1.25; }
  .twocol { display:grid; grid-template-columns:1fr 1fr; gap:.15in; align-items:start; }
  .runtrace { margin:.08in 0; padding-left:.22in; }
  .runtrace li { margin:.05in 0 .1in; padding-left:.03in; }
  .tool-inventory { display:grid; grid-template-columns:1fr 1fr; column-gap:.2in; row-gap:.035in; margin:.06in 0 .12in; padding-left:.2in; font-size:8.5pt; line-height:1.22; }
  .tool-inventory li { margin:0; padding-left:.02in; break-inside:avoid; page-break-inside:avoid; }
  .sources li { margin:.07in 0; font-size:8.4pt; overflow-wrap:anywhere; }
  a { color:#3f6c49; text-decoration:underline; text-underline-offset:2px; }
  code { color:#385140; }
  .hero { min-height:8.85in; display:flex; flex-direction:column; justify-content:space-between; }
  .heroTop { padding-top:.35in; }
  .heroTitle { font-size:46pt; max-width:6.2in; margin:.15in 0 .22in; }
  .mark { color:#608964; font-style:italic; }
  .heroMeta { border-top:1px solid var(--line); padding-top:.15in; display:grid; grid-template-columns:1fr 1fr; gap:.2in .22in; align-items:start; font-size:9.5pt; }
  .heroMeta > div { min-width:0; display:flex; flex-direction:column; align-items:flex-start; gap:.045in; overflow-wrap:anywhere; }
  .heroMeta .metaValue { display:block; min-width:0; line-height:1.3; overflow-wrap:anywhere; word-break:break-word; }
  .heroMeta .metaValue a { overflow-wrap:anywhere; word-break:break-word; }
  .heroMeta .metaNote { display:block; line-height:1.25; }
  .sourceLine { border-top:1px solid var(--line); padding-top:.08in; margin-top:.13in; }
  .svgbox { width:100%; height:auto; display:block; margin:.12in 0 .16in; }
  .endnote { border-left:2px solid var(--leaf); padding-left:.12in; color:var(--muted); font-size:8.5pt; }
  @media screen { .page { border-radius:3px; } }
  @media print {
    html,body { background:white; }
    .page { width:auto; min-height:10.03in; margin:0; padding:.02in .02in .22in; box-shadow:none; }
    .folio { left:.02in; right:.02in; bottom:0; }
    a { color:inherit; }
    .figure img { max-height:4.1in; }
    .heroTitle { font-size:42pt; margin:.08in 0 .12in; }
    .hero .lead { font-size:13pt; }
    .heroTop > .figure { margin-top:.05in !important; }
    .hero .figure img { max-height:3.15in; }
  }
</style>
</head>
<body>
<section class="page">
 <div class="hero">
  <div class="heroTop">
   <div class="pagehead"><span>AI Applications · Final project report</span><span>Evidence review · 25 October 2026</span></div>
   <p class="kicker">CampusLoop / New Haven</p>
   <h1 class="heroTitle">A softer landing,<br><span class="mark">on both sides</span><br>of move day.</h1>
   <p class="lead">CampusLoop is a local prototype that helps students moving out list useful belongings, helps students moving in find them, and checks whether a proposed handoff fits dates, quantity, availability, and transport.</p>
   <figure class="figure" style="margin-top:.28in">$home<figcaption>Home page. The hero and two move-direction entry points live on this dedicated page.</figcaption></figure>
  </div>
  <div>
   <div class="heroMeta">
    <div><b>Prepared by</b><span class="metaValue">Victoria Woods</span></div>
    <div><b>Project boundary</b><span class="metaValue">Independent class project; not a Yale service or endorsement.</span></div>
    <div><b>Local app URL</b><span class="metaValue"><a href="http://127.0.0.1:5173">http://127.0.0.1:5173</a></span><span class="tiny metaNote">Only works while the local app is running on this computer.</span></div>
    <div><b>Public GitHub repository</b><span class="metaValue"><a href="https://github.com/victoriagwoods2/CampusLoop">https://github.com/victoriagwoods2/CampusLoop</a></span></div>
   </div>
   <p class="sourceLine small">Independent student testing was not conducted. The public source repository is linked above.</p>
  </div>
 </div>
 <div class="folio"><span>CampusLoop · Victoria Woods</span><span>01 / 14</span></div>
</section>

<section class="page">
 <div class="pagehead"><span>02 · Motivation</span><span>Problem framing</span></div>
 <p class="kicker">A recurring transition problem</p>
 <h2>Moving creates two connected problems.</h2>
 <p class="lead">This project grew from my own experience moving repeatedly as a student: useful belongings can be left behind or discarded at move-out, while a student arriving later may spend money replacing similar essentials.</p>
 <p>The two moments are separated by time, different schedules, and uncertain logistics. A listing alone does not tell an arriving student whether an item will still exist on pickup day, whether enough quantity remains, or whether someone without a car can move it. A need list alone does not show which nearby item is feasible to collect.</p>
 <div class="grid2" style="margin:.2in 0">
  <div class="callout"><p class="kicker">Moving out</p><h3>Useful items need a next home.</h3><p>Students need a clear way to describe condition, quantity, pickup deadline, and whether an item needs a vehicle.</p></div>
  <div class="callout"><p class="kicker">Moving in</p><h3>Essentials need a workable pickup.</h3><p>Students need to compare items against arrival dates, availability windows, location, and transport limits before requesting them.</p></div>
 </div>
 <h3>Product hypothesis</h3>
 <p>If a local tool joins listings and needs with deterministic timing and transport checks, then students may be able to identify workable reuse handoffs and clearer donation next steps. This is the hypothesis behind the prototype, not a measured impact claim.</p>
 <div class="warn"><b>Evidence boundary.</b> The project has no participant study yet. The report does not claim reduced waste, lower student spending, carbon savings, or actual reuse outcomes from the fictional demo workflow.</div>
 <div class="folio"><span>Section 2 · Motivation</span><span>02 / 14</span></div>
</section>

<section class="page">
 <div class="pagehead"><span>03 · What is new</span><span>Existing alternatives</span></div>
 <p class="kicker">A specific workflow focus</p>
 <h2>CampusLoop enters an existing reuse landscape.</h2>
 <p>Students already have community and campus options. Buy Nothing’s official site describes free giving and getting through its app and Facebook groups [1]. Yale Graduate Housing’s Sustainable Living page describes community programs including Spring Salvage [2], and a dedicated Swap Room page gives specific location and program information [3]. The Greater New Haven ReStore is another local option for donating goods [4,5]. CampusLoop complements these channels rather than claiming to invent student reuse.</p>
 <table>
  <thead><tr><th>Alternative</th><th>Verified description</th><th>CampusLoop’s product focus</th></tr></thead>
  <tbody>
   <tr><td><b>Buy Nothing Project</b></td><td>Its official site invites people to give and get items for free through local groups in the app or on Facebook [1].</td><td>CampusLoop records a student’s requested items, dates, transport constraints, and a two-sided handoff status in one local prototype.</td></tr>
   <tr><td><b>Yale Graduate Housing programs</b></td><td>The Sustainable Living page describes the Community Garden, Spring Salvage, events, and volunteer opportunities [2]. The dedicated Swap Room page lists 533 Prospect Street, basement level; commonly exchanged clothing/shoes, household/kitchen goods, small appliances, books/school/office supplies, and toys/children’s items; and contact information [3].</td><td>Swap Room hours vary; Yale Connect provides current schedules and announcements. Eligibility for graduate students in private housing is not explicit and requires confirmation. Published categories do not guarantee acceptance of every item.</td></tr>
   <tr><td><b>Habitat for Humanity of Greater New Haven ReStore</b></td><td>A donation-based retail store with an official item acceptance list and donation instructions [4,5].</td><td>CampusLoop links people to the source when no feasible student match exists; the organization makes the acceptance decision.</td></tr>
  </tbody>
 </table>
 <div class="callout"><b>What this prototype contributes:</b> one flow joins item records to requested needs, deterministic feasibility checks, explicit reservation decisions, and confirmation by both people. This describes CampusLoop’s design; it does not assert that other channels lack these capabilities.</div>
 <p class="small">CampusLoop focuses on item-level student listings and needs, with deterministic checks for date, quantity, status, and transport compatibility. This prototype uses only its own records; it does not read Swap Room stock or connect to Yale systems. No partnership, endorsement, or automatic contact is claimed.</p>
 <div class="folio"><span>Section 3 · Alternatives</span><span>03 / 14</span></div>
</section>

<section class="page">
 <div class="pagehead"><span>04 · What is new</span><span>Interface and scope</span></div>
 <p class="kicker">One clear starting point</p>
 <h2>Each page now starts with its own job.</h2>
 <p>The large hero and move-in/move-out cards are confined to Home. Find Items, Moving In, Moving Out, Handoffs, Donation Guide, and Project Evidence open directly on their own headings and primary actions. Project Evidence sits in secondary navigation.</p>
 <p>Moving Out puts personal listings first and opens the form with <b>Add an item</b>; Moving In puts needs first and uses <b>Add a request</b>. Less common form fields sit under <b>More details</b>. Functional labels, buttons, and status text were enlarged while retaining the existing green/cream palette and typography.</p>
 <div class="twocol">
  <figure class="figure">$home<figcaption>Home alone carries the large introduction and direction cards.</figcaption></figure>
  <figure class="figure">$find<figcaption>Find Items provides search and filters. This filtered view shows one clearly labeled demonstration listing.</figcaption></figure>
 </div>
 <p class="small">Other refinements: plan cards are scoped to the signed-in user, direction, selected records, and unchanged record snapshot; edits make a prior plan stale. Handoffs emphasizes pending requests, accepted reservations, and completed pickups. Page counts now describe page-specific records.</p>
 <div class="folio"><span>Section 3 · Interface</span><span>04 / 14</span></div>
</section>

<section class="page">
 <div class="pagehead"><span>05 · Agent design</span><span>Architecture and tools</span></div>
 <p class="kicker">A bounded tool-using planner</p>
 <h2>The model proposes; application code verifies.</h2>
 <svg class="svgbox" viewBox="0 0 920 365" role="img" aria-label="CampusLoop architecture diagram">
  <defs><marker id="arr" markerWidth="9" markerHeight="9" refX="7" refY="4.5" orient="auto"><path d="M0 0L9 4.5L0 9Z" fill="#63856a"/></marker></defs>
  <rect x="14" y="42" width="180" height="86" rx="12" fill="#eef3e9" stroke="#9caf94"/><text x="104" y="76" text-anchor="middle" font-size="16" fill="#263b31">React + Vite UI</text><text x="104" y="102" text-anchor="middle" font-size="12" fill="#53665a">lists · plans · actions</text>
  <rect x="256" y="42" width="190" height="86" rx="12" fill="#f5f2e8" stroke="#c3b991"/><text x="351" y="76" text-anchor="middle" font-size="16" fill="#263b31">FastAPI</text><text x="351" y="102" text-anchor="middle" font-size="12" fill="#53665a">auth · routes · checks</text>
  <rect x="516" y="22" width="185" height="92" rx="12" fill="#eef3e9" stroke="#9caf94"/><text x="608" y="58" text-anchor="middle" font-size="15" fill="#263b31">SQLite database</text><text x="608" y="82" text-anchor="middle" font-size="11" fill="#53665a">accounts · listings · needs</text><text x="608" y="99" text-anchor="middle" font-size="11" fill="#53665a">reservations · plans · usage</text>
  <rect x="516" y="154" width="185" height="90" rx="12" fill="#f5f2e8" stroke="#c3b991"/><text x="608" y="190" text-anchor="middle" font-size="15" fill="#263b31">Deterministic core</text><text x="608" y="215" text-anchor="middle" font-size="11" fill="#53665a">dates · quantity · status</text><text x="608" y="232" text-anchor="middle" font-size="11" fill="#53665a">condition · transport</text>
  <rect x="759" y="42" width="145" height="86" rx="12" fill="#e6eee1" stroke="#85a184"/><text x="831" y="74" text-anchor="middle" font-size="15" fill="#263b31">Portkey</text><text x="831" y="99" text-anchor="middle" font-size="12" fill="#53665a">gpt-6-luna</text>
  <rect x="759" y="160" width="145" height="112" rx="12" fill="#f4f7f0" stroke="#9caf94"/><text x="831" y="188" text-anchor="middle" font-size="14" fill="#263b31">Python tools</text><text x="831" y="212" text-anchor="middle" font-size="10.5" fill="#53665a">retrieve · check</text><text x="831" y="230" text-anchor="middle" font-size="10.5" fill="#53665a">resources · validate</text><text x="831" y="250" text-anchor="middle" font-size="10.5" fill="#53665a">no reservation writes</text>
  <path d="M194 85H251" stroke="#63856a" stroke-width="2" marker-end="url(#arr)"/><path d="M446 75H510" stroke="#63856a" stroke-width="2" marker-end="url(#arr)"/><path d="M446 105C480 105 480 199 510 199" fill="none" stroke="#63856a" stroke-width="2" marker-end="url(#arr)"/><path d="M701 68H753" stroke="#63856a" stroke-width="2" marker-end="url(#arr)"/><path d="M831 128V154" stroke="#63856a" stroke-width="2" marker-end="url(#arr)"/>
  <text x="343" y="310" text-anchor="middle" font-size="12" fill="#53665a">A validated plan returns to the UI; a person still requests the item.</text>
  <path d="M608 246C608 295 351 295 351 135" fill="none" stroke="#63856a" stroke-width="2" stroke-dasharray="6 5" marker-end="url(#arr)"/>
 </svg>
 <p>CampusLoop uses React/Vite, FastAPI, SQLite, and the Responses API through Portkey; PydanticAI is not in the runtime. One bounded agent suits this short, sequential task over shared records; multiple agents would have no independent subproblem. Application code rechecks proposed IDs and quantities, while reservation and pickup remain explicit user actions.</p>
 <p class="small"><b>Model selection.</b> I chose the course-key option, which requires <code>gpt-6-luna</code> through Portkey [9]. The assignment also permits other models with a personal key. The implementation pins this choice, and the saved real run succeeded; no comparative model-quality study was performed.</p>
 <table>
  <thead><tr><th>Implemented limit</th><th>Code-level behavior</th></tr></thead>
  <tbody>
   <tr><td>Model loop</td><td>At most 6 Responses API requests, 8 function calls total, and 700 output tokens requested per response. After 4 calls, the next request sets <code>tool_choice="none"</code> to require a final text response.</td></tr>
   <tr><td>Timeouts</td><td>25-second OpenAI client timeout; 0 automatic retries.</td></tr>
   <tr><td>Plan input</td><td>At most 10 listing IDs and 10 need IDs by request schema, with 20 combined in the shared validator. Context is capped at 800 characters by the schema and 3,200 UTF-8 bytes by validation.</td></tr>
   <tr><td>Tool inputs/results</td><td>ID-array arguments allow at most 10 IDs; candidate listing/need tools return up to 20 records (database scans are capped at 40); donation resources return up to 10. Each JSON tool result is capped at 24,000 UTF-8 bytes.</td></tr>
   <tr><td>Account rate</td><td>At most 5 planning runs per account in a rolling 24-hour window.</td></tr>
  </tbody>
 </table>
 <p class="tiny">These are implemented limits from <code>backend/agent.py</code>, <code>backend/core.py</code>, and <code>backend/app.py</code>; they describe the current planner and are not a broader security guarantee.</p>
 <div class="endnote">The planner cannot reserve an item, agree an appointment, confirm a physical pickup, message anyone, or see secrets. Reservation and handoff writes use separate API routes and explicit account actions.</div>
 <div class="folio"><span>Section 4 · Agent design</span><span>05 / 14</span></div>
</section>

<section class="page">
 <div class="pagehead"><span>06 · Real run trace</span><span>Portkey · gpt-6-luna</span></div>
 <p class="kicker">A saved successful planning run</p>
 <h2>One request found one grounded lamp match.</h2>
 <p>On 25 October 2026, the fictional incoming demo account selected its <b>Lamp</b> need. Plan <code>604fc8bd…</code> completed through Portkey using only <code>gpt-6-luna</code>. All five provider requests succeeded.</p>
 <div class="twocol">
  <figure class="figure">$plan<figcaption>Genuine cropped browser screenshot of the saved result: Floor lamp → Lamp, East Rock, one item. The crop is from the original screenshot in <code>output/screenshots/</code>.</figcaption></figure>
  <div>
   <ol class="runtrace">
    <li><b>Read the selected need.</b> <code>retrieve_selected_needs</code> returned the actual account request.</li>
    <li><b>Find candidates.</b> <code>retrieve_available_listings</code> returned database inventory instead of invented items.</li>
    <li><b>Check feasibility.</b> <code>check_match</code> tested the Floor lamp/Lamp pair against availability, dates, quantity, and transport.</li>
    <li><b>Validate the proposal.</b> <code>validate_proposed_plan</code> checked record IDs and quantity against current records.</li>
    <li><b>Return an action summary.</b> The plan said to review the details and request the item; it explicitly did not reserve it.</li>
   </ol>
   <div class="callout"><b>Grounding result.</b> One feasible match; 0 unmatched selected needs; 0 clarifications. The rationale referenced a working lamp, East Rock, and overlapping dates/times present in the two records.</div>
  </div>
 </div>
 <p class="small">The plan’s temporary demonstration listing and need were removed after the evidence was saved, so the completed plan is now marked stale. This is a historical successful run, not a current reservation or a real exchange.</p>
 <p class="small">A separate successful tool trace invoked <code>get_donation_resources</code> during a move-out plan. It did not return a donation recommendation; a tool call is not proof an organization accepts an item.</p>
 <h3 style="margin:.08in 0 .04in">Tools available to the planner</h3>
 <ul class="tool-inventory">
  <li><code>retrieve_available_listings</code> returns available listings not ruled out by deterministic checks for selected needs.</li>
  <li><code>retrieve_selected_listings</code> reads selected move-out listings, their remaining quantities, and availability status.</li>
  <li><code>retrieve_move_in_needs</code> returns open requests not ruled out by deterministic checks for selected listings.</li>
  <li><code>retrieve_selected_needs</code> reads the signed-in planner’s selected open requests.</li>
  <li><code>check_match</code> checks one listing/request pair against recorded dates, quantity, status, condition, category, and transport.</li>
  <li><code>get_donation_resources</code> returns source-linked donation resources with their acceptance-verification status.</li>
  <li><code>validate_proposed_plan</code> checks proposed IDs and quantities against current records and deterministic feasibility rules.</li>
 </ul>
 <div class="folio"><span>Section 4 · Real model run</span><span>06 / 14</span></div>
</section>

<section class="page">
 <div class="pagehead"><span>07 · Workflow evidence</span><span>Two-account browser run</span></div>
 <p class="kicker">Recommendations and handoffs are different states</p>
 <h2>Both parties must confirm after the exchange.</h2>
 <figure class="figure">$handoff<figcaption>Focused browser screenshot of an accepted fictional reservation with no agreed appointment. Its requested slot remains labeled as a proposal; the listing window and general area are separate. The completion row below summarizes an earlier, separate two-account demo run.</figcaption></figure>
 <svg class="svgbox" viewBox="0 0 900 112" role="img" aria-label="Handoff state flow from request to completion">
  <defs><marker id="arr2" markerWidth="9" markerHeight="9" refX="7" refY="4.5" orient="auto"><path d="M0 0L9 4.5L0 9Z" fill="#63856a"/></marker></defs>
  <rect x="8" y="20" width="180" height="66" rx="10" fill="#eef3e9" stroke="#9caf94"/><text x="98" y="48" text-anchor="middle" font-size="14" fill="#263b31">Recipient requests</text><text x="98" y="68" text-anchor="middle" font-size="11" fill="#53665a">quantity guarded</text>
  <rect x="248" y="20" width="180" height="66" rx="10" fill="#f5f2e8" stroke="#c3b991"/><text x="338" y="48" text-anchor="middle" font-size="14" fill="#263b31">Giver accepts</text><text x="338" y="68" text-anchor="middle" font-size="11" fill="#53665a">reservation held</text>
  <rect x="488" y="20" width="180" height="66" rx="10" fill="#eef3e9" stroke="#9caf94"/><text x="578" y="48" text-anchor="middle" font-size="14" fill="#263b31">Both confirm</text><text x="578" y="68" text-anchor="middle" font-size="11" fill="#53665a">giver + recipient</text>
  <rect x="728" y="20" width="164" height="66" rx="10" fill="#e4ede0" stroke="#85a184"/><text x="810" y="48" text-anchor="middle" font-size="14" fill="#263b31">Completed</text><text x="810" y="68" text-anchor="middle" font-size="11" fill="#53665a">quantity updated</text>
  <path d="M188 53H243M428 53H483M668 53H723" stroke="#63856a" stroke-width="2" marker-end="url(#arr2)"/>
 </svg>
 <table><thead><tr><th>Final saved state</th><th>Verified value</th></tr></thead><tbody>
  <tr><td>Reservation</td><td>completed; giver confirmation true; recipient confirmation true</td></tr>
  <tr><td>Listing quantity</td><td>0 remaining after completion</td></tr>
  <tr><td>Move-in need</td><td>fulfilled</td></tr>
  <tr><td>Request/accept flow</td><td>requested, then accepted by the giver, then confirmed by each account</td></tr>
 </tbody></table>
 <div class="warn"><b>Real-world boundary.</b> “Completed” here means the two demo accounts completed the app workflow and database state changed. No physical pickup occurred and no waste diversion was measured.</div>
 <div class="folio"><span>Section 4 · Handoff workflow</span><span>07 / 14</span></div>
</section>

<section class="page">
 <div class="pagehead"><span>08 · Tokenomics</span><span>Measured provider usage</span></div>
 <p class="kicker">One actual planner run · saved usage rows</p>
 <h2>Five Responses API calls, four database tools.</h2>
 <p>The successful tool-using plan in page 6 used <code>gpt-6-luna</code> for all requests. Per-request usage came from provider response usage and was stored in the application evidence log.</p>
 <table>
  <thead><tr><th>#</th><th>Tool or response</th><th>Input</th><th>Cached input detail</th><th>Output</th><th>Latency ms</th><th>Tool calls</th></tr></thead>
  <tbody>$request_rows
   <tr><th colspan="2">Total</th><th>5,436</th><th>2,318</th><th>600</th><th>14,031</th><th>4</th></tr>
  </tbody>
 </table>
 <div class="grid3">
  <div class="stat"><b>5</b><span>successful provider responses</span></div>
  <div class="stat"><b>4</b><span>actual function tool calls</span></div>
  <div class="stat"><b>42.6%</b><span>of aggregate input reported as cached reads</span></div>
 </div>
 <p>Tool order: retrieve the selected need → retrieve available listings → check the proposed pair → validate the plan → return final text. The last request made no tool call. Every request row identifies the same model, <code>gpt-6-luna</code>.</p>
 <div class="callout"><b>Cached-token accounting.</b> OpenAI’s prompt-caching guide places <code>cached_tokens</code> and cache-write fields inside <code>usage.input_tokens_details</code>. Its pricing example computes ordinary input as total input minus cached reads and cache writes. Therefore the 2,318 cached reads are a breakdown of the 5,436 total input tokens; they must not be added as another 2,318 tokens [7].</div>
 <p class="small">The app saved input, cached-read, output, latency, tool-call, and status fields. It did not persist cache-write token counts. The report therefore separates measured token counts from the cost assumptions on the next page.</p>
 <div class="folio"><span>Section 5 · Measured usage</span><span>08 / 14</span></div>
</section>

<section class="page">
 <div class="pagehead"><span>09 · Tokenomics</span><span>Prices and comparison</span></div>
 <p class="kicker">Authoritative public price · bounded comparison</p>
 <h2>Input filtering reduced tokens in the same four cases.</h2>
 <p>OpenAI’s public Standard short-context price table lists <code>gpt-6-luna</code> at $$0.10 per 1M input tokens, $$0.01 per 1M cached input tokens, and $$0.50 per 1M output tokens [6], checked 25 October 2026. This published rate is a reference assumption; the Portkey/course-key invoice and any account adjustments were not available.</p>
 <table><thead><tr><th>Configuration</th><th>Input tokens</th><th>Cached reads</th><th>Output</th><th>Exact decisions</th><th>Invalid / missed</th></tr></thead><tbody>
  <tr><td>Baseline: all four case records</td><td>806</td><td>0</td><td>213</td><td>4 / 4</td><td>0 invalid; 0 missed</td></tr>
  <tr><td>Efficient: case-scoped feasible candidates</td><td>581</td><td>0</td><td>199</td><td>4 / 4</td><td>0 invalid; 0 missed</td></tr>
 </tbody></table>
 <svg class="svgbox" viewBox="0 0 800 145" role="img" aria-label="Input token comparison, 806 baseline versus 581 efficient">
  <text x="0" y="39" font-size="13" fill="#263b31">Baseline input</text><rect x="150" y="18" width="520" height="34" rx="6" fill="#c5d1bd"/><text x="684" y="41" font-size="13" fill="#263b31">806</text>
  <text x="0" y="102" font-size="13" fill="#263b31">Filtered input</text><rect x="150" y="81" width="375" height="34" rx="6" fill="#63856a"/><text x="539" y="104" font-size="13" fill="#263b31">581</text>
  <text x="720" y="77" font-size="12" fill="#53665a">27.9% fewer</text>
 </svg>
 <p><b>Separate experiment, not the tool-using run:</b> two one-shot Portkey requests used the same four fictional seed-database cases: a feasible lamp match, a date mismatch, a car-required item for a car-free recipient, and an unavailable reserved item. Both returned four correct case decisions, with no invalid proposals or missed feasible matches. This small context-filtering ablation made no database tool calls and does not measure the full planner. The separate five-request run on page 6 used actual database tools.</p>
 <table><thead><tr><th>Planning-volume assumption</th><th>Reference cost range</th></tr></thead><tbody>
  <tr><td>One measured-profile run</td><td>$$0.000635–$$0.000713</td></tr>
  <tr><td>One user × 20 runs/month</td><td>$$0.012700–$$0.014259/month</td></tr>
  <tr><td>100 users × 20 runs/month</td><td>$$1.269960–$$1.425860/month</td></tr>
  <tr><td>10,000 users × 20 runs/month</td><td>$$126.996–$$142.586/month</td></tr>
 </tbody></table>
 <p class="tiny">Range reflects an unlogged cache-write split: lower end treats the remaining 3,118 input tokens as ordinary input; upper end treats all as default 30-minute cache writes at $$0.125/1M. Both price 2,318 cached reads once and 600 output tokens. Portkey account billing may differ. Each scale assumes every run repeats the measured token profile. The experiment cost references are $$0.0001871 baseline and $$0.0001576 filtered, using public rates and no reported cached reads.</p>
 <div class="folio"><span>Section 5 · Cost and comparison</span><span>09 / 14</span></div>
</section>

<section class="page">
 <div class="pagehead"><span>10 · Safety</span><span>Tested defenses</span></div>
 <p class="kicker">A deterministic defense you can inspect</p>
 <h2>Feasibility checks run in application code.</h2>
 <div class="twocol">
  <div>
   <p>Before a reservation is accepted, CampusLoop checks that dates overlap, quantity remains, the listing is available, and the transport requirement can be met. A plan validator also rejects invalid IDs, quantities, and incompatible proposals.</p>
   <table><thead><tr><th>Attempt</th><th>Tested response</th></tr></thead><tbody>
    <tr><td>Move-in dates later than listing deadline</td><td>Incompatible; UI says dates do not overlap and no reservation can be requested.</td></tr>
    <tr><td>Car-free pickup for vehicle-required furniture</td><td>Incompatible without a confirmed delivery/transport arrangement.</td></tr>
    <tr><td>Reservation after quantity is gone</td><td>API returns HTTP 409; no duplicate allocation.</td></tr>
    <tr><td>Fake record IDs or infeasible model proposals</td><td>Final plan validator rejects them.</td></tr>
    <tr><td>Malicious listing text, oversized planner input</td><td>Text is labeled untrusted and contact strings are stripped; oversized input is rejected before model call.</td></tr>
   </tbody></table>
  </div>
  <figure class="figure">$date<figcaption>Genuine historical browser warning. It shows an internal Browser QA fixture name because it predates final fixture cleanup; those test records were later removed from the normal demo dataset.</figcaption></figure>
 </div>
 <div class="grid3" style="margin:.11in 0">
  <div class="stat"><b>10 / 10</b><span>standalone safety checks passed</span></div>
  <div class="stat"><b>12 / 12</b><span>pytest suite passed; two deprecation warnings</span></div>
  <div class="stat"><b>1 + 1</b><span>both accounts must confirm before completed</span></div>
 </div>
 <div class="warn"><b>Important test limit.</b> The malicious-listing test checks untrusted-data marking and contact redaction. No live adversarial model run proved prompt-injection resistance. The UI and deterministic layers were tested; production security and adversarial robustness were not established.</div>
 <p class="small">Saved safety results are in <code>output/safety_tests.json</code>; later Chrome workflow and edge results are in <code>output/workflow_results.json</code> and <code>output/edge_checks.json</code>. The safety suite covers atomic quantity allocation and a demo reset that preserves user-created records.</p>
 <div class="folio"><span>Section 6 · Safety</span><span>10 / 14</span></div>
</section>

<section class="page">
 <div class="pagehead"><span>11 · Impact and metrics</span><span>Donation alternatives</span></div>
 <p class="kicker">Source-backed guidance with uncertainty kept visible</p>
 <h2>The resource directory points outward; it does not promise acceptance.</h2>
 <div class="twocol">
  <figure class="figure">$donation<figcaption>The app’s Donation Guide preserves an “acceptance details need verification” label for each resource while the app’s directory records remain conservative.</figcaption></figure>
  <div>
   <p>The Habitat ReStore’s official acceptable-donations page says items must be in good, sellable condition and may be refused if unsafe, broken, unclean, or unusable. It lists lamps only when complete, working, and in excellent condition; it explicitly says ceiling fans are no longer accepted [5].</p>
   <p>The list names wood and office furniture, chairs, tables, bookshelves, and bed frames, while excluding mattresses, box springs, toddler beds, cribs, and entertainment units. It lists small appliances under ten years old and in perfect working order.</p>
   <p>For towels, the page excludes “linens (bed or table)” but does not name bath towels. <b>Bath-towel acceptance is unknown</b>; the app should not infer it from the broader exclusion.</p>
  </div>
 </div>
 <div class="callout"><b>Drop-off and pickup.</b> The ReStore’s overview says small tools, dishware, and decorative items may be delivered during regular hours; the more detailed acceptable-donations page says drop-offs are by appointment during business hours. Because the official pages differ, contact the ReStore and arrange an appointment before traveling. Its page says pickups cover most New Haven County towns and also Clinton and Killingworth; exact town/service availability still needs confirmation [4,5].</div>
 <table><thead><tr><th>Resource</th><th>What this research verified</th><th>Still unknown</th></tr></thead><tbody>
  <tr><td>Habitat ReStore</td><td>Published item categories, condition rules, exclusions, location, and donation instructions.</td><td>Acceptance of bath towels; current availability of a truck slot; item-by-item decisions.</td></tr>
  <tr><td>Yale Graduate Housing Swap Room</td><td>533 Prospect Street, basement level; commonly exchanged clothing/shoes, household/kitchen goods, small appliances, books/school/office supplies, and toys/children’s items; contact swaproom.whitehall@gmail.com [3].</td><td>Hours vary and Yale Connect provides current schedules and announcements. Eligibility for graduate students in private housing is not explicit and requires confirmation. Published categories do not guarantee acceptance of every item.</td></tr>
  <tr><td>City of New Haven recycling</td><td>Official page URL was identified.</td><td>Page returned HTTP 403 on 25 October 2026; item rules and schedules remain unknown.</td></tr>
 </tbody></table>
 <p class="tiny">CampusLoop does not contact organizations, claim live stock, or publish unsupported donation policy. The tool can retrieve stored source links, but the stored app acceptance fields remain unverified.</p>
 <div class="folio"><span>Section 7 · Resource evidence</span><span>11 / 14</span></div>
</section>

<section class="page">
 <div class="pagehead"><span>12 · Impact and metrics</span><span>What the evidence supports</span></div>
 <p class="kicker">Prototype indicators, not population impact</p>
 <h2>What has been measured is workflow behavior.</h2>
 <div class="grid2" style="margin:.18in 0">
  <div class="stat"><b>1</b><span>successful grounded AI match in the saved plan run</span></div>
  <div class="stat"><b>1</b><span>fictional two-account handoff workflow completed in the browser</span></div>
  <div class="stat"><b>4 / 4</b><span>case decisions correct in each side of the small comparison</span></div>
  <div class="stat"><b>27.9%</b><span>fewer input tokens with case-scoped filtering in that comparison</span></div>
 </div>
 <h3>What “completed” means here</h3>
 <p>One local demo listing and one local demo need moved through request, giver acceptance, and confirmation by both demo accounts. SQLite then showed the reservation completed, listing quantity at zero, and need fulfilled. The fixture is fictional and was removed after screenshots and database verification were saved.</p>
 <h3>What is not measured</h3>
 <p>No real-student reuse handoffs, pounds of material kept from disposal, carbon emissions, replacement spending, task time, donation acceptance success, app adoption, or student satisfaction have been measured. No independent student usability observations or participant interviews have been collected.</p>
  <p class="callout"><b>Independent student testing was not conducted.</b> No participant task time, outcome, or feedback is available.</p>
 <div class="callout" style="padding:.09in .12in;margin:.09in 0"><p class="kicker" style="margin:0 0 .04in">Creator walkthrough — 26 October 2026</p><p class="small"><b>Observed by me:</b> I could submit an item request and observe an accepted reservation; I was unsure where to find a specific pickup time; the completion-confirmation wording was confusing; and a success notification overlapped the navigation.</p><p class="small"><b>Fixes subsequently verified in focused local browser checks:</b> accepted reservations distinguish a proposed time from an agreed appointment and show the available window and general area; completion buttons use role-specific physical-exchange wording; and success notices now sit below the header without covering navigation or content. These checks used fictional demo records; no physical pickup or independent participant was involved.</p></div>
 <p class="small">The project’s potential impact remains a testable hypothesis: a single well-coordinated handoff could help both sides of move day. This prototype has not measured whether it changes what students discard, buy, or donate.</p>
 <div class="folio"><span>Section 7 · Metrics</span><span>12 / 14</span></div>
</section>

<section class="page">
 <div class="pagehead"><span>13 · Limits and next steps</span><span>Submission status</span></div>
 <p class="kicker">Local prototype, not an operating service</p>
 <h2>Several questions need people and live sources.</h2>
 <ul>
  <li><b>No public deployment.</b> The app runs locally at <code>http://127.0.0.1:5173</code> and is not a Yale service. Demo accounts are fictional and are not verified students.</li>
  <li><b>No live inventory.</b> Listings, availability, pickup windows, and transport depend on user-provided records. The system does not calculate real routes or guarantee item condition.</li>
  <li><b>Limited appointment coordination.</b> A recipient may propose a pickup date/time; the giver can explicitly agree while accepting. Otherwise, the reserved card shows that no appointment is agreed and displays the listing’s availability window and general area. The app has no chat or post-acceptance rescheduling flow, so the people must coordinate any later change outside CampusLoop.</li>
  <li><b>Donation research is partial.</b> Yale Swap Room hours vary and current schedules are on Yale Connect; eligibility for graduate students in private housing needs confirmation, and listed categories do not guarantee each item is accepted. ReStore bath-towel acceptance needs direct confirmation; the City page was inaccessible.</li>
  <li><b>AI evidence is narrow.</b> One grounded successful plan and a four-case single-request comparison are not enough to estimate broad match quality. Model prompt-injection resistance was not tested live.</li>
  <li><b>Token-cost evidence has a billing gap.</b> Provider input, cached read, and output counts are logged; cache-write counts are not. Public OpenAI rates yield a reference range, not a Portkey account statement.</li>
  <li><b>No independent student testing.</b> No participant task time, outcome, or feedback is available.</li>
 </ul>
 <h3>Next submission work</h3>
 <ol>
   <li>If an independent student test is conducted later, record the task, completion time, outcome, and feedback with consent and no unnecessary personal data.</li>
  <li>Confirm private-housing student eligibility with the Swap Room and check Yale Connect for current hours and announcements; confirm each item before travel. Also confirm ReStore towel acceptance and obtain City item-specific recycling guidance.</li>
   <li>Upload only report.html and slides.html to Canvas. A demonstration video is optional; no separate URL, ZIP, PDF, or other files are required.</li>
  <li>Check course-key billing against the measured token log if exact account charges are required.</li>
  <li>The self-contained presentation is available in slides.html.</li>
 </ol>
 <p class="small">Design and feature scope are frozen. The items above are research, evidence, and course-submission follow-ups, not requests to expand this prototype now.</p>
 <div class="folio"><span>Section 8 · Limits and next steps</span><span>13 / 14</span></div>
</section>

<section class="page">
 <div class="pagehead"><span>14 · Sources and methods</span><span>Updated 26 October 2026</span></div>
 <p class="kicker">Official sources and preserved evidence</p>
 <h2>Reference list</h2>
 <ol class="sources">
  <li><a href="https://buynothingproject.org/">The Buy Nothing Project, official homepage</a>. Describes free giving/getting and joining local app or Facebook groups. Accessed 2026-10-25.</li>
  <li><a href="https://housing.yale.edu/graduate-housing/residence-life/sustainable-living">Yale Housing, Graduate Housing Residence Life: Sustainable Living</a>. Community Garden, Spring Salvage, sustainability events, and volunteer opportunities [2].</li>
  <li><a href="https://housing.yale.edu/graduate-housing/residence-life/sustainable-living/swap-room">Yale Housing, Graduate Housing Swap Room</a>. Location, commonly exchanged item categories, variable hours and Yale Connect updates, and contact address. Eligibility for graduate students in private housing is not explicit; individual item acceptance is not guaranteed [3]. The page could not be fetched from this environment during this edit; the listed details were supplied from the linked official page for this revision.</li>
  <li><a href="https://habitatgnh.org/restore/">Habitat for Humanity of Greater New Haven, New Haven County ReStore</a>. Overview, location, and donation instructions. Accessed 2026-10-25.</li>
  <li><a href="https://habitatgnh.org/restore/acceptable-donations-for-our-restore/">Habitat ReStore, Acceptable Donations for Our ReStore</a>. Item categories, condition requirements, exclusions, and appointment instructions. Accessed 2026-10-25.</li>
  <li><a href="https://developers.openai.com/api/docs/pricing">OpenAI API pricing</a>. Standard per-million-token price table, including GPT-6 Luna short-context input/output/cached rates and cache-write rates. Accessed 2026-10-25.</li>
  <li><a href="https://developers.openai.com/api/docs/guides/prompt-caching">OpenAI API prompt caching</a>. Usage accounting example distinguishes ordinary input, cached reads, and cache writes. Accessed 2026-10-25.</li>
  <li><a href="https://www.newhavenct.gov/government/departments-divisions/public-works/recycling">City of New Haven recycling page</a>. Official URL identified, but returned HTTP 403 during this review; no item rule is inferred.</li>
  <li>The original course assignment specification supplied for the project. It permits a personal-key model choice or the course-key option requiring <code>gpt-6-luna</code> through Portkey; the creator chose the course-key option. Yale program descriptions above are based on official Yale Housing pages [2] and [3].</li>
 </ol>
 <h3>Evidence files used</h3>
 <p class="small"><code>output/refinement_verification.json</code>, <code>output/usage.jsonl</code>, <code>output/workflow_results.json</code>, <code>output/edge_checks.json</code>, <code>output/safety_tests.json</code>, <code>output/pytest_results.txt</code>, <code>output/frontend_build.txt</code>, <code>output/baseline_efficient_comparison.json</code>, <code>output/cost_calculations.json</code>, <code>output/official_source_checks.json</code>, <code>output/focused_followup_browser_check.json</code>, and original and focused PNGs in <code>output/screenshots/</code>.</p>
 <div class="warn"><b>Submission status:</b> Independent student testing was not conducted. The public repository URL is shown on the cover. Upload only report.html and slides.html to Canvas; a demonstration video is optional.</div>
 <p class="tiny">This HTML embeds its screenshots and SVG diagrams directly and can be opened offline. Source links require a connection. All descriptions of demo handoffs refer to local fictional test data, not real-world reuse.</p>
 <div class="folio"><span>End · CampusLoop report</span><span>14 / 14</span></div>
</section>
</body>
</html>
''')

values = {
    "home": home,
    "find": find,
    "plan": plan,
    "handoff": handoff,
    "date": date_failure,
    "donation": donation,
    "request_rows": request_table,
}
result = html.substitute(values)
OUT.write_text(result, encoding="utf-8")
print(f"Wrote {OUT} ({len(result.encode('utf-8')):,} bytes; 14 explicit print pages).")
