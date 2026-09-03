# Build from the repo root so app/tools.py is in context:
#   docker build -f agentcore/Dockerfile -t civicmate-agent .
FROM --platform=linux/arm64 python:3.12-slim

WORKDIR /app

COPY agentcore/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/tools.py ./tools.py
COPY agentcore/runtime_app.py ./runtime_app.py

EXPOSE 8080
CMD ["python", "runtime_app.py"]
