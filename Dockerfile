FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY pyproject.toml README.md ./
COPY arcam_rs232 ./arcam_rs232
COPY main.py ./

RUN pip install --no-cache-dir .

ENTRYPOINT ["arcam-daemon"]
CMD ["--config", "/config/config.yaml"]
