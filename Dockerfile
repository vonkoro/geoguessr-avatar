# Headless image for servers without a GPU. WebGL runs on SwiftShader (software).
#   docker build -t geoguessr-avatar .
#   docker run --rm -v "$PWD:/out" geoguessr-avatar render <user-id> -a LOSE_KNEES -o /out/knees.png
FROM python:3.13-slim

ENV PYTHONUNBUFFERED=1 \
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright \
    XDG_CACHE_HOME=/cache

COPY . /src
RUN pip install --no-cache-dir /src \
    && playwright install --with-deps --only-shell chromium \
    && rm -rf /src /var/lib/apt/lists/*

VOLUME /cache
ENTRYPOINT ["geoguessr-avatar"]
CMD ["--help"]
