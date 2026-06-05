# syntax=docker/dockerfile:1
#
# Build a custom app on top of one of the published pixi base images.
#
#   docker build -f examples/Dockerfile.app \
#       --build-arg BASE=pixi-ubi:micro -t pixi-ubi:app-micro .
#
# This works against full, minimal, AND micro because we only COPY files in.
# Note the constraint: on ubi-micro you CANNOT `RUN dnf install ...` (there is
# no package manager and no shell). Extend micro by COPY only. If you need to
# install OS packages at this layer, build on the full or minimal base instead
# -- or, better, add the dependency to pixi.toml and rebuild the base.

ARG BASE=pixi-ubi:micro
FROM ${BASE}

WORKDIR /app
COPY examples/extra.py /app/extra.py

ENTRYPOINT ["python", "/app/extra.py"]
