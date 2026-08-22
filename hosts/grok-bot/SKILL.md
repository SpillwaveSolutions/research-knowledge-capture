---
name: grok-bot-research-knowledge-capture
description: Bind a Grok Bot agent to RKC. Isolation, identity, fail-closed writes.
---

# Grok Bot / research-knowledge-capture

1. Identity: `grok-bot/research-knowledge-capture`
2. Grok Build loads the Claude plugin layout with zero config. `.grok-plugin/marketplace.json` pins identity.
3. Isolated session. Ready PR. No force-push. No write to main.
4. Layer 1 lives in `research-graph`. Do not stand up Chroma/Kuzu from this plugin.
