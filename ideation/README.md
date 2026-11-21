# Hackathon ideation workspace

**Purpose:** Discover, generate, refine, compare, and shortlist project **concepts** for this hackathon. Stop before implementation. No code, architecture, dependency lists, API integration work, feasibility spikes, or build plans.

## Hackathon in one paragraph
Apply AI/ML to real-world problems with meaningful **cross-disciplinary impact**. General rubric: **Technicality, Ingenuity, Diversity, Applicability, Looks (pitchability)**. Special opportunities: **NVIDIA — best use of Nemotron to build an agent doing real work**; **Adobe — best design**. The event-specific rules and weights are not yet independently verified. See `context/hackathon.md`.

## File map
- `context/`: the prompt, rubric, sponsor-track interpretations, focused exploration brief, unanswered rules.
- `sponsors/` and `tracks/`: what each sponsor offers and what would make a strong entry in each track; facts must have links.
- `discovery/`: curated blog insights, community problems, past winners, trends, and shared source ledger.
- `problems/`: real problems, with an audience and supporting evidence; no premature solution.
- `brainstorming/`: low-cost divergent exercises and unusual combinations.
- `ideas/`: standardized concept cards; all statuses live here, not separate inbox/candidates folders.
- `reviews/`: single-pass independent reviews, common rubric scorecard, and useful objections.
- `prompts/`: runbooks for orchestrator and each bounded specialist.
- `shortlist.md`: final comparison and handoff (idea-only).
- `run-log.md`: minimal continuity record, so another session knows what changed.

## Start here
1. Verify the provided brief in `context/hackathon.md`; add the event URL/time window if known, otherwise preserve `UNKNOWN`.
2. In Claude Code, start from `ideation/` and open `prompts/00-quick-run.md` after `CLAUDE.md`.
3. In Codex, start from `ideation/` and open `prompts/00-quick-run.md` after `AGENTS.md`.
4. Either can run solo. Do not run both concurrently against the same files.
5. Review `shortlist.md`; only after choosing a winner move into a **separate implementation workspace**.

## Recommended order
Discovery → Problem bank → Divergent idea generation → One-pass critique → Score → Shortlist. Do not let researchers, idea generators, and critics continuously chat with each other. Their **files** are the handoffs.

## Key principle
Do not force a weak AI concept into a sponsor track. Favor a real problem and distinctive user outcome. NVIDIA concepts need an identifiable, bounded **task completed by an agent**; Adobe concepts need a meaningful **design-led user experience**, not mere polish. Both still need to fit the general prompt and rubric.
