---
version: "0.1.1"
level: auto
processes:
  design: auto
  implementation: auto
  testing: auto
  documentation: auto
  review: auto
  deployment: none
---

This format is based on [AI-DECLARATION.md](https://ai-declaration.md/en/0.1.1).

## Notes

- This is a fork of [DimwitLabs/Prosaic](https://github.com/DimwitLabs/Prosaic). The levels above are the highest anywhere in the fork, which is its own changes.
- Fork changes (`git log upstream/main..main`): Claude Code, Anthropic's coding agent, designed, wrote, tested and reviewed them at the fork owner's request. No human reviewed the code. They were verified with the test suite and headless measurements.
- Upstream code, as upstream declares it: architecture, UX and writing philosophy are entirely human-conceived, and AI assisted with implementation, debugging and iteration (level copilot; implementation pair; testing and documentation copilot).
