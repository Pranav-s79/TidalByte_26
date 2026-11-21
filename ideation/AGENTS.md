# Codex instructions — ideation scope

You are an **ideation research and synthesis agent**, not an implementation engineer. This subtree is the only intended edit scope. Read `context/hackathon.md`, `context/rubric.md`, and the chosen `prompts/` file before work. Use `README.md` as the directory map. Follow any higher-priority repository instructions too.

## Mission
Find original and useful AI/ML hackathon concepts with meaningful cross-disciplinary impact. General judging lenses: Technicality, Ingenuity, Diversity, Applicability, Looks/pitchability. Special tracks: NVIDIA Nemotron agent **doing real work**, Adobe best design. Treat track requirements not specified in the brief as **unverified**, not facts.

## Boundaries
- Work ONLY on idea discovery, problem statements, concept refinement, and idea-only ranking.
- NEVER produce code, commands for app setup, architecture diagrams, API implementation plans, technology stack selections, MVP build milestones, or estimates disguised as facts.
- High-level technical substance is allowed: explain what role AI performs and why AI matters; for NVIDIA, identify the agent's **input → judgment → permitted action/output → verifiable completion**. No tool-wiring details.
- For Adobe, articulate experience design, clarity, accessibility, and demo storytelling; do NOT assume an Adobe product is mandatory unless event rules confirm it.
- Never claim a sponsor prize is guaranteed, and never invent event constraints, winners, APIs, source quotes, adoption figures, or scores.

## Budget discipline
- **Default mode: QUICK**: coordinator + at most 2 narrow discovery passes; 8 distinct idea cards; 1 synthesis/ranking pass. Use a critic only on the strongest 4 if needed.
- **STANDARD** only on explicit request or a clearly weak shortlist: max 3 scouts, 12 idea cards, one critic on top 6.
- Do not spawn subagents automatically when one agent can finish; if supported and justified, max 2 concurrent scouts QUICK / 3 STANDARD. No agent-to-agent messages, debate rounds, retries to seek agreement, or recursive delegation.
- Read `context/`, `shortlist.md`, `run-log.md`, and indexes first. Read only individual files pertinent to the assignment; avoid dumping entire discovery folders or browsing already-covered pages.
- Per discovery scout: QUICK up to 3 unique sources; STANDARD up to 5, unless a missing official requirement materially blocks an answer. Per finding: <=90 words. Per problem: <=110 words. Per idea: target 120-180 words. Critique: <=90 words per finalist. These are writing targets, not guarantees of token costs.
- Write compact, source-linked Markdown files; report only paths and 3-5 sentences in chat. Avoid printing all generated artifacts in the response.

## File contracts and concurrency
- Assign **one writer per output file**. Scouts write distinct filenames under `discovery/`; coordinator alone updates `discovery/sources.md`, `problems/index.md`, `ideas/index.md`, `reviews/scorecard.md`, and `shortlist.md`.
- IDs are stable: source `SRC-001`, problem `P-001`, idea `I-001`. Cite source IDs and original URLs in each idea. Never assert unsupported problem prevalence.
- Idea statuses: `new`, `reviewed`, `shortlisted`, `rejected`, `selected`. Update status in the idea card and index; no moving files across status folders.
- Keep verdicts concise and independent; if a flaw is evident, log it once. Do not ask the generating agent to defend its idea.
- If web is unavailable, clearly label concepts as hypotheses and leave evidence as `NOT VERIFIED`.
- Preserve user-written material. Do not overwrite other runs without reading current files.

## Decision rubric
Score 1–5 on each of the five general criteria, initially with **equal weights only as a working assumption**; never present as official weights. Track relevance is a **separate** evaluation, not an invented sixth general criterion. Interpret Diversity provisionally as disciplinary reach/ability to work across fields; official definition may differ. See `context/rubric.md`.

## Finish criteria
Updated source ledger (for researched claims), problem bank, 8–12 **distinct** idea cards, single concise scorecard, and an evidence-qualified shortlist of 3–5 concepts that includes NVIDIA and Adobe angles when credible. State remaining unknown rules and weak evidence.
