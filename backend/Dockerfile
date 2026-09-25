# Backend image: Python + LibreOffice (headless, no GUI) + Carlito.
# Carlito is metric-compatible with Calibri, so line breaks and page counts match Word.
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

CMD ["pytest", "-q"]
