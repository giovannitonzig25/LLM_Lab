FROM python:3.13-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app/src

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src ./src
COPY prove_reali ./prove_reali

# /data: cartella del volume `dati-note`, scrivibile dall'utente non root.
RUN useradd --create-home --uid 1000 app && mkdir /data && chown app /data
USER app

CMD ["python", "-m", "assistente.terminale"]
