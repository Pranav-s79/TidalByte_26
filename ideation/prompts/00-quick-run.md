# QUICK RUN — paste as the main coordinator task

You are coordinating **idea discovery only** for this hackathon. Read `AGENTS.md`, `context/hackathon.md`, `context/rubric.md`, `context/opportunity-brief.md`, `context/prize-lenses.md`, and the current `run-log.md`/indexes. Do not reread every individual source file unless needed.

**Run mode QUICK, with hard ceilings:** up to 2 narrow scouts, ~3 unique sources each; at most 6 distinct sourced problem statements; exactly 8 distinct idea cards where evidence permits; review only the top 4 if a review is needed; shortlist 3–5. Do not use agent-to-agent debate. If subagents unavailable or token budget is constrained, do scout tasks sequentially using only one agent.

**Process**
1. Read event facts and open questions. Keep unknown track constraints marked unknown.
2. Delegate ONE sponsor-oriented scout (`prompts/01-sponsor-scout.md`, NVIDIA + Adobe) and ONE community/problem-oriented scout (`prompts/02-problem-scout.md`). Each must write a separate discovery note and return only its path plus 2–4 bullet findings. Do not ask them to communicate.
3. Merge unique sources in `discovery/sources.md`; write `problems/index.md` and up to 6 short problem files using their template.
4. Follow `prompts/04-ideas.md`: generate 8 concept cards in `ideas/`; coverage target 2 NVIDIA-action, 2 Adobe-design-led, 2 wildcards, 2 user-impact-first. Do not force unsupported concepts. Update index.
5. Use `prompts/05-review.md` ONCE on top 4 if they cannot be ranked confidently; otherwise coordinator reviews and ranks directly with five general rubric dimensions and separate sponsor fit.
6. Update `reviews/scorecard.md`, `shortlist.md` (3–5 ideas), and `run-log.md`. Include evidence gaps and official-rule unknowns.
7. Final chat response: ≤200 words, only changed paths, top 3 ideas, and next unresolved rule. No code, architecture, or implementation advice.

**Stop condition:** shortlist exists and identifies substantive differences. Never recursively start a second discovery round to chase perfection.
