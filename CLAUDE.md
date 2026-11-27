# tickr-web: rules for agents

The tickr.bot web app: Django + Postgres behind the public site, on its own server (never beside
the trading bot). Docs: `web/README.md`. Split out of tickr-devs/Tickr on 2026-11-27 (history kept).

Sibling repositories: `tickr-bot` (bot, API, model), `tickr-infra` (Terraform of the servers,
including this app's server in `ops/aws/web`), `tickr-ios` (Apple apps).

## Hard rules

1. **Secrets are never read, printed, logged or committed.** Code handles credential variable
   NAMES and presence only. `.env`, tokens, passwords and personal data never enter the repo or logs.
2. **Never print the process environment.** Never run `env`, `printenv`, `export -p`, a bare `set`,
   never trace a shell that sees a secret (`set -x`), never print or iterate `os.environ` whole.
3. **Refuse, never guess.** Unknown input or a failed check is a typed refusal with one cause.
4. **Privacy promise.** The waitlist stores only email, language and the signed-up/confirmed
   times (the privacy page says so); a new stored field needs the owner's yes and a privacy page edit.
5. **The image user's uid equals `service_uid` in tickr-infra `ops/aws/web/variables.tf`.**
   tickr-infra's CI checks it against this repo's `web/Dockerfile`; change both together.

## How we work

- Work on a branch, open a pull request, keep it small (one reviewable idea). Threads never merge
  their own pull requests; the Reviewer thread reviews and queues them. Auth and session code
  (sign-in, passkeys, tokens) also needs Fable at the exact head.
- CI must be green (`ci`: web-tests, web-image). Never weaken a test or add a retry to pass CI.
- Deploy: `web/deploy/ship.sh` from the owner's Mac, only commits on origin/main; it reads the
  server's terraform outputs from a tickr-infra clone next to this one (or `TICKR_INFRA_DIR`).
- Releases: Actions > release (semver tag + GitHub Release); ship tagged commits.
- Write code, comments, commits and docs in English. The owner reads Russian in chat.
