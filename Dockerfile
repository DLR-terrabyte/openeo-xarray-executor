# ============================================================================
# Base stage
# ============================================================================
FROM ghcr.io/osgeo/gdal:ubuntu-small-3.13.1 AS base
WORKDIR /opt

ENV UV_PROJECT_ENVIRONMENT=/opt/openeo_xarray_executor/.venv \
    UV_PYTHON_PREFERENCE=only-system \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH=/opt/openeo_xarray_executor/.venv/bin:$PATH

# git wird für die Git-Dependency benötigt; python3-venv entfällt, das übernimmt uv selbst
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    git \
    build-essential \
    python3-dev \
    libexpat1 \
    libexpat1-dev \
    && rm -rf /var/lib/apt/lists/*

# uv-Binary direkt aus dem offiziellen Image übernehmen -> kein pip-Bootstrap mehr nötig
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Copy dependency files first for Docker layer caching
COPY README.md pyproject.toml uv.lock /opt/

COPY openeo_xarray_executor /opt/openeo_xarray_executor

# Install Python dependencies (nur main, ohne dev-Gruppe), gegen das Lockfile
RUN uv sync --frozen --no-dev

# ============================================================================
# Production stage
# ============================================================================
FROM ghcr.io/osgeo/gdal:ubuntu-small-3.13.1 AS prod
ARG USER_ID=1000
ARG GROUP_ID=1000

WORKDIR /opt/openeo_xarray_executor

ENV VIRTUAL_ENV=/opt/openeo_xarray_executor/.venv
ENV PATH="$VIRTUAL_ENV/bin:$PATH"
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Minimal runtime packages
RUN apt-get update && apt-get install -y --no-install-recommends \
    libexpat1 \
    libexpat1-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy virtual environment from builder
COPY --from=base \
    /opt/openeo_xarray_executor/.venv \
    /opt/openeo_xarray_executor/.venv

# Copy application source code
COPY ./openeo_xarray_executor \
    /opt/openeo_xarray_executor

# Create executor user
RUN groupadd -g ${GROUP_ID} -o executor && \
    useradd -m -u ${USER_ID} -g ${GROUP_ID} -o -s /bin/bash executor && \
    chown -R ${USER_ID}:${GROUP_ID} /opt/openeo_xarray_executor

USER ${USER_ID}

CMD ["openeo_executor"]
