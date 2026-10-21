FROM docker.io/library/python:3.13-slim
WORKDIR /app
COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install --no-cache-dir .
ENV MCP_HOST=0.0.0.0 MCP_PORT=8650
EXPOSE 8650
USER 65534
CMD ["transmission-mcp"]
