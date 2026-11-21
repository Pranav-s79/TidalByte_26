# Why the workflow is structured this way

The **event-specific criteria** are from the user's supplied prompt, rubric, and sponsor descriptions, not verified event documents. The generic links below informed tool and sponsor concept choices; **none are a substitute for the event's rules**.

- NVIDIA Nemotron official overview: https://www.nvidia.com/en-us/ai-data-science/foundation-models/nemotron/
- NVIDIA's separate agent toolkit hackathon retrospective: https://developer.nvidia.com/blog/hackathon-winners-bring-agentic-ai-to-life-with-the-nvidia-nemo-agent-toolkit/
- Adobe's separate Design Awards criteria: https://blog.adobe.com/en/publish/2026/06/18/adobe-max-2026-creativity-awards-here-are-categories-and-how-to-submit
- Anthropic on CLAUDE.md scope / keeping always-on instruction files short: https://claude.com/resources/articles/steering-claude-code-skills-hooks-rules-subagents-and-more
- OpenAI on Codex AGENTS.md: https://learn.chatgpt.com/docs/agent-configuration/agents-md

No scripts, runtime integrations, or technical implementations are included. The `AGENTS.md` / `CLAUDE.md` files are concise dispatch instructions, and the specialized procedures only load when requested.
