# CLAUDE.md — Street-Level Flood Intelligence Hackathon

> **Project status:** Concept / hackathon prototype. This file defines product intent, scope, priorities, and how Claude should work. It is **not** evidence that any capability, dataset, accuracy level, or integration already works.
>
> **Working title:** *Every Photo Is a River Gauge* (may be renamed to reflect street cameras as the primary input).
>
> **Primary audience:** Emergency coordinators, municipal transportation/public-works staff, and community planners. Residents are an eventual beneficiary, but this prototype must not present itself as a public navigation or official emergency-warning service.

## 1. Project at a glance

**One-sentence pitch:** Turn existing street-camera footage and community photos into reviewable flood-depth readings, project each camera's readings a short time ahead, give dispatchers least-deep route options within a depth limit their agency sets, and show where recurring flooding suggests future infrastructure attention.

**Personal motivation:** Our team has experienced being stranded because a nearby bridge repeatedly floods. We know how frustrating it is to see an impassable crossing without knowing what is happening elsewhere or which communities are being cut off. Use this authentic experience as the opening of the pitch; do not invent a bridge name, date, rescue event, injury, or other details.

**Core problem:** River gauges, weather alerts, and road-closure reports provide essential information but may not describe water conditions at a particular street or bridge. Cameras and community media sometimes show those conditions, yet their observations are fragmented, difficult to validate, and hard to connect to road-network consequences. Repeated local incidents can also be difficult to see as a long-term infrastructure pattern.

**Our intended change:**
- **During a flood:** Convert footage into time-stamped, source-linked observations, help an authorized reviewer spot possible road-access disruptions, and propose least-deep route options for a dispatcher to choose from (rules: `docs/routing-and-prediction.md`).
- **After a flood:** Replay documented events, identify places that repeatedly appear affected, and suggest locations for further civil-engineering investigation.
- **For everyone interpreting results:** Present observations and uncertainty in a clear, accessible 2D/3D interface.

This is **decision support**, not a flood forecasting service (only short per-camera projections, at most 60 minutes ahead), a certified road-safety system, or a replacement for public authorities.

## 2. Hackathon objective and judging lens

**Event prompt:** “Apply AI and machine learning to real world problems in ways that create meaningful, cross-disciplinary impact.”

**Rubric provided by organizers:** Technicality, Ingenuity, Diversity, Applicability, Looks (ability to pitch the project). Unless the official event publishes weights or definitions, treat the five as equally important working lenses, not a confirmed scoring formula.

| Criterion | What the demo should prove |
| --- | --- |
| **Technicality** | AI actually interprets visual observations, maintains source evidence, and connects observations to a meaningful analysis/action. |
| **Ingenuity** | Existing cameras become useful flood observers; the product connects observation, road impact, and historical infrastructure insight. |
| **Diversity** | Meaningful integration of AI, hydrology, transportation engineering, geospatial analysis, emergency management, public infrastructure planning, and design. |
| **Applicability** | Specific users can identify what changed, where attention is needed, and what needs human verification. |
| **Looks / pitch** | One clear camera-to-map-to-impact story, visually legible uncertainty, and a compelling before/after experience. |

### Sponsor tracks

- **NVIDIA — best use of Nemotron:** The agent must do **real work**, not just chat. It should inspect or interpret an observation, identify relevant evidence and limitations, relate it to a location/road segment, and produce a proposed incident summary or review task. Show the **input → model reasoning/assessment → structured output → human decision** chain. Verify the exact model, hosting, and prize restrictions from official event rules before committing.
- **Adobe — best design:** Design must improve understanding and decisions, not merely look polished. Prioritize intuitive navigation, visual evidence, readable water-depth references, time exploration, confidence/unknown states, accessibility, and clear separation of historical vs live content. Do not assume a particular Adobe product is required without checking the official track rules.

**Do not chase sponsor prizes by adding unnecessary features.** A cohesive, trustworthy demonstration beats a list of loosely connected integrations.

## 3. Who uses it and what decisions it supports

**A. Emergency or transportation coordinator**
- Sees potentially flooded camera locations and which reports need verification.
- Opens the original visual evidence and sees what the AI observed or could not determine.
- Reviews potential effects on roads, bridges, and access to important facilities.
- Accepts/rejects an incident for the *prototype's review queue*; this must not operate actual road closures.
- Compares 2–3 least-deep route options computed within the depth limit the agency set for a vehicle type, and picks one. The prototype never dispatches vehicles.

**B. Municipal planner / civil engineer**
- Replays a past flood, compares multiple documented events, and finds repeatedly affected road segments.
- Checks whether apparent hotspots are supported by adequate historical coverage.
- Reviews candidate interventions (e.g., drainage assessment, culvert inspection, bridge approach study) as **questions for engineering evaluation**, not approved designs.

**C. Resident / community member (secondary)**
- Understands where flooding has been reported and what remains unknown.
- Can contribute photos only through an appropriate, permissioned workflow.
- Is never told that a proposed alternate route or unobserved road is safe.

## 4. Product scope

### P0 — Required end-to-end experience (build these first)

1. **Camera/photo input:** Accept at least one authorized prerecorded street-camera clip or image sequence, and optionally manually uploaded community photos. A prerecorded clip is replayed *through the real analysis pipeline*, not simply animated as fake AI output.
2. **Observed-water analysis:** Detect whether visible standing/rising floodwater is plausible, associate the observation with its time and known camera location, and show evidence. Estimate a numeric depth **only when a usable calibration or reference object exists**. Otherwise say “water detected; depth unknown.”
3. **Map observation:** Place the observation on a 2D map at a known location with a timestamp, source preview, verification status, and uncertainty/limitations. Never invent coordinates.
4. **Human verification:** Provide an obvious accept/reject or needs-review action. Clearly distinguish AI-proposed observations from verified reports and official notices.
5. **Road consequence and route options:** Flag nearby road segment(s) as **potentially affected**, and compute least-deep route options within a person-set depth limit on the replay data, following the rules in `docs/routing-and-prediction.md`.
6. **Explainable agent output:** Nemotron produces a short, evidence-backed incident summary and a concrete reviewer task; the summary references actual observations instead of inventing facts.

### P1 — Differentiating features (after P0 is stable)

7. **Historical backtracking:** A time slider or event selector replays recorded observations from one past flood. Separate event time from upload/processing time. Show how the evidence changed, not a fabricated continuous flood field.
8. **Recurring hotspot map:** Aggregate documented flooding across *different events* to identify repeated reports at particular streets/bridges. Display event count, dates, data coverage, and evidence links. Label this “repeated observed reports,” not a proven annual flood frequency.
9. **3D neighborhood / street view:** Show buildings, the road network, camera positions, and understandable water-height references. If using illustrative water surfaces, explicitly label them **conceptual visualization**, not a validated hydraulic simulation.
10. **Critical-facility context:** Highlight potentially affected access to hospitals, fire stations, schools, bridges, or shelters when reliable map data is available. Describe impact as conditional on a reported or confirmed restriction.
11. **Infrastructure review cards:** For a repeated hotspot, generate a factual summary of observed incidents, a map of potential access consequences, and possible categories of investigation (e.g., drainage capacity review, culvert maintenance review, low-water-crossing signage review, roadway elevation assessment). The agent **does not prescribe construction** or claim an intervention is effective without engineering evidence.
12. **Live camera readings and short-term prediction:** TranStar camera frames read by Nemotron against each camera's dry baseline, with a per-camera Gaussian process that projects depth at most 60 minutes ahead (`docs/routing-and-prediction.md`).
13. **Least-deep routing on predicted depth:** route options that use each segment's depth at the vehicle's arrival time (observed, estimated or predicted, always labeled).

### P2 — Stretch features (only if time and evidence permit)

- Compare several plausible road restrictions using a **what-if** route/network tool; never certify a route as safe.
- Optional live webcam/miniature flooded-street demonstration, with model-scale measurements labeled as such.
- Camera-to-camera consistency checks or duplicate/repost detection when reliable evidence is available.
- Historic comparison of before/after infrastructure work, if independent event records actually support it.
- Concise incident briefing showing the top changes and where human attention is needed.

### Explicitly out of scope for the hackathon

- Hydrodynamic forecasting, citywide water-depth prediction, high-resolution flood simulation, or claiming a 3D visualization reflects true water surface elevation. (Short per-camera projections up to 60 minutes ahead are in scope; see `docs/routing-and-prediction.md`.)
- Automatic public alerts, actual dispatcher control (dispatching vehicles, CAD integration), road-closure requests to governments, or public/driver navigation. Least-deep route *options* that a dispatcher chooses from are in scope, under the routing rules.
- Telling any driver that a road is safe based on absent/low water detections, camera visibility, or estimated depth.
- Full metropolitan camera integration, mass-scale continuous processing, or unsupported claims of real-time citywide coverage.
- Production-grade infrastructure design, cost estimates, investment optimization, or regulatory certification.

## 5. Conceptual workflow

```text
Authorized camera replay / live image / community photo
  → source and timestamp validation
  → water observation (or insufficient evidence)
  → reference-based depth range, if defensible
  → structured result with uncertainty and source evidence
  → location-linked map marker
  → possible road/network impact (explicitly conditional)
  → Nemotron incident summary and verification request
  → human confirms, rejects, or requests more information

Historical records from multiple events
  → filter by time, location, and evidence quality
  → recurring observed hotspots (with coverage caveats)
  → infrastructure review suggestions for municipal experts
```

### Evidence and system status vocabulary

Keep these distinctions visible in every layer:

- **Official closure / warning:** Sourced from an identified authority, with issue time and expiration/status if provided.
- **Human-confirmed observation:** Reviewed visual evidence for a specific time/place; still not an official road closure or a certified measurement.
- **AI-proposed observation:** Awaiting human review.
- **Estimated water depth:** A range tied to a known reference/calibration, with uncertainty; not an exact roadway-wide depth.
- **Possible network impact:** A conditional model result (“if this segment is inaccessible…”), not an observation.
- **Unknown / unobserved:** Absence of evidence; never equate it with dry or passable.
- **Predicted water depth:** A projection of one camera's recent readings to a stated time, at most 60 minutes ahead, with a range that widens the further ahead it looks. A model output, never an observation.
- **Route option:** A conditional plan computed from observed, estimated and predicted depths within a depth limit set by a person at the agency. It reports its deepest point and its unobserved distance, and is never a safety certification.
- **Historical / replay / simulated:** Clearly distinguish all three from current, observed conditions.

When the VLM and any secondary model disagree, preserve the disagreement instead of averaging it into unjustified precision.

### Routing rules (full version and math: `docs/routing-and-prediction.md`)

1. Never say safe, clear, passable or all clear; report numbers with their source.
2. A person at the agency sets each vehicle type's depth limit; the agent never sets or changes it.
3. Plan on the upper end of every depth range.
4. Every depth is labeled Observed, Estimated, Predicted (with its time) or Unknown.
5. Unobserved roads are never treated as dry; every option shows its unobserved distance.
6. Predict at most 60 minutes ahead, and only with enough recent readings.
7. The agent proposes 2–3 options; the dispatcher picks; the agent re-plans and alerts but never switches routes itself.

## 6. Historical backtracking and infrastructure impact

This is an intentional second chapter of the project, not a separate app.

### Historical questions to answer

- Which bridges, low crossings, or intersections appear in **multiple distinct flood events**?
- How long did observations remain concerning within each documented event, when timestamps allow?
- Which repeatedly affected road segments have outsized *potential* effects on access to schools, hospitals, or neighboring communities?
- Which locations should public works evaluate first, **given what the available evidence can and cannot establish**?

### Important analytical constraints

- A camera with many images during one incident is **one event with many observations**, not many independent floods.
- More cameras or residents in one area can create an apparent hotspot because of **reporting bias**. Show observation coverage alongside hotspot rankings.
- Historical camera footage may be unavailable. Never synthesize an actual historical record from a current image or from a model-generated scene.
- River-gauge history, rainfall records, official road closures, community archives, and authorized camera evidence are different source types; do not treat them as equivalent proof of road depth.
- Repeated observed flooding is a **screening signal for further study**; engineering experts must assess drainage capacity, road elevations, water flow, safety, property constraints, and costs before selecting any intervention.

### Example infrastructure insight (hypothetical)

> “Bridge approach A appears in three documented flood events. If its adjoining road were closed, the model shows reduced access to Facility B. Recommend a drainage and bridge-approach assessment; evidence is incomplete for events without camera coverage.”

Never frame a hypothesis like this as a verified local fact until real records support it.

## 7. How the disciplines fit together

| Discipline | Genuine role |
| --- | --- |
| **Computer vision / multimodal AI** | Interpret images or video and identify the visible basis for a flood observation. |
| **Hydrology / flood science** | Explain why a point observation is not a citywide depth estimate; define reasonable water-level and uncertainty interpretation. |
| **Transportation / network analysis** | Model the *conditional* impact of losing a road segment on connectivity and facility access. |
| **GIS / geospatial data** | Tie known cameras, observations, road segments, facilities, and history to place and time. |
| **Emergency management** | Shape useful verification queues, escalation context, and trustworthy information displays. |
| **Civil engineering / public works** | Turn repeated observed trouble spots into candidates for professional investigation. |
| **Human-centered design** | Make evidence, uncertainty, changing conditions, and long-term patterns understandable under pressure. |

In the pitch, emphasize **the interaction** among disciplines rather than merely listing them: vision detects an issue; GIS locates it; transportation analysis reveals conditional access impacts; history surfaces repeat patterns; civil engineering identifies what must be investigated; design helps humans interpret the result.

## 8. Demo strategy

**Current plan (Nov 21):** the Harvey 2017 Meyerland replay is the **proof of concept** and is built (`python -m flood.run`, `web/index.html`, `web/3d.html`). Live TranStar cameras, short-term prediction and least-deep routing are the **product**; demo the router on the replay data and present anything not working as planned. Tasks: `docs/tasks/2026-11-21-polish.md`.

**Preferred format:** A deterministic replay of a real, authorized street-camera sequence processed by the working pipeline, with a visually polished 2D map and a targeted 3D close-up. A live webcam demo is a bonus, not a dependency.

### Suggested 90-second narrative

1. **0–12s — Personal connection:** “A bridge near us floods repeatedly, and we've been stranded by it. We realized a map of river levels doesn't always show the condition of the road people actually need.”
2. **12–27s — Show the evidence:** A camera view changes from normal to visibly flooded; the AI identifies an observation (or explains why depth is unknown).
3. **27–42s — Put it on the map:** The observation appears with source, time, and uncertainty; a road is flagged for review.
4. **42–57s — Explain consequences:** A conditional road restriction changes a simple connectivity view; the 3D scene makes the location understandable.
5. **57–72s — Nemotron does real work:** It prepares an evidence-backed incident and a reviewer confirms/rejects the proposed action.
6. **72–85s — Backtrack:** Switch to history, show a documented recurring location, and produce a cautious infrastructure-review card.
7. **85–90s — Closing:** “From detecting a flooded road today to understanding why the same road keeps flooding.”

If history is not verified or functioning, omit that step from the live demo rather than fabricate it. A stable, truthful 60-second P0 demonstration is better than a broken 90-second one.

### Show, do not claim

- Use a visible source image/frame, timestamp, and known camera location.
- Show at least one **uncertain/rejected** case to demonstrate judgment rather than a perfect stream of green checks.
- If using precomputed fixtures or simulated events, label them clearly.
- Do not display fabricated accuracy comparisons, improvement percentages, flood-death reductions, or “safe route” assertions.
- Prefer one clean before/after sequence over many tiny dashboards or animations.

## 9. Interaction and visual design principles

- **Two main modes:** `During an event` and `Historical analysis` (not a dozen tabs).
- **Primary canvas:** Map; camera evidence and AI reasoning open in a compact side panel.
- **Camera-to-pin interaction:** The user can always click from a map marker to the specific frame/report that caused it.
- **Unknown is visually prominent:** Gray/hatched/outlined areas must not silently look safe.
- **Confidence isn't just color:** Pair labels and ranges with icons or patterns; ensure color-blind accessibility and sufficient contrast.
- **Depth is relatable:** Only show familiar object silhouettes (curb, tire, door) when the underlying reference is appropriate. Avoid universal vehicle-safety thresholds.
- **Time is explicit:** Replay/live status and source timestamps stay visible; stale observations fade or are flagged, not silently carried forward.
- **3D provides context:** Buildings, bridge approaches, camera viewpoints, and conditional access impacts. Avoid cinematic effects that suggest unsupported physics.
- **Design for a judge in 15 seconds:** They should understand what changed, where, why it matters, and what remains uncertain without reading a paragraph.

## 10. Data and model boundaries

- Prioritize **lawfully usable**, attributed historical images or clips with a known location/time. Confirm rights and provider conditions before downloading, redistributing, or displaying them.
- Some traffic camera portals provide still snapshots but do **not** provide archived footage. Never assume access to historical feeds or unrestricted live streaming.
- A camera can detect visible flooding without supporting accurate centimeter-level depth. Fixed-camera geometry and calibrated reference objects improve interpretability; unknown perspective/reference means **no numeric depth claim**.
- Do not invent labels, ground truth, confidence scores, or test results. Separate model-generated confidence labels from empirically calibrated accuracy.
- Avoid publishing faces, license plates, precise home details, or sensitive personal media; redact/blur as appropriate and minimize retention.
- Verify actual Nemotron model availability, vision/video/reasoning behavior, access terms, and track eligibility from current official docs. Do not assume a single model can do every stage in one API call.
- **Verified Nov 21 (Lane B):** `nvidia/nemotron-3.5-super-vl-120b-a12b` on NVIDIA Build reads images sent as OpenAI-style `image_url` parts (4 images in one request worked). It reasons before answering, so it needs a large `max_tokens` (8192) and takes 17–67 s per photo, and the same photo can give different readings on different runs. A pretrained PyTorch detector and a scikit-learn per-camera Gaussian process support it; neither is trained on our data.

### Official reference starting points (verify when used)

- NWS safety guidance: https://www.weather.gov/safety/flood-turn-around-dont-drown
- NVIDIA Nemotron VL documentation: https://docs.nvidia.com/nim/vision-language-models/1.6.0/examples/nemotron-nano-12b-v2-vl/api.html
- Houston TranStar camera page: https://traffic.houstontranstar.org/cctv/transtar/

These are **starting references**, not proof that footage/API access or data licenses are available for the event.

## 11. Claude's operating instructions

### Working style

1. **Start from the user's immediate request.** Do not automatically expand into the entire product or start coding when asked to brainstorm, plan, write, or review.
2. **Inspect existing repository files first.** Reuse what's already implemented and avoid recreating docs, integrations, or components.
3. **Prioritize P0.** Only propose P1/P2 additions after identifying their impact on a working end-to-end demonstration.
4. **Use a single coherent user story.** Treat live flood understanding and historical infrastructure insight as one connected product, not separate competing apps.
5. **Keep scope honest.** Differentiate `planned`, `implemented`, `tested`, and `validated`; never describe planned features as finished.
6. **Lead with evidence.** If a claim, historical event, source, location, or metric is unverified, label it and state the simplest way to validate it.
7. **Avoid premature stack lock-in.** Recommend tools only in response to a relevant task, with a concrete reason and any access/dependency caveat.
8. **Prioritize privacy and safety.** For flood/routing output, use decision-support language and human-in-the-loop confirmation.
9. **Keep communication efficient.** Give the next logical action and concise trade-offs rather than a giant roadmap on every turn.
10. **Never fabricate a successful test, model benchmark, permission, external integration, user interview, or historical flood record.**

### Token and multi-agent efficiency

- Default to one agent handling the active task; use subagents only for **truly independent, bounded** research or work.
- No agent-to-agent debates, repeated self-critique loops, or duplicate web searches. Summarize findings once and store durable notes in repository files if useful.
- Read only files relevant to the active task; avoid repeatedly loading large source dumps.
- When delegating, specify a tight question, a short output format, and exactly where to save results. The coordinator, not every agent, integrates findings.
- Prefer one structured comparison over long prose when selecting features.
- Do not produce code, designs, or implementation plans without an explicit user request.

### If asked to implement

- First identify the **smallest vertical slice** from input → actual analysis → map → human review.
- State dependencies and biggest blockers, especially dataset/camera permissions, video processing, location accuracy, and model access.
- Use authentic recorded data or clearly labeled fixtures; ensure a replay still triggers real processing, not hidden hardcoded outcomes.
- Keep the prototype deterministic enough to demonstrate under time pressure. Have a backup replay if internet/model service is unavailable.
- Test observable behavior and error paths, not only happy-path visuals.
- Report what changed, what was verified, and what remains unproven in plain language.

### Definition of a successful hackathon prototype

A judge can watch an authorized camera clip being processed, inspect a source-linked flood observation, see the *conditional* impact on a road or nearby community, and understand the human-review action Nemotron prepared. If historical evidence is available, they can also see why a location is repeatedly flagged and what kind of engineering study it may merit. Every output is visibly differentiated as official, observed, estimated, hypothetical, or unknown.

## 12. Decisions still open

- Adobe track requirements. (Model: the event kit allows any Nemotron model; we use Super VL on NVIDIA Build, verified working.)
- Team size, available hardware, internet reliability, and event duration.
- Confirmed usable footage with trustworthy location/timestamp metadata and permission.
- ~~Geographic focus for first event replay~~ **Decided:** Meyerland (Brays Bayou), Houston, Hurricane Harvey 2017 replay from 10 USGS high-water marks.
- **Decided (Nov 21):** demo = replay proof of concept; product = TranStar cameras + short-term prediction + least-deep routing.
- Whether historical data supports repeated flooding at the proposed bridge/location.
- Exact baseline for evaluating detection and any defensible depth-error metrics.
- Which P1 feature (history, 3D, or road analysis depth) gets precedence after P0 is working.

**North star:** *Make one street-level flood observation understandable, trustworthy, and useful — then show how repeated observations can guide smarter long-term infrastructure attention.*
