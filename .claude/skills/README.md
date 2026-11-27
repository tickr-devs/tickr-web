# Vendored design skills

Claude Code skills by Emil Kowalski, from https://github.com/emilkowalski/skills at commit
`64eb3deb9a5fbfa041faf783e0bc3fd635872e9c` (2026-11-15), MIT licence (`LICENSE`).
Any Claude session started in this repository picks them up from `.claude/skills/`.

The files are copied unchanged except for the `> **Tickr:**` lines under each skill's front
matter: where a skill differs from this repository's `CLAUDE.md`, `CLAUDE.md` wins.

Left out: write-swift (Swift), animate-expo (React Native), pick-ui-library and ask-sonner (React libraries; the site has no React), prototype (we design in the mockup first).

To update: copy the chosen `skills/<name>/` folders from a newer commit, put the Tickr lines back,
and change the commit above. On a Mac, `npx skills@latest add emilkowalski/skills` installs the
full set for your own sessions.
