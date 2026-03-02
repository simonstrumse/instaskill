# instaskill

Claude Code skill package for Instagram saved posts — download, analyze, build editorial deep dives.

## Structure

```
.claude/skills/
├── instagram-pipeline/   # Sync + download + extract (bundled scripts)
├── instagram-analysis/   # Embeddings, topics, sentiment, networks
├── instagram-deep-dive/  # Narrative archives, chronicles, profiles
└── video-analysis/       # Key frames → AI vision → structured data
templates/                # Generalized reference scripts the agent adapts
reference/                # GOTCHAS.md, DATA_CONTRACT.md, DESIGN_SYSTEM.md
examples/                 # sample_config.py
```

## Skill chain

```
instagram-pipeline → instagram-analysis → instagram-deep-dive
                                        → video-analysis (optional)
```

## Key principles

- **Free by default:** Every skill works with Claude subagents (free on Max plan). Paid API modes are optional.
- **Templates are reference, not copy-paste:** The agent reads templates and adapts them for the user's collection.
- **Discovery over configuration:** Narrative frames, account types, and entity aliases emerge from data.
- **Trust hierarchy (video):** Claude = ground truth, Gemini = additive only, merge = deterministic script.
