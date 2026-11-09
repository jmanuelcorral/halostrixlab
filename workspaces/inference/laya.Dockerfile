FROM python:3.11-slim-bookworm@sha256:a36c24f9cbdf4fd0f52d67f0823eeac19c2028c637cecc392d97f980d4fec56b
ENV PIP_DISABLE_PIP_VERSION_CHECK=1 PIP_NO_CACHE_DIR=1 PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 USE_TF=0 USE_TORCH=1 TOKENIZERS_PARALLELISM=false LAYA_DEVICE=cpu LAYA_THREADS=4 OMP_NUM_THREADS=4 HF_HOME=/cache
RUN pip install torch==2.8.0 --index-url https://download.pytorch.org/whl/cpu
COPY source/ /src/laya/
RUN pip install 'transformers==4.57.6' 'huggingface-hub==0.36.2' 'safetensors==0.7.0' 'numpy==2.2.6' 'fastapi==0.135.1' 'uvicorn==0.41.0' /src/laya && pip check && pip freeze --all > /opt/packages.txt
ENV HOME=/cache USER=laya LOGNAME=laya TORCHINDUCTOR_CACHE_DIR=/cache/torchinductor TORCH_COMPILE_DISABLE=1
COPY laya_server.py /opt/laya_server.py
LABEL org.opencontainers.image.source="https://github.com/NandhaKishorM/laya" org.opencontainers.image.revision="d120d4ba220711b93c171973118753460310e16b" org.opencontainers.image.licenses="Apache-2.0"
USER 10001:10001
WORKDIR /tmp
CMD ["python", "/opt/laya_server.py"]
