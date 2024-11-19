# syntax=docker/dockerfile:1
# Initialize device type args
ARG USE_CUDA=false
ARG USE_OLLAMA=false
ARG USE_CUDA_VER=cu121
ARG USE_EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2
ARG USE_RERANKING_MODEL=""
ARG BUILD_HASH=dev-build
ARG UID=0
ARG GID=0
ARG HTTP_PROXY
ARG HTTPS_PROXY
ARG http_proxy
ARG https_proxy

######## WebUI frontend ########
FROM --platform=$BUILDPLATFORM node:22-alpine3.20 AS build
ARG BUILD_HASH
ARG HTTP_PROXY
ARG HTTPS_PROXY
ARG http_proxy
ARG https_proxy

# Set proxy environment variables
ENV HTTP_PROXY=${HTTP_PROXY}
ENV HTTPS_PROXY=${HTTPS_PROXY}
ENV http_proxy=${HTTP_PROXY}
ENV https_proxy=${HTTPS_PROXY}

WORKDIR /app

# Copy package files
COPY package.json package-lock.json ./

# Download onnxruntime
RUN apk add --no-cache curl && \
    curl -x "${HTTP_PROXY}" -L -o /tmp/onnxruntime-linux-x64-gpu-1.19.2.tgz \
    https://github.com/microsoft/onnxruntime/releases/download/v1.19.2/onnxruntime-linux-x64-gpu-1.19.2.tgz && \
    tar -tzf /tmp/onnxruntime-linux-x64-gpu-1.19.2.tgz > /dev/null || (echo "Download failed" && exit 1)

# Install npm dependencies
RUN if [ ! -z "${HTTP_PROXY}" ]; then \
    npm config set proxy "${HTTP_PROXY}" && \
    npm config set https-proxy "${HTTP_PROXY}" && \
    npm config set strict-ssl false; \
    fi && \
    npm config set registry https://registry.npmjs.org/ && \
    # Set environment variable to skip ONNX download during npm install
    ONNXRUNTIME_DIST_PATH=/tmp/onnxruntime-linux-x64-gpu-1.19.2.tgz \
    npm ci --verbose

COPY . .
ENV APP_BUILD_HASH=${BUILD_HASH}
RUN npm run build

######## WebUI backend ########
FROM python:3.11-slim-bookworm AS base

# Use args
ARG USE_CUDA
ARG USE_OLLAMA
ARG USE_CUDA_VER
ARG USE_EMBEDDING_MODEL
ARG USE_RERANKING_MODEL
ARG UID
ARG GID
ARG HTTP_PROXY
ARG HTTPS_PROXY

# Set proxy environment variables
ENV HTTP_PROXY=${HTTP_PROXY}
ENV HTTPS_PROXY=${HTTPS_PROXY}
ENV http_proxy=${HTTP_PROXY}
ENV https_proxy=${HTTPS_PROXY}

ENV ENV=prod \
    PORT=8080 \
    USE_OLLAMA_DOCKER=${USE_OLLAMA} \
    USE_CUDA_DOCKER=${USE_CUDA} \
    USE_CUDA_DOCKER_VER=${USE_CUDA_VER} \
    USE_EMBEDDING_MODEL_DOCKER=${USE_EMBEDDING_MODEL} \
    USE_RERANKING_MODEL_DOCKER=${USE_RERANKING_MODEL}

WORKDIR /app/backend

ENV HOME=/root
RUN if [ $UID -ne 0 ]; then \
    if [ $GID -ne 0 ]; then \
    addgroup --gid $GID app; \
    fi; \
    adduser --uid $UID --gid $GID --home $HOME --disabled-password --no-create-home app; \
    fi

# Setup directories
RUN mkdir -p $HOME/.cache/chroma && \
    echo -n 00000000-0000-0000-0000-000000000000 > $HOME/.cache/chroma/telemetry_user_id

# Make sure the user has access to the app and root directory
RUN chown -R $UID:$GID /app $HOME

# Install dependencies for OLLAMA or default setup
RUN if [ "$USE_OLLAMA" = "true" ]; then \
    apt-get update && \
    apt-get install -y --no-install-recommends git build-essential pandoc netcat-openbsd curl && \
    apt-get install -y --no-install-recommends gcc python3-dev && \
    apt-get install -y --no-install-recommends ffmpeg libsm6 libxext6 && \
    apt-get install -y --no-install-recommends jq && \
    curl -fsSL https://ollama.com/install.sh | sh && \
    rm -rf /var/lib/apt/lists/*; \
    else \
    apt-get update && \
    apt-get install -y --no-install-recommends git build-essential pandoc gcc netcat-openbsd curl jq && \
    apt-get install -y --no-install-recommends gcc python3-dev && \
    apt-get install -y --no-install-recommends ffmpeg libsm6 libxext6 && \
    rm -rf /var/lib/apt/lists/*; \
    fi

# Install Python dependencies
COPY --chown=$UID:$GID ./backend/requirements.txt ./requirements.txt

RUN pip3 install uv && \
    if [ "$USE_CUDA" = "true" ]; then \
    pip3 install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/$USE_CUDA_DOCKER_VER --no-cache-dir && \
    uv pip install --system -r requirements.txt --no-cache-dir && \
    python -c "import os; from sentence_transformers import SentenceTransformer; SentenceTransformer(os.environ['RAG_EMBEDDING_MODEL'], device='cpu')" && \
    python -c "import os; from faster_whisper import WhisperModel; WhisperModel(os.environ['WHISPER_MODEL'], device='cpu', compute_type='int8', download_root=os.environ['WHISPER_MODEL_DIR'])"; \
    else \
    pip3 install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu --no-cache-dir && \
    uv pip install --system -r requirements.txt --no-cache-dir && \
    python -c "import os; from sentence_transformers import SentenceTransformer; SentenceTransformer(os.environ['RAG_EMBEDDING_MODEL'], device='cpu')" && \
    python -c "import os; from faster_whisper import WhisperModel; WhisperModel(os.environ['WHISPER_MODEL'], device='cpu', compute_type='int8', download_root=os.environ['WHISPER_MODEL_DIR'])"; \
    fi; \
    chown -R $UID:$GID /app/backend/data/

# Copy frontend build and backend code
COPY --chown=$UID:$GID --from=build /app/build /app/build
COPY --chown=$UID:$GID --from=build /app/package.json /app/package.json
COPY --chown=$UID:$GID ./backend .

EXPOSE 8080

HEALTHCHECK CMD curl --silent --fail http://localhost:${PORT:-8080}/health | jq -ne 'input.status == true' || exit 1

USER $UID:$GID

ARG BUILD_HASH
ENV WEBUI_BUILD_VERSION=${BUILD_HASH}
ENV DOCKER=true

CMD [ "bash", "start.sh"]
