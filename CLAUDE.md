# CLAUDE.md

Guidance for Claude Code when working in this repo. See `README.md` for setup and
`PLAN.md` for the full build plan (journey logging is §9).

## Journey log — keep this updated as you work

This project is being built in public. The `/journal/` directory is raw material
for Instagram and atproto/Bluesky posts (PLAN.md §7) — it captures the actual
process of building Call of Kiuru, not just the finished result.

**Write an entry when something happens, not at the end of a session.** Good
triggers: a validation run completes (pass or fail), a model parameter gets
tuned and why, a pipeline bug gets found and fixed, a chart or dashboard view
renders for the first time or changes meaningfully, a dead end gets abandoned,
a decision gets made that wasn't obvious in advance.

**Format:** one file per entry, `journal/YYYY-MM-DD-short-slug.md`:

```markdown
---
date: YYYY-MM-DD
tags: [validation, pipeline, model, frontend, ...]
---

## What happened

Plain description of the milestone/bug/decision. Include actual numbers
(RMSE, day counts, city names) — specifics make better posts than "it worked."

## Why it's interesting

The non-obvious part: a surprise, a tradeoff, something a reader wouldn't
guess. This is the post hook.

## Post idea

One or two lines sketching an Instagram/Bluesky post angle, if one exists.
Skip this section if the entry is pure internal debugging with no public angle.

## Screenshots

- `screenshots/YYYY-MM-DD-description.png` — what it shows
```

Not every entry needs every section — a quick bug-fix entry might just be
"What happened" + a screenshot. A big validation milestone might have all four.

## Screenshots

- Store under `journal/screenshots/`, named `YYYY-MM-DD-description.png` to
  match the entry that references them.
- **Ask the user to take and save a screenshot** at moments worth capturing
  visually: a dashboard or chart rendering (especially the first time, or after
  a visible change), terminal output showing a validation result, a map view,
  anything that would read better as an image than a text description. Tell
  them exactly what to capture and where to save it (or offer to save it for
  them if it's something you can screenshot directly, e.g. via a running dev
  server).
- Don't ask for a screenshot of something purely internal (a diff, a config
  file) — those belong in the entry as text/code, not an image.

## Everything else

Follow the existing conventions in `PLAN.md` and `README.md` for stack choices,
data sources, and licensing (Copernicus CDS: open/commercial-use OK; ECA&D/
E-OBS bulk data: non-commercial only; PEP725: licence set per dataset since
May 2026, check each one before use. Do not conflate them).
