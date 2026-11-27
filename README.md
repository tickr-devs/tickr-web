# tickr-web

The tickr.bot web app (Django + Postgres, Caddy, Docker). Everything lives in [`web/`](web/README.md):
the app, its tests, and its server files (`web/deploy`, including `ship.sh`, the deploy from the
owner's Mac). The server itself is Terraform in tickr-devs/tickr-infra (`ops/aws/web`).
