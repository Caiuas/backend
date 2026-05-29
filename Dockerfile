FROM ubuntu:latest
RUN apt update -y
RUN apt install -y python3
RUN apt install -y python3-pip
RUN apt install -y python-is-python3
RUN apt install -y python3-venv
WORKDIR /app
RUN python -m venv .venv
ENV PATH="/app/.venv/bin:$PATH"
COPY flask_app/requirements.txt .
RUN pip install -r requirements.txt