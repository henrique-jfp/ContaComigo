# Dockerfile para rodar ContaComigo com suporte a WeasyPrint (HTML -> PDF)
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

RUN apt-get update \
 && apt-get install -y --no-install-recommends --allow-downgrades --allow-remove-essential --allow-change-held-packages \
   build-essential \
   libcairo2 \
   libpango-1.0-0 \
   pango1.0-tools \
   libpangocairo-1.0-0 \
   libgdk-pixbuf-2.0-0 \
   libgdk-pixbuf-xlib-2.0-0 || true \
 && apt-get install -y --no-install-recommends \
   libffi-dev \
   shared-mime-info \
   fonts-dejavu-core \
   git \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copia apenas requirements primeiro para aproveitar cache do Docker
COPY requirements.txt /app/requirements.txt
RUN python -m pip install --upgrade pip setuptools wheel
RUN pip install --no-cache-dir -r /app/requirements.txt

# Copia o resto da aplicação
COPY . /app

# O Gunicorn usará o arquivo de configuração definitivo
CMD ["gunicorn", "-c", "gunicorn_config.py", "app:app"]
