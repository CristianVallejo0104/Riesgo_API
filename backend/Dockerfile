# ── ETAPA 1: builder ──────────────────────────────────────
# Instala dependencias con compiladores
FROM python:3.11.9-slim-bookworm AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Crear entorno virtual aislado
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

# ── ETAPA 2: runtime ──────────────────────────────────────
# Solo copia lo necesario — sin compiladores
FROM python:3.11.9-slim-bookworm AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH"

WORKDIR /app

# Copia solo el venv construido — no los compiladores
COPY --from=builder /opt/venv /opt/venv

# Copia el código
COPY . .

# Usuario no-root por seguridad
RUN useradd --uid 1000 --create-home api
USER api

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]