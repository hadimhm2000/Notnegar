FROM python:3.11-slim-bookworm

ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1 \
    TORCH_HOME=/models/torch NOTNEGAR_DATA=/data

# ffmpeg decodes any audio; LilyPond engraves the score; fonts render Persian text in the PDF
RUN apt-get update \
 && apt-get install -y --no-install-recommends ffmpeg lilypond fontconfig fonts-noto-core fonts-dejavu-core curl \
 && (apt-get install -y --no-install-recommends fonts-vazirmatn || true) \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt requirements-ml.txt ./

# CPU build of PyTorch by default; for an NVIDIA GPU use --build-arg TORCH_INDEX=https://download.pytorch.org/whl/cu121
ARG TORCH_INDEX=https://download.pytorch.org/whl/cpu
RUN pip install torch==2.3.1 torchaudio==2.3.1 --index-url ${TORCH_INDEX}
RUN pip install -r requirements.txt -r requirements-ml.txt

# Basic Pitch (polyphonic transcription for piano, guitar and other layers); optional
ARG WITH_BASIC_PITCH=1
RUN if [ "$WITH_BASIC_PITCH" = "1" ]; then pip install "basic-pitch==0.4.0" "numpy<2" || echo "basic-pitch skipped"; fi

COPY notnegar ./notnegar
COPY static ./static
COPY scripts ./scripts

# bake the Demucs weights into the image so the server works without internet access
ARG PRELOAD_MODELS=1
RUN if [ "$PRELOAD_MODELS" = "1" ]; then python scripts/download_models.py || echo "model preload failed; it will download on first use"; fi

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s CMD curl -fs http://localhost:8000/api/health || exit 1
CMD ["uvicorn", "notnegar.app:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "*"]
