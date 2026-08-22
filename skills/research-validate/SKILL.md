---
name: research-validate
description: Fail-closed RKC validator. Unknown type or rel is an error. Accepted Claims need evidenced_by. Verbatim quotes must match the archived span.
---

# research-validate

```
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/rkc_validate.py --root knowledge
```

## Fail closed

- Type not in the eight RKC nouns → error.
- Rel not in the twelve registered rels → error. Do not invent. Do not write `draws_from` (content-media owns it).
- Invalid id (must be `<type-slug>.<subject-slug>.<ulid>`).
- Accepted Claim missing `evidenced_by`.
- `verbatim: true` Evidence whose text does not match the locator span.

Do not "fix" an unknown rel by minting a new one.
