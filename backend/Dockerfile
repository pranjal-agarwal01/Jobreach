# Jobreach backend: the API and the background worker run from this one image.
# Python + LibreOffice (headless, no GUI) + Carlito. Carlito is metric-compatible with Calibri,
# so line breaks and page counts match Word.
#
#   API (default):  uvicorn on $PORT (8000 if unset)
#   Worker:         python -m app.worker
#   Tests:          pytest -q
#
# Secrets come from the host's environment settings, never from the image (.env is excluded).
FROM python:3.12-slim-bookworm

RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      libreoffice-writer-nogui \
      fonts-crosextra-carlito \
      fontconfig \
 && rm -rf /var/lib/apt/lists/* \
 && fc-cache -f

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
ENV PYTHONPATH=/app PYTHONUNBUFFERED=1

# Run as an ordinary user, not root.
RUN useradd --create-home --uid 10001 jobreach && chown -R jobreach /app
USER jobreach

EXPOSE 8000
CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --proxy-headers --forwarded-allow-ips='*'"]
