# Every Photo Is a River Gauge

Nov 21, 2026 · @Sujit Kushalnagar

## The pitch and the problem

An agent turns residents' flood photos into verified, street-level water-depth readings on a live map, so dispatchers and drivers can tell which streets are passable.

**Why depth matters.** Most flood deaths happen in cars. The National Weather Service cites CDC data that over half of flood-related drownings occur when a vehicle is driven into hazardous flood water ([NWS](https://www.weather.gov/safety/flood-turn-around-dont-drown)). Six inches of water reaches the bottom of most passenger cars, and a foot floats many vehicles ([weather.com](https://weather.com/safety/floods/news/flash-flooding-vehicle-danger-20140717)). From the driver's seat, those depths look alike.

**The gap.** Official gauges sit on rivers and bayous, often miles apart, so nobody knows the depth on a given street. Meanwhile, residents post photos where the water line is visible against tires, signs and doors. Nobody has time to read them.

**Why here.** Texas had more flood deaths than any other state from 1959 to 2019: 1,069 ([FOX Weather](https://www.foxweather.com/learn/peak-flash-flood-season-us-june-july)).

**What it is not.** It doesn't forecast or prevent floods (it only projects each camera's own readings up to 60 minutes ahead), and it never replaces official warnings. Its value is the first few hours of a flood, when everyone is guessing.

## Update: street cameras for emergency dispatch

The input is now Houston's traffic cameras instead of resident photos, and the user is an emergency dispatcher who needs the least-deep route for a vehicle, for example crossing 6 inches of water instead of 1 foot. Sections below still say "photo" in places; read it as "camera frame."

| Part | Before (photos) | Now (cameras) |
| --- | --- | --- |
| Input | Resident uploads | Snapshots from Houston TranStar's roughly 1,000 freeway cameras ([KPRC](https://click2houston.com/traffic/2021/02/11/ask-2-can-you-get-highway-video-for-insurance-purposes)) |
| Location | Read from photo metadata | Fixed and known for each camera |
| Vetting | Fakes and reposts | Frame quality: night, glare, rain on the lens, frozen feed, camera turned away |
| Depth reading | Reference objects in an unknown scene | Current frame compared with the same camera's dry baseline; fixed references (curb, barrier, sign pole) measured once |
| Time | One reading per photo | A reading every few minutes per camera, so water is rising or falling |
| Coverage | Wherever people post | Only where cameras point, mostly freeways; everything else is "no camera" |
| Routing goal | Avoid all water | Least-deep route within the vehicle's depth limit |
| Demo data | Uploaded photos | TranStar does not record video or save images ([KPRC](https://www.click2houston.com/news/local/2024/05/15/what-will-it-take-for-houston-transtar-cameras-to-record)), so we collect dry baselines today and flood-time frames from a past event, and replay them |

**How the dispatcher router works.** Full rules and the prediction math: [`docs/routing-and-prediction.md`](routing-and-prediction.md).

1. The agency sets a depth limit for each vehicle type. A person sets it, never the agent.
2. Each road segment a camera watches gets a depth of mean + 1 standard deviation, so the router plans on the cautious number.
3. Drop every segment deeper than the vehicle's limit.
4. Among the remaining routes, pick the one whose deepest point is shallowest, then the shortest of those. To do this, try depth caps in small steps (0, 5, 10 cm and up to the limit); the first cap that still connects start to end wins, and `networkx` finds the shortest path under it.
5. Nemotron Lightning presents 2–3 options with total distance, deepest point and distance not covered by any camera. The dispatcher picks one.
6. If a camera on the chosen route shows water rising, the agent re-plans and alerts the dispatcher.

Roads with no camera stay open, since most roads have none, but they're drawn grey and counted on every option card so the dispatcher sees what is unobserved.

**Depth over time.** Each camera gets its own Gaussian process with time in place of distance: the same math, smoothing noisy frame-by-frame readings and giving a rate of rise with uncertainty.

**Positioning.** Researchers have already estimated flood depth from existing traffic-camera images ([Water Resources Management, 2023](https://link.springer.com/article/10.1007/s11269-023-03669-9)), so lead with what's new: an agent that turns a city's existing cameras into live, depth-aware routing for dispatchers, with no new hardware (CRIS-HAZARD installs its own cameras).

**New risks.**

- [ ] Find flood-time frames from at least 5 cameras in one corridor of a past event (the biggest demo risk)
- [ ] Capture dry baseline frames from those same cameras today
- [ ] Check TranStar's terms for reusing camera snapshots, ask an organizer, and credit TranStar on screen
- [ ] Night and rain frames: have the agent mark them low confidence rather than guess

## How it works

Every photo goes through the same steps and ends as a depth pin that a human confirms.

&#91;embedded content: photo-to-route pipeline · 7 steps, 1 reject branch\]

Photos that fail vetting stop there. Usable ones get two independent depth estimates, and nothing reaches the priority list until a dispatcher confirms it.

Confirmed pins then feed the route agent, which proposes least-deep routes within the depth limit the agency sets.

## Where AI/ML does the work

Each of the three required tools has a job that a form or a search box couldn't do. The agent ties them together and ends every photo with a checkable result.

| Part | Tool | Job | Output |
| --- | --- | --- | --- |
| Photo vetting | Nemotron vision-language model (e.g. [Nemotron Nano 2 VL, 12B](https://developer.nvidia.com/blog/develop-specialized-ai-agents-with-new-nvidia-nemotron-vision-rag-and-guardrail-models/)) | Is this a flood? A duplicate or a reposted old photo? Does the location make sense? | Keep or reject, with a reason |
| Depth reading | Same Nemotron VLM | Finds reference objects (tire, curb, sign, door, person) and where the waterline hits each one | Depth range in cm, objects used |
| Object finder | PyTorch: pretrained torchvision Faster R-CNN (stretch: a CNN fine-tuned on depth levels) | Boxes cars, trucks, people, stop signs and hydrants so Super VL reads the waterline against known objects | Labeled boxes |
| Depth map | scikit-learn `GaussianProcessRegressor` | Interpolates between geotagged pins | Continuous depth surface with uncertainty |
| Hotspots | scikit-learn `DBSCAN` | Groups nearby deep readings | Ranked rescue-priority list |
| Agent loop | Nemotron reasoning model | Runs the steps, merges the two depth estimates, writes a one-line explanation per pin | Pin + explanation, waiting for dispatcher approval |
| Least-deep routes | Nemotron reasoning model + routing tool (osmnx + networkx on OpenStreetMap) | Calls the router, checks the route against pins, re-plans when a new pin lands on it | Route that avoids flooded streets + list of what it avoided, each with its photo |
| App | Next.js + Supabase + Leaflet | Upload, storage, live map, confirm/reject buttons | What judges see |

The combined estimate is the honest part: when the VLM and the CNN disagree, the pin shows a wider range and lower confidence instead of hiding the conflict.

## Nemotron model plan

The event kit allows any Nemotron model. These picks follow the kit's own recommendation for each kind of job, so the vision work and the fast tool-calling work run on the models built for them.

| Job | Nemotron model | Why this one (per the kit) |
| --- | --- | --- |
| Photo vetting + waterline reading | Nemotron 3.5 Super VL (120B total / 12B active) | Built for multi-step agents that need tools and image understanding |
| Orchestrator + routing tool calls | Nemotron 3.5 Lightning (30B total / 3B active) | Fast tool calls, routing and high-volume text; up to 1M-token context, 6 languages |
| Upload screening (new) | Nemotron 3.5 Content Safety | Text and image moderation in 12 languages with custom policies; photos end up on a public map |
| Stretch: voice reports | Nemotron 3.5 Transcribe or ASR Streaming | 40 languages; a resident can say "water's up to my knees on Bissonnet" instead of sending a photo |
| Stretch: spoken directions | Magpie TTS Multilingual | Reads the dispatcher's chosen route aloud to the crew, in 12 languages |

The Nemotron Nano 2 VL named in the earlier table still works; Super VL is the kit's current pick for images.

**Access and compute.** Call the free hosted endpoints on NVIDIA Build from a Brev CPU instance; the kit says most hackathon agents never need more. Each team gets one $50 Brev coupon. Use a T4 or L4 only if fine-tuning the CNN on CPU is too slow, and stop instances when idle.

**Framework.** Wrap the agent in the NeMo Agent Toolkit. It works with LangGraph or a custom stack and adds tracing and evaluation, which feed straight into the criteria below.

## Least-deep route agent

> Current rules and math: [`docs/routing-and-prediction.md`](routing-and-prediction.md). Where this section differs, that doc wins.

The agent also proposes least-deep route options. It runs a real routing tool over Houston's road map, drops every segment deeper than the person-set depth limit, and re-plans when new readings change the chosen route.

1. Load the road network for one part of Houston from OpenStreetMap with `osmnx`, and route with `networkx`.
2. Snap each confirmed pin to its nearest road segment. Use the depth surface to mark nearby segments flooded or uncertain.
3. Give Nemotron three tools: `get_route(start, end)`, `pins_near_route(route)` and `explain_route(route)`.
4. A user asks in plain language: "Get me from Meyerland to the Medical Center." Nemotron calls the router, checks the route against the pins, re-plans if needed, and returns the route plus each flooded street it avoided, linked to its photo.
5. When a new pin lands on an active route, the agent re-plans and flags the change.

**Why Nemotron calls a router instead of routing itself.** Language models are unreliable at shortest-path math, so Nemotron decides and explains while the tool computes. NVIDIA positions its Nemotron Nano reasoning model for agentic reasoning that includes tool calling ([NVIDIA](https://developer.nvidia.com/blog/develop-specialized-ai-agents-with-new-nvidia-nemotron-vision-rag-and-guardrail-models/)).

**The routing rule: least-deep route within the vehicle's limit.** Dispatchers sometimes must cross water, so the router picks the route whose deepest point is shallowest (6 inches beats 1 foot), then the shortest of those, and never exceeds the depth limit the agency sets for that vehicle. Details are in the camera update section above.

**Prior work.** Texas A&M researchers already showed flood-aware routing in Houston, combining gauge readings with 20 crowd photos from Harvey ([Alizadeh et al., 2022](https://repository.library.noaa.gov/view/noaa/57328)). This version adds the agent, live photo vetting and plain-language requests.

## Demo moment and design

The whole demo is one gesture: drop in a flooded-street photo and watch a depth pin land and the map redraw.

A 60-second walkthrough:

1. Open on a map of Houston during a past flood, with a few pins already placed.
2. Drop in a new photo. The agent card reads: flood yes, recent yes, reference object sedan tire, water at top of tire, about 45 cm, knee-deep, medium confidence.
3. The pin lands and the depth surface redraws around it.
4. A cluster turns red and moves to the top of the priority list. The dispatcher taps Confirm.
5. Type "Get me from Meyerland to the Medical Center." The agent draws a route around the flooded streets and lists each one it avoided, with its photo. Drop a new pin on that route and watch it re-plan.
6. Drop in a reposted old photo. The agent rejects it and says why.
7. End on one slide comparing accuracy: VLM alone vs. CNN alone vs. combined.

**Design (Adobe "best design" angle).** The design is how non-experts read danger, not decoration:

- Depth shown as familiar silhouettes (ankle, knee, waist, car door, car roof) next to the number in cm.
- Confidence shown as pin opacity and a range bar, so shaky readings look shaky.
- A time slider to watch water rise and fall across the event.
- A color-blind-safe depth palette and a plain-language legend.
- One tap from any pin to the original photo and the agent's reasoning.

## Evidence it works

Published research already estimates flood depth from crowd photos to within a few inches. What's missing is an agent that vets the incoming photos and a map non-experts can read.

| Study | Method | Data | Error (MAE) |
| --- | --- | --- | --- |
| [FloodVision (arXiv 2509.04772)](https://arxiv.org/pdf/2509.04772) | Vision-language model names reference objects and their submerged share; a knowledge graph supplies true object heights | 110 crowdsourced photos from MyCoast New York | 8.17 cm, vs. 10.28 cm for the VLM alone |
| [Alizadeh & Behzadan, 2023](https://repository.library.noaa.gov/view/noaa/58645) | CNN detects traffic signs; compares visible pole length before and after the flood | Crowdsourced photos of submerged signs | 4.71 in |

The FloodVision result is the key design lesson: telling the model the real heights of reference objects beats letting it guess. Build a small table of reference heights (sedan tire, curb, stop sign, door handle) on day one.

FloodVision doesn't say its curated dataset is public, so plan to collect and label your own demo set.

## What already exists

Houston already has good maps of where water is. None of the official tools says how deep it is on a given street, and the two apps that do need a stop sign or an installed camera.

| Tool | Run by | What it shows | Street-level depth? |
| --- | --- | --- | --- |
| [Harris County Flood Warning System](https://www.hcfcd.org/Community/Communications/News-Room/post/hcfcd-enhances-flood-warning-system-with-inundation-mapping) | Harris County Flood Control District | Gauge levels and current flooding next to gauged bayous and creeks | No: extent only, no depth |
| [TranStar Roadway Flood Warning](https://www.txdot.gov/content/dam/docs/programs/houston-transtar-roadway-flood-warning-system-fy2022.pdf) | Houston TranStar | Roads where rainfall and stream sensors pass flood thresholds | No: where flooding is likely |
| [DriveTexas](https://www.txdot.gov/about/newsroom/stories/know-the-hidden-dangers-of-a-flooded-roadway.html) | TxDOT | Road closures and alternate routes in real time | No |
| [NWS Flood Inundation Mapping](https://www.insurancejournal.com/news/national/2026/09/28/887007.htm) | National Weather Service | River and stream flood extent, now nearly nationwide, with forecasts | Not for rain flooding away from rivers |
| [Waze flood reports](https://support.google.com/waze/answer/13809605) | Drivers | A flood marker on a road | No depth field described |
| [BluPix](https://stories.tamu.edu/news/2020/08/26/construction-science-professor-develops-unique-app-to-gauge-flood-levels/) | Texas A&M (Behzadan group), 2020 | AI depth from photos that include a stop sign, paired with a pre-flood photo of the same spot | Yes, at stop signs |
| [CRIS-HAZARD](https://www.stpetersburg.usf.edu/news/2026/flood-monitoring-system-expands-from-research-tool-to-critical-community-resource.aspx) | USF St. Petersburg | About 40 solar cameras with depth markers plus a resident photo app, Pinellas County, Florida | Yes, at camera sites |
| Every Photo Is a River Gauge | Us | Depth from any photo, vetted by an agent, plus least-deep route options | Yes, wherever photos are posted (accuracy unproven) |

How to position it:

- **Any photo works.** It reads whatever reference object is in frame; no stop sign, no before photo.
- **No hardware.** Nothing to install before the flood.
- **The agent vets every photo** before it reaches the map.
- **It adds depth to the maps Houston already uses** instead of replacing them.
- **It acts on the data** by planning routes around confirmed flooding.

Name BluPix, CRIS-HAZARD and the Texas A&M routing paper as prior work in the pitch. A judge may know BluPix.

## Today's plan: 11:30 AM to 7:30 PM

Hacking ends at 7:30 PM, preliminary Devpost submissions are due at 6:00 PM, and judging is in person from 8:00 to 9:30 PM in MSC 2300. That leaves about 8 hours, so this plan replaces the 12-hour plan below.

The biggest change is that **the PyTorch piece uses a pretrained detector instead of a fine-tuned CNN.** torchvision's COCO-trained Faster R-CNN already finds cars, trucks, people, stop signs and fire hydrants, so it boxes the reference objects with no labeling or training. Nemotron Super VL then reads the waterline against those boxes. Fine-tuning a depth CNN becomes a stretch goal.

**11:30 AM–12:30 PM: setup and data**

- [ ] Captain: Brev coupon, CPU instance, invite teammates; everyone gets a build.nvidia.com key
- [ ] C: repo, Next.js + Supabase, empty Leaflet map
- [ ] D: collect about 60 geotagged photos from one past Houston flood; hand-label 30 with depth levels for testing
- [ ] All: reference-height table (sedan tire, curb, stop sign, door handle, adult knee)

**12:30–2:30 PM: one photo becomes one pin**

- [ ] B: Super VL prompt that returns JSON (flood?, recent?, objects, waterline, depth range); Content Safety check before it
- [ ] A: torchvision detector boxes reference objects and passes them to the prompt
- [ ] C: upload → agent → pin on the map

**2:30–4:30 PM: agent, depth map and routes**

- [ ] B: Lightning orchestrator with tools (vet, read depth, place pin, get route, pins near route); NeMo Agent Toolkit only if setup takes under 30 minutes, otherwise log tool calls ourselves
- [ ] A: scikit-learn Gaussian process depth surface; osmnx + networkx router that closes flooded or uncertain roads
- [ ] C: route request box, route on the map, dispatcher confirm/reject

**4:30–5:30 PM: measure and fix**

- [ ] A + D: depth error on the 30 labeled photos (Super VL alone vs. Super VL with detector boxes and the reference-height table) and seconds per photo
- [ ] All: fix whatever breaks in the demo path

**5:30–6:00 PM: preliminary Devpost**

- [ ] D: submit the draft with the NVIDIA explanation and real numbers. Due 6:00 PM.

**6:00–7:30 PM: polish and ship**

- [ ] C: design pass for Best Design (depth silhouettes, confidence shading, readable legend)
- [ ] D: record a backup demo video; rehearse the 60-second pitch
- [ ] All: final submission by 7:30 PM

Cut in this order if behind: time slider, DBSCAN hotspots, voice and TTS stretch goals, fine-tuned CNN. Never cut photo vetting, depth pins, routing or the accuracy slide.

## 12-hour build plan

*Written before we knew the event runs 10:00 AM to 7:30 PM; use Today's plan above. Kept for reference.*

The plan assumes a team of four with one owner per lane; with fewer people, merge the model and agent lanes. Tick items off as you go.

Lanes: **A** = model (PyTorch), **B** = agent (Nemotron), **C** = map and app, **D** = data and pitch.

**Hours 0–1: scope and data**

- [ ] D: collect 300–500 photos from one past Houston flood, each with a location and time
- [ ] C: set up repo, Next.js + Supabase, empty Leaflet map
- [ ] All: agree on depth levels and a reference-height table
- [ ] Captain: redeem the team's Brev coupon, start a CPU instance, invite teammates; everyone gets a build.nvidia.com API key

**Hours 1–4: first estimates**

- [ ] B: Nemotron prompt that returns JSON (flood?, duplicate?, objects, waterline, depth range)
- [ ] D + A: hand-label about 200 photos with depth levels; hold out 50 for testing
- [ ] B: Nemotron 3.5 Content Safety check on every upload before it can reach the map

**Hours 4–7: models**

- [ ] A: fine-tune the CNN on depth levels
- [ ] A: Gaussian process depth surface and DBSCAN hotspots
- [ ] B: merge rule for VLM + CNN estimates
- [ ] B: load the OpenStreetMap road network for one part of Houston (osmnx) and a networkx routing function that closes flooded or uncertain segments

**Hours 7–10: wire it up**

- [ ] C: upload → agent → pin → map redraw
- [ ] C: dispatcher confirm/reject and priority list
- [ ] B: one-line explanation on every pin
- [ ] B: give Nemotron the route tools (get\_route, pins\_near\_route, explain\_route) and re-plan when a pin lands on an active route
- [ ] C: route request box and the route drawn on the map, with avoided streets linked to their photos

**Hours 10–11: measure**

- [ ] A + D: error on the 50 held-out photos for VLM alone, CNN alone and combined; one slide
- [ ] B: seconds per photo and per route request (Lightning vs. Super VL as orchestrator) and tool-call success rate from the NeMo Agent Toolkit traces; add to the slide

**Hours 11–12: ship**

- [ ] D: rehearse the 60-second demo and record a backup video
- [ ] All: Devpost write-up
- [ ] D: fill the brackets in the NVIDIA submission explanation with the measured numbers

Cut list if behind: drop the time slider first, then DBSCAN (keep the map), never the accuracy slide.

## Judging fit

On our working rubric it averages 4.4 of 5 (Ingenuity lowered to 3 after finding BluPix and CRIS-HAZARD), still the highest of the eight ideas we scored, and it has a credible angle on both sponsor tracks. These are our own equal-weight scores, not official ones.

**Official rubric (opening slides).** Technicality: how advanced is your code? Ingenuity: do you solve a unique problem? Diversity: is your project interdisciplinary? Applicability: can your project make a real impact? Looks: are you able to pitch your project? Judging is in person, 8:00–9:30 PM in MSC 2300. Track prizes: Best Design (Adobe, $250 gift cards) and Best Use of Nemotron (NVIDIA Brev credits).

| Criterion | Score /5 | Why |
| --- | --- | --- |
| Technicality | 5 | Multimodal reading, a trained model and spatial interpolation with uncertainty |
| Ingenuity | 3 | Photo-depth apps (BluPix, CRIS-HAZARD) and flood-routing research exist; any-photo reading, agent vetting and live re-routing are the new parts |
| Diversity | 5 | Hydrology, emergency management, computer vision, GIS, community reporting |
| Applicability | 4 | Clear need; responder adoption is untested |
| Looks | 5 | Photo in, pin out, map redraws: obvious in seconds |
| NVIDIA track | strong | The agent finishes work: vets each photo, places a pin and updates the priority list, all checked by a dispatcher, then proposes least-deep routes within the agency's depth limit |
| Adobe track | strong | Depth silhouettes, confidence shading and a time slider make danger readable to non-experts |

For the NVIDIA pitch, say the loop out loud: photo in → Nemotron judges and measures → pin and priority list out → human confirms → Nemotron routes around it.

## Meeting the NVIDIA track criteria

The track asks for "an agent where the model is doing real work" and then proof that Nemotron was the right choice. Here's how we cover each of the kit's five official criteria.

| Official criterion | How we show it |
| --- | --- |
| 1. Core model usage | Nemotron makes every decision: keep or reject each photo, read the waterline, merge the estimates, plan and re-plan routes. Without it there is no product. |
| 2. Technical execution | Orchestrator (Lightning) plus a vision specialist (Super VL), tool calls to the router, NeMo Agent Toolkit traces, and latency per photo shown on screen. If a VLM call fails, the pin falls back to the CNN estimate and is marked low confidence. |
| 3. Quality of AI output | Prompts grounded in a reference-height table (FloodVision's lesson), error measured on 50 held-out photos, Content Safety screening, and dispatcher confirm/reject as the feedback loop. |
| 4. Impact and usefulness | Clear audience (dispatchers and drivers in Houston), a real problem (vehicle drownings), and a path past the hackathon: county maps show flood extent but not depth. |
| 5. Creativity and differentiation | Reads any photo, not just stop signs; acts by routing instead of only mapping; always on, so it keeps watching new photos and re-plans. |

**Proving Nemotron was the right choice.** Show numbers, not claims:

- **Accuracy:** depth error for Super VL alone vs. Super VL grounded with detector boxes and reference heights.
- **Speed:** seconds per photo and per route request, with Lightning vs. Super VL as the orchestrator. This shows why the small fast model handles routing and the vision model handles photos.
- **Tool use:** successful vs. failed tool calls from the traces.
- **Open weights:** a county could self-host the same models (the kit lists open weights on Hugging Face), so residents' photos never leave its servers.

Don't claim Nemotron beats other models unless you measured it.

## NVIDIA submission explanation (draft)

The kit asks for a short explanation of what Nemotron is doing, why it matters, and how we maximize its capabilities. Paste this and fill in the brackets with measured numbers.

> Every Photo Is a River Gauge is an always-on flood agent for Houston. Most flood deaths happen when drivers enter water of unknown depth, and official maps show where water is, not how deep. Nemotron 3.5 Super VL vets each resident photo (is it a flood, is it recent, is the location plausible) and reads where the waterline hits reference objects of known height to produce a depth range. Nemotron 3.5 Lightning orchestrates: it checks that estimate against objects boxed by a PyTorch detector, explains each pin in one line, and calls a routing tool that treats confirmed flooding as closed roads, re-planning when new pins land. Nemotron 3.5 Content Safety screens uploads before they reach the public map, and a dispatcher confirms every pin. We maximize Nemotron by grounding prompts in a reference-height table, splitting work between a fast tool-calling model and a vision model, and evaluating on \[N\] held-out photos: \[X\] cm error with grounding vs. \[Y\] cm without, at \[Z\] seconds per photo.

## Risks, ethics and open questions

The biggest risk is a confident wrong pin, so every design choice leans toward showing uncertainty and keeping a human in the loop.

| Risk | Mitigation |
| --- | --- |
| Fake or reposted old photos | Check timestamps, flag near-duplicates, compare with neighboring pins |
| Reference objects vary (truck tire vs. sedan tire) | Report a range, not a point; widen it when objects disagree |
| Missing or wrong location | Reject photos with no location; never guess one |
| Faces and license plates | Blur them before storing or displaying |
| Mistaken for an official warning | Label the map as community-reported and unofficial; link to NWS alerts |
| Over-trust by drivers | Message stays "turn around" for any reading above ankle depth |
| Router sends a crew into deeper water than expected | Plan on the upper end of every range; drop segments above the person-set limit; predict at most 60 min ahead; show unobserved km on every option; roads with no data are "Unknown: no data", never dry |

Open questions:

- [x] Does the event require a specific Nemotron model or hosting?

  Answered by the event kit: any Nemotron model qualifies; hosted endpoints on NVIDIA Build or OpenRouter, or open weights on Brev.
- [ ] Where do we get a few hundred geotagged photos from one flood, and are we allowed to use them?
- [ ] Team size: does the four-lane plan fit?
- [ ] Which part of Houston do we load for routing, and does it match where our demo photos are?

## Sources

- [Turn Around Don't Drown](https://www.weather.gov/safety/flood-turn-around-dont-drown), National Weather Service
- [Flash flooding vehicle danger](https://weather.com/safety/floods/news/flash-flooding-vehicle-danger-20140717), weather.com
- [Peak flash flood season](https://www.foxweather.com/learn/peak-flash-flood-season-us-june-july), FOX Weather
- [FloodVision: knowledge-guided VLM flood depth estimation](https://arxiv.org/pdf/2509.04772), arXiv 2509.04772
- [Scalable flood inundation mapping using deep convolutional networks and traffic signage](https://repository.library.noaa.gov/view/noaa/58645), Alizadeh & Behzadan, 2023
- [New Nemotron vision, RAG and guardrail models](https://developer.nvidia.com/blog/develop-specialized-ai-agents-with-new-nvidia-nemotron-vision-rag-and-guardrail-models/), NVIDIA developer blog
- [HCFCD enhances Flood Warning System with inundation mapping](https://www.hcfcd.org/Community/Communications/News-Room/post/hcfcd-enhances-flood-warning-system-with-inundation-mapping), Harris County Flood Control District
- [TranStar Roadway Flood Warning System](https://www.txdot.gov/content/dam/docs/programs/houston-transtar-roadway-flood-warning-system-fy2022.pdf), TxDOT
- [Know the hidden dangers of a flooded roadway](https://www.txdot.gov/about/newsroom/stories/know-the-hidden-dangers-of-a-flooded-roadway.html), TxDOT
- [NWS flood inundation mapping expands nationwide](https://www.insurancejournal.com/news/national/2026/09/28/887007.htm), Insurance Journal
- [Report bad weather](https://support.google.com/waze/answer/13809605), Waze Help
- [Construction science professor develops app to gauge flood levels (BluPix)](https://stories.tamu.edu/news/2020/08/26/construction-science-professor-develops-unique-app-to-gauge-flood-levels/), Texas A&M Today
- [Flood monitoring system expands to critical community resource (CRIS-HAZARD)](https://www.stpetersburg.usf.edu/news/2026/flood-monitoring-system-expands-from-research-tool-to-critical-community-resource.aspx), USF St. Petersburg
- [Human-centered flood mapping and intelligent routing](https://repository.library.noaa.gov/view/noaa/57328), Alizadeh et al., 2022
- NVIDIA Nemotron Track – tidalBYTE Hack Developer Hack Kit (event PDF, November 2026): track challenge, five judging criteria, model guide, Brev and NVIDIA Build access
- tidalBYTE '26 Opening Slides (event PDF, November 21, 2026): prompt, rubric, prizes, rules and schedule
- [Ask 2: Can you get highway video for insurance purposes?](https://click2houston.com/traffic/2021/02/11/ask-2-can-you-get-highway-video-for-insurance-purposes), KPRC 2 (TranStar has about 1,000 freeway cameras)
- [What will it take for Houston TranStar cameras to record?](https://www.click2houston.com/news/local/2024/05/15/what-will-it-take-for-houston-transtar-cameras-to-record), KPRC 2 (system does not record video or save images)
- [Urban flood depth from traffic-camera images](https://link.springer.com/article/10.1007/s11269-023-03669-9), Water Resources Management, 2023
