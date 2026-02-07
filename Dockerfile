FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

# Install Node.js 20 for the WhatsApp bridge
RUN apt-get update && \
    apt-get install -y --no-install-recommends curl ca-certificates gnupg git && \
    mkdir -p /etc/apt/keyrings && \
    curl -fsSL https://deb.nodesource.com/gpgkey/nodesource-repo.gpg.key | gpg --dearmor -o /etc/apt/keyrings/nodesource.gpg && \
    echo "deb [signed-by=/etc/apt/keyrings/nodesource.gpg] https://deb.nodesource.com/node_20.x nodistro main" > /etc/apt/sources.list.d/nodesource.list && \
    apt-get update && \
    apt-get install -y --no-install-recommends nodejs && \
    apt-get purge -y gnupg && \
    apt-get autoremove -y && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies first (cached layer)
COPY pyproject.toml README.md LICENSE ./
RUN mkdir -p icron bridge && touch icron/__init__.py && \
    uv pip install --system --no-cache ".[mcp]" && \
    rm -rf icron bridge

# Copy the full source and install
COPY icron/ icron/
COPY bridge/ bridge/
COPY ui/ ui/
COPY start.sh /app/start.sh
COPY docker/entrypoint.sh /entrypoint.sh
RUN uv pip install --system --no-cache ".[mcp]"

# Convert line endings (CRLF to LF) and make scripts executable
RUN sed -i 's/\r$//' /app/start.sh /entrypoint.sh && \
    chmod +x /app/start.sh /entrypoint.sh

# Build the WhatsApp bridge
WORKDIR /app/bridge
RUN npm install && npm run build

# Build the web UI
WORKDIR /app/ui
RUN npm install && npm run build
WORKDIR /app

# Create config directory
RUN mkdir -p /root/.icron

# Gateway default port
EXPOSE 3883

# Health check for the gateway
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:3883/health || exit 1

ENTRYPOINT ["icron"]
CMD ["status"]
