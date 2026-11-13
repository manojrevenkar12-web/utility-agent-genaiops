FROM python:3.12-slim
WORKDIR /app
RUN useradd --create-home --uid 10001 app
COPY pyproject.toml ./
COPY src ./src
RUN pip install --no-cache-dir '.[azure]' uvicorn
COPY config ./config
COPY examples ./examples
ENV PYTHONUNBUFFERED=1 \
    UTILITYAGENT_ROOT=/app
USER app
EXPOSE 8080
CMD ["uvicorn", "utilityagent.service.main:app", "--host", "0.0.0.0", "--port", "8080"]
