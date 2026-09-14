ARG BASE_IMAGE=rocm/pytorch@sha256:c38eeda81d85f00fbe35d3d50ce42ce59c524e87d810624f4eb5c52fddb3b9ad
FROM ${BASE_IMAGE}

ARG LLAMAFACTORY_COMMIT=7af909522a951e3ad9f022ea6f88b6755257eaa5
ARG PIP_INDEX_URL=https://pypi.org/simple

LABEL org.opencontainers.image.title="LLaMA-Factory ROCm 7.14 for Halo Strix" \
      org.opencontainers.image.source="https://github.com/hiyouga/LlamaFactory" \
      org.opencontainers.image.revision="${LLAMAFACTORY_COMMIT}" \
      com.halostrix.project="halostrix-llamafactory" \
      com.halostrix.service="llamaboard" \
      com.halostrix.base-image="${BASE_IMAGE}"

ENV DEBIAN_FRONTEND=noninteractive \
    GRADIO_SERVER_NAME=0.0.0.0 \
    GRADIO_SERVER_PORT=7860 \
    HF_HOME=/workspace/hf-cache \
    HF_HUB_CACHE=/workspace/hf-cache/hub \
    TRANSFORMERS_CACHE=/workspace/hf-cache/transformers \
    TORCH_EXTENSIONS_DIR=/workspace/cache/torch-extensions \
    TRITON_CACHE_DIR=/workspace/cache/triton \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_ROOT_USER_ACTION=ignore

SHELL ["/bin/bash", "-o", "pipefail", "-c"]

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates curl \
    && rm -rf /var/lib/apt/lists/*

RUN curl --fail --location --retry 5 \
      "https://codeload.github.com/hiyouga/LlamaFactory/tar.gz/${LLAMAFACTORY_COMMIT}" \
      --output /opt/llamafactory-source.tar.gz \
    && mkdir -p /opt/llamafactory \
    && tar -xzf /opt/llamafactory-source.tar.gz -C /opt/llamafactory --strip-components=1 \
    && python3 -m pip install --no-cache-dir --index-url "${PIP_INDEX_URL}" \
      packaging wheel setuptools hatchling \
    && python3 -m pip install --no-cache-dir --index-url "${PIP_INDEX_URL}" \
      /opt/llamafactory \
    && rm /opt/llamafactory-source.tar.gz \
    && llamafactory-cli version

WORKDIR /workspace
EXPOSE 7860

CMD ["llamafactory-cli", "webui"]
