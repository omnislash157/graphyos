# The gallery as the site (graphyos #47). Railway pulls this repo and builds this file on its own builder —
# never GitHub Actions. The gallery is a build product that is not in git, so the image builds it: the engine
# installed from this checkout (what main does, not what PyPI last published), gallery.sh over gallery.txt
# with --no-provision (ten shallow clones, nothing of theirs executes), and the directory served by the
# standard library. Every deploy is a fresh gallery on the current engine.
FROM python:3.12-slim
RUN apt-get update -qq && apt-get install -y -qq --no-install-recommends git ca-certificates >/dev/null && rm -rf /var/lib/apt/lists/*
WORKDIR /src
COPY engine /src/engine
RUN pip install --no-cache-dir -q "/src/engine[typescript]"
COPY gallery.py gallery.sh gallery.txt /src/
# --jobs 4: the lane waits on clones, not cores (RECON §90); the builder's core count and memory cap are not this repo's to read
RUN bash gallery.sh --jobs 4 /site $(cat gallery.txt) && rm -rf /site/.work
ENV PORT=8080
EXPOSE 8080
CMD ["sh", "-c", "exec python3 -m http.server \"${PORT:-8080}\" --directory /site --bind 0.0.0.0"]
