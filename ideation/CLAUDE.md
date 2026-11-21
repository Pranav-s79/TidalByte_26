# Claude Code — hackathon ideation

This is a **research / brainstorming only** directory. Your job is to identify promising hackathon project concepts, not build them. The shared detailed working contract is in `AGENTS.md` (read it explicitly; it is not a Claude-specific instruction file). Read `context/hackathon.md` and `context/rubric.md` at task start; use only the relevant `prompts/` runbook afterward.

**Brief:** AI/ML for meaningful cross-disciplinary real-world impact. Judging: Technicality, Ingenuity, Diversity, Applicability, Looks/pitchability. NVIDIA: best use of **Nemotron** as an agent doing actual work. Adobe: best design. Do not invent unprovided track eligibility rules.

**Must not do:** implementation, coding, API wiring, architecture, tool setup, technical design docs, model benchmarks, speculative development estimates, or massive market research. Discuss AI behavior conceptually and user outcomes only.

**Claude optimization:**
1. Default to **one main session** and `prompts/00-quick-run.md`. Do not launch Agent Teams, multi-turn debates, or review/rebuttal loops.
2. If focused parallel scouting materially helps and subagents are available, launch at most **two** independent short scouting tasks in QUICK mode (three only in STANDARD). Each subagent gets only its assignment, source cap, and exact output file path; no full conversation history in handoff.
3. Subagents do not talk to each other. Each writes its own concise Markdown finding; the parent does one merge/dedupe pass and writes shared indexes and shortlist.
4. Do not spend tokens rereading all discoveries. Read the small source ledger and indexes first; open only the specific cited items necessary.
5. Keep parent-visible subagent reports to **file path + 2-4 bullets**. Detailed findings belong in the file, not chat.
6. Load domain-specific prompts **on demand**. Keep `CLAUDE.md` short and stable to minimize always-on context overhead.
7. Stop after the shortlist, even if some enticing idea could be elaborated technically. Mark research gaps honestly.

**Quality bar:** a plausible real beneficiary; a concrete problem; a clearly non-generic AI role; cross-disciplinary impact; an instantly understandable pitch/demo moment; traceable evidence; serious weaknesses visible. For NVIDIA specifically, do not confuse a chat interface with an agent that completes work. For Adobe, make the design solve a communication or usability problem, not just look stylish.

**At end:** name changed files and report 3-5 top ideas briefly. Do not reprint every card in chat.
