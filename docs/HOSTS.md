# Host matrix

`research-knowledge-capture` is one plugin, five install surfaces. Skills live once under `skills/`.

| Host | Manifest | Install |
| --- | --- | --- |
| Agent Plugins 1.0 | `plugin.json` | any host that reads agent-plugins.org |
| Claude Code | `.claude-plugin/plugin.json` + `marketplace.json` | `claude plugin marketplace add SpillwaveSolutions/research-knowledge-capture` |
| Grok Build | `.grok-plugin/marketplace.json` | drop into workspace / Claude marketplace |
| Codex | `.codex-plugin/plugin.json` | `codex plugin marketplace add SpillwaveSolutions/research-knowledge-capture` |
| Cursor | `.cursor-plugin/plugin.json` + `.cursor/rules/` | `/plugin install research-knowledge-capture` |

Commands: `/research-ingest`, `/research-pack`, `/research-validate` (Codex: `$research-ingest`).
