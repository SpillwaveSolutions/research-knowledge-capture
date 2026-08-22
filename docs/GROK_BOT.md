# Grok Bot

Identity: `grok-bot/research-knowledge-capture`.

Grok Build loads the Claude plugin layout with zero config. `.grok-plugin/marketplace.json` pins marketplace identity.

Isolation: one session, one actor. Ready PR against a branch. No force-push. No write to main. Do not document a private remote.

`GRAPH_USE_LLM_EXTRACTION` is a Layer 1 (`research-graph`) concern. Leave it unset here.
