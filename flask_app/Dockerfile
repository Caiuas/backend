# Usa uma imagem Ubuntu recente. 'latest' sempre pegará a versão mais nova.
FROM ubuntu:25.04

# Define variáveis de ambiente para evitar perguntas durante a instalação
ENV DEBIAN_FRONTEND=noninteractive

# Atualiza os pacotes do sistema e instala as dependências básicas
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    python3 \
    python3-pip \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Define o diretório de trabalho dentro do container
WORKDIR /app

# Copia o arquivo de requisitos e instala as dependências Python
# Usa pip3 para garantir que está usando o Python 3
# Adiciona --break-system-packages para contornar o erro "externally-managed-environment"
COPY requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt --break-system-packages

# Copia o código da sua aplicação Flask para o container
# COPY app.py .

# Expõe a porta em que o Flask vai rodar
# EXPOSE 5000

# Comando para rodar a aplicação Flask
# Usa python3 para garantir que está usando o Python 3
# CMD ["flask", "run", "--host=0.0.0.0","--debug", "--port=5000"]
