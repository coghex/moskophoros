# The CI image: Python 3.13, exactly the development dependencies
# requirements.lock pins, and the git and bash the validation groups run. It
# contains no Blender, no project source and no project build output.
#
# Build it only through `image.py publish`, which stages exactly the recipe
# inputs the fingerprint covers as the build context and supplies that
# fingerprint. See docs/validation.md.
FROM python:3.13-slim-trixie@sha256:7c61056e61ac89e852de05f3dc6fa51a6dd2181797bceed46aa725dd7cb2cd3b

ARG RECIPE_FINGERPRINT

ENV LANG=C.UTF-8 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    VIRTUAL_ENV=/opt/moskophoros/venv \
    PATH=/opt/moskophoros/venv/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin

RUN apt-get update \
 && apt-get install --yes --no-install-recommends git \
 && rm -rf /var/lib/apt/lists/*

# The build context is mounted rather than copied, so no recipe file remains in
# the image. The environment has no pip of its own: it holds exactly the locked
# distributions, which the stamp checks before recording their versions.
RUN --mount=type=bind,target=/recipe \
    /usr/local/bin/python3 -m venv --without-pip /opt/moskophoros/venv \
 && /usr/local/bin/python3 -m pip --python /opt/moskophoros/venv/bin/python \
        install --no-deps --requirement /recipe/requirements.lock \
 && /opt/moskophoros/venv/bin/python /recipe/tools/ci-image/stamp.py \
        "$RECIPE_FINGERPRINT" /recipe/requirements.lock /opt/moskophoros/image.json

LABEL org.opencontainers.image.source="https://github.com/coghex/moskophoros" \
      org.opencontainers.image.description="Moskophoros validation environment"
