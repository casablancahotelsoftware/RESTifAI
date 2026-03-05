 
FROM python:3.11
WORKDIR /app
RUN apt-get update && apt-get install -y \
    curl \
    git \
    build-essential \
    && rm -rf /var/lib/apt/lists/*
# Install Node.js and npm
RUN curl -fsSL https://deb.nodesource.com/setup_18.x | bash - \
    && apt-get install -y nodejs
# Install UV (Python package manager)
RUN pip install uv
# Install Newman globally
RUN npm install -g newman
COPY . /app
RUN uv sync
RUN mkdir -p /app/output && chmod 777 /app/output
ENV PYTHONPATH=/app
ENV UV_PROJECT_ENVIRONMENT=/app/.venv
ENTRYPOINT ["uv", "run", "python", "src/cli_scripts/generate_tests.py"]
CMD []
 