# Dependencies builder
FROM python:3.12-slim AS builder

RUN apt-get update && apt-get install -y build-essential gcc && \
    rm -rf /var/lib/apt/lists/* && apt-get clean

WORKDIR /app

RUN python -m venv /venv
ENV PATH="/venv/bin:$PATH"
ENV PYTHONUNBUFFERED=1

COPY requirements.txt .

RUN pip install --upgrade pip && \
    pip install uv && \
    uv pip install --no-cache-dir -r requirements.txt

COPY . .

# RUN pytest

FROM  python:3.12-slim AS production

RUN apt-get update && apt-get install -y --no-install-recommends \
    libnss3 libatk-bridge2.0-0 libgtk-3-0 libxss1 libasound2 libgbm1 libxshmfence1 \
    fonts-liberation libatk1.0-0 libcups2 libdrm2 libxcomposite1 libxdamage1 libxrandr2 \
    libxinerama1 libpangocairo-1.0-0 libpango-1.0-0 ca-certificates curl && \
    rm -rf /var/lib/apt/lists/* && apt-get clean

RUN groupadd -r appuser && useradd -r -g appuser appuser

COPY --from=builder /venv /venv
ENV PATH="/venv/bin:$PATH"
ENV PYTHONUNBUFFERED=1

WORKDIR /app
COPY --from=builder /app /app
RUN chown -R appuser:appuser /app

ENV PLAYWRIGHT_BROWSERS_PATH=/ms-playwright
RUN mkdir -p /ms-playwright && chown root:root /ms-playwright

RUN PLAYWRIGHT_BROWSERS_PATH=/ms-playwright /venv/bin/python -m playwright install --with-deps chromium && \
    chown -R appuser:appuser /ms-playwright
USER appuser

CMD ["python", "app.py"]