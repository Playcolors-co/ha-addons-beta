ARG BUILD_FROM=docker.io/library/python:3.11-slim
FROM ${BUILD_FROM}

RUN apt-get update && apt-get install -y --no-install-recommends \
        jq curl ca-certificates ffmpeg \
    && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir agora-python-server-sdk paho-mqtt cryptography

# mediamtx (RTSP server) — republishes the robot's video for Home Assistant
ARG MEDIAMTX_VERSION=1.9.3
RUN set -e; \
    curl -fsSL "https://github.com/bluenviron/mediamtx/releases/download/v${MEDIAMTX_VERSION}/mediamtx_v${MEDIAMTX_VERSION}_linux_amd64.tar.gz" \
      | tar xz -C /usr/local/bin mediamtx

ENV LD_LIBRARY_PATH=/usr/local/lib/python3.11/site-packages/agora/agora_sdk
WORKDIR /app
COPY ebo_bridge.py ebo_cloud.py ebo_sign.py ebo_video.py run.sh /app/
RUN chmod +x /app/run.sh

CMD ["/app/run.sh"]
