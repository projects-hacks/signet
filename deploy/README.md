# Deploying

Two pieces, in two places, for one reason: the site is static files and the
verifier is a Python process that takes eight to thirteen seconds to answer.
Nothing that runs functions on a ten second timeout can host the second.

| Piece | Where | Why there |
|---|---|---|
| The site | Vercel | static, and the URL is the one a judge sees |
| The site, again | Xano static hosting | already working, and the Xano track is about their platform |
| The verifier | Hugging Face Spaces | Docker, no card, no cold start worth the name |

## The site

Vercel, with the project root set to `web`. Vite is detected, `npm ci` and
`npm run build` are the defaults, and the output is `dist`.

One environment variable, and it is read at **build** time rather than run time,
so changing it means redeploying:

```
VITE_API_BASE=https://<your-space>.hf.space
```

Leave it empty and the page expects the API on its own origin, which is right
when one process serves both and wrong here.

The site is two real pages rather than a client side router, `index.html` and
`verify/index.html`, so no rewrite rules are needed and an unknown path is an
honest 404.

## The verifier

A Docker Space. `deploy/space/` holds the Dockerfile and the Space README, and
the image installs the package from this repository at a pinned ref, so what is
deployed is what is reviewable.

Set the secrets from the table in `deploy/space/README.md`, including:

```
SIGNET_ALLOWED_ORIGINS=https://<your-project>.vercel.app
```

Without it the browser refuses the call, because the allowlist is named origins
only and never a wildcard. A verifier any page can drive on a reader's behalf is
a verifier whose answers can be attributed to a site that did not compute them.

## What is deliberately not deployed

Issuance, enrolment and the DNS write. They run from a machine a person
controls, and no public endpoint reaches them. That is why the verifier needs
three credentials rather than eight: a compromise of the public surface produces
a wrong answer about somebody's upload, never a forged document.
