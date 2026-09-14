ARG BASE_IMAGE=rocm/pytorch@sha256:a223aee17aef5d21c3b9f63436dd19d27d1c665ec8b2f40011c9546cabae2a80
ARG NODE_IMAGE=node@sha256:35531c52ce27b6575d69755c73e65d4468dba93a25644eed56dc12879cae9213
FROM ${NODE_IMAGE} AS frontend
ARG UNSLOTH_COMMIT=e18a069c15cde98c7af77ccdb952254db8b0315d
ARG UNSLOTH_TARBALL_SHA256=52037b47de581f360e1db0a2072e65202d8993782e99f0300f181df93c63eeb8
RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates curl \
    && rm -rf /var/lib/apt/lists/*
RUN curl --fail --location --retry 5 \
      "https://codeload.github.com/unslothai/unsloth/tar.gz/${UNSLOTH_COMMIT}" -o /source.tar.gz \
    && echo "${UNSLOTH_TARBALL_SHA256}  /source.tar.gz" | sha256sum --check --strict \
    && mkdir /source && tar -xzf /source.tar.gz -C /source --strip-components=1
WORKDIR /source/studio/frontend
RUN npm ci --ignore-scripts && npm run build

FROM ${BASE_IMAGE}
ARG UNSLOTH_COMMIT=e18a069c15cde98c7af77ccdb952254db8b0315d
ARG UNSLOTH_TARBALL_SHA256=52037b47de581f360e1db0a2072e65202d8993782e99f0300f181df93c63eeb8
ARG PIP_INDEX_URL=https://pypi.org/simple
LABEL org.opencontainers.image.title="Unsloth Studio PyTorch 2.11 ROCm 7.14 for Halo Strix" \
      org.opencontainers.image.source="https://github.com/unslothai/unsloth" \
      org.opencontainers.image.revision="${UNSLOTH_COMMIT}" \
      com.halostrix.project="halostrix-unsloth-studio" \
      com.halostrix.service="studio" \
      com.halostrix.commit="${UNSLOTH_COMMIT}" \
      com.halostrix.stack="pytorch-2.11-rocm-7.14-gfx1151"
ENV DEBIAN_FRONTEND=noninteractive PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_ROOT_USER_ACTION=ignore PYTHONUNBUFFERED=1
SHELL ["/bin/bash", "-o", "pipefail", "-c"]
RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates curl \
    && rm -rf /var/lib/apt/lists/*
RUN curl --fail --location --retry 5 \
      "https://codeload.github.com/unslothai/unsloth/tar.gz/${UNSLOTH_COMMIT}" -o /opt/unsloth.tar.gz \
    && echo "${UNSLOTH_TARBALL_SHA256}  /opt/unsloth.tar.gz" | sha256sum --check --strict \
    && mkdir /opt/unsloth && tar -xzf /opt/unsloth.tar.gz -C /opt/unsloth --strip-components=1 \
    && rm /opt/unsloth.tar.gz
COPY --from=frontend /source/studio/frontend/dist /opt/unsloth/studio/frontend/dist
COPY scripts/verify_stack.py /opt/verify_stack.py
RUN python3 /opt/verify_stack.py capture
RUN python3 -m pip install --no-cache-dir --index-url "${PIP_INDEX_URL}" \
      --constraint /opt/stack-constraints.txt \
      pydantic setuptools==80.9.0 setuptools-scm==9.2.0 \
    && python3 -m pip install --no-cache-dir --index-url "${PIP_INDEX_URL}" \
      --constraint /opt/stack-constraints.txt \
      -r /opt/unsloth/studio/backend/requirements/studio.txt \
    && python3 -m pip install --no-cache-dir --index-url "${PIP_INDEX_URL}" \
      --constraint /opt/stack-constraints.txt \
      -r /opt/unsloth/studio/backend/requirements/no-torch-runtime.txt \
    && python3 -m pip install --no-cache-dir --index-url "${PIP_INDEX_URL}" \
      --constraint /opt/stack-constraints.txt "/opt/unsloth[huggingface]" \
    && python3 -m pip check
RUN python3 /opt/verify_stack.py verify
COPY scripts/container-entrypoint.sh /usr/local/bin/halostrix-unsloth-entrypoint
RUN groupadd --gid 10001 unsloth && useradd --uid 10001 --gid 10001 --create-home unsloth \
    && mkdir -p /workspace/hf-cache /workspace/projects /workspace/tmp /home/unsloth/.unsloth/studio \
    && chown -R unsloth:unsloth /workspace /home/unsloth \
    && chmod 0755 /workspace /home/unsloth /home/unsloth/.unsloth \
      /usr/local/bin/halostrix-unsloth-entrypoint
USER unsloth
WORKDIR /workspace
EXPOSE 8888
CMD ["/usr/local/bin/halostrix-unsloth-entrypoint"]
