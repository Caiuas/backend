# Usa uma imagem Ubuntu recente. 'latest' sempre pegará a versão mais nova.
FROM python:3.12-bookworm

# Define variáveis de ambiente para evitar perguntas durante a instalação
ENV DEBIAN_FRONTEND=noninteractive
ENV TZ=America/Sao_Paulo

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    build-essential \
    default-jdk \
    tzdata \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt --break-system-packages