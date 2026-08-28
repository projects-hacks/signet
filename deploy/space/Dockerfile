# The verifier, and only the verifier.
#
# What runs here answers three questions about a document somebody uploaded. It
# cannot issue one, cannot enrol an issuer, and cannot write to DNS: those live
# in the command line and stay on a machine a person controls. That is why the
# credential list below is three entries rather than eight, and why a compromise
# of this container cannot mint a signature.
#
# The image installs from the public repository at a pinned commit rather than
# copying a snapshot, so what is deployed is exactly what is reviewable.

FROM python:3.13-slim

# Spaces run the container as uid 1000 and files copied in must be owned by it.
RUN useradd -m -u 1000 user
USER user
ENV HOME=/home/user \
    PATH=/home/user/.local/bin:$PATH \
    PYTHONUNBUFFERED=1
WORKDIR $HOME/app

# The one thing to change when redeploying.
ARG SIGNET_REF=main

RUN pip install --no-cache-dir --upgrade pip \
 && pip install --no-cache-dir "signet @ git+https://github.com/projects-hacks/signet@${SIGNET_REF}"

# Fixtures are the default in the library, so live behaviour is opt in and a
# misconfigured deployment serves recorded answers rather than wrong ones.
ENV SIGNET_FIXTURES=0

# Spaces exposes 7860. Nothing else is reachable from outside the container.
EXPOSE 7860

# No static root: the site is served from elsewhere, so this process is an API
# and a request for a page is a 404 rather than a stale copy of the frontend.
CMD ["python", "-c", "import uvicorn; from signet.api.app import create_app; \
uvicorn.run(create_app(static_root=None), host='0.0.0.0', port=7860)"]
