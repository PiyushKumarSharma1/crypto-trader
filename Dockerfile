FROM python:3.11-slim
WORKDIR /app
COPY pyproject.toml ./
COPY nova ./nova
RUN pip install --no-cache-dir .
RUN useradd --create-home --uid 10001 nova && mkdir -p /app/runtime && chown -R nova:nova /app
USER nova
EXPOSE 8765
CMD ["python", "-m", "uvicorn", "nova.service:app", "--host", "0.0.0.0", "--port", "8765"]

