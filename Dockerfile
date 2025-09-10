# We use the Astral UV image as a base, which includes Python and UV for dependency management
FROM ghcr.io/astral-sh/uv:debian

# Install mapi CLI
RUN curl -o /usr/local/bin/mapi https://app.mayhem.security/cli/mapi/linux-musl/latest/mapi && \
    chmod +x /usr/local/bin/mapi

# Set up app directory
RUN mkdir /app
WORKDIR /app

# Copy only files that affect dependency resolution
COPY pyproject.toml uv.lock ./
# Install deps only (cacheable layer)
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-install-project

# Copy rest of the files and install project
COPY . .
RUN uv pip install -e .

# Install deps and run
RUN uv run mcp-server-mapi version
