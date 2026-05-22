# --- Stage 1: Builder ---
# Install dependencies in a separate stage so they're cached
# independently from code changes. If only main.py changes,
# Docker reuses the cached pip install layer.
FROM python:3.11-slim AS builder

WORKDIR /app

# Copy requirements first — Docker caches this layer separately.
# As long as requirements.txt doesn't change, pip install is skipped.
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt


# --- Stage 2: Final image ---
FROM python:3.11-slim

# Create a non-root user to run the app.
# Running as root inside a container is a security risk —
# if the container is compromised, the attacker has root.
RUN addgroup --system appgroup && adduser --system --ingroup appgroup appuser

WORKDIR /app

# Copy installed packages from builder stage
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy application code
COPY . .

# Set ownership to non-root user
RUN chown -R appuser:appgroup /app
USER appuser

# Expose the port uvicorn will listen on
EXPOSE 8000

# Start the server.
# --host 0.0.0.0 makes it reachable from outside the container.
# --workers 2 runs 2 worker processes for better concurrency.
# Remove --reload in production (it's for development only).
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
