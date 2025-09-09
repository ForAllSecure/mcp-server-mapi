FROM ghcr.io/astral-sh/uv:debian

RUN curl -o /usr/local/bin/mapi https://app.mayhem.security/cli/mapi/linux-musl/latest/mapi && \
    chmod +x /usr/local/bin/mapi

RUN mkdir /app
WORKDIR /app

COPY . .

# Install deps and run
RUN uv run mcp-server-mapi || true
