FROM python:3.12-slim@sha256:05cda9777409a9c3ffddd94a4c476b79f0769a0b4857f0c7ed9226b6800b0d6f
WORKDIR /runner
COPY requirements.lock.txt .
RUN pip install --no-cache-dir -r requirements.lock.txt
COPY worker.py .
ENV PYTHONDONTWRITEBYTECODE=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1
USER 65534:65534
ENTRYPOINT ["python", "/runner/worker.py"]
