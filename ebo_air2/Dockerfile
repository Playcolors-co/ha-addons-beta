ARG BUILD_FROM
FROM ${BUILD_FROM}

RUN apt-get update && apt-get install -y --no-install-recommends \
        jq curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir agora-python-server-sdk paho-mqtt cryptography

ENV LD_LIBRARY_PATH=/usr/local/lib/python3.11/site-packages/agora/agora_sdk
WORKDIR /app
COPY ebo_bridge.py ebo_cloud.py ebo_sign.py run.sh /app/
RUN chmod +x /app/run.sh

CMD ["/app/run.sh"]
