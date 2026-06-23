# Symbolic Music Assistant Configuration
- Tech Stack: Python 3.11+, google-adk (v2.0), music21, pretty_midi, matplotlib, FluidSynth
- Architecture Pattern: Single-agent Root with Native SkillToolset Progressive Disclosure
- Workflow Rule: Strictly use the official `google-agents-cli` for scaffolding, evaluations, and deployment routines. Do not generate code until scaffolding is confirmed.
- Testing Requirement: Every execution tier must pass programmatic trajectory validation in the target testing suites before graduating permissions.
