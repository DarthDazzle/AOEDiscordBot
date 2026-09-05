FROM python:3.12-slim

# ffmpeg + libopus for voice; docker CLI + compose plugin (static binaries) to
# manage the game-server stacks through the mounted docker socket.
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg libopus0 \
    && rm -rf /var/lib/apt/lists/*
COPY --from=docker:cli /usr/local/bin/docker /usr/local/bin/docker
COPY --from=docker:cli /usr/local/libexec/docker/cli-plugins/docker-compose /usr/local/libexec/docker/cli-plugins/docker-compose

WORKDIR /app
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    DATA_DIR=/app/data \
    TAUNTS_DIR=/app/taunts \
    SUNTZU_DIR=/app/suntzu

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY aoebot ./aoebot
COPY aunts.jpg taints.mp4 ./

CMD ["python", "-m", "aoebot"]
