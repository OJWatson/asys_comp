FROM python:3.10-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN pip install --no-cache-dir asreview==1.6.2

WORKDIR /workspace
EXPOSE 5000

CMD ["sh", "-lc", "asreview lab --host 0.0.0.0 --port ${ASREVIEW_LAB_PORT:-5000}"]
