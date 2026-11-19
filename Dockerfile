# Job Radar Agent + the pinned LinkedIn MCP server in ONE image.
# Base image pinned by digest (python:3.12-slim, Python 3.12.16 >= 3.12.4 required by the MCP server).
FROM python@sha256:5e2bdb1b0d542d5039cffb8181c65930093949194a65c365dfb1b0fe13a4fa5b

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    JOB_RADAR_HOME=/app \
    PLAYWRIGHT_BROWSERS_PATH=/opt/browsers

WORKDIR /app
COPY pyproject.toml README.md LICENSE NOTICE THIRD_PARTY_LICENSES ./
COPY src ./src
RUN pip install ".[linkedin,llm]" \
 && (patchright install --with-deps chromium || true)

# Apache-2.0 (mcp-server-linkedin): ship its LICENSE and NOTICE with the image, as the license requires.
COPY LICENSE NOTICE THIRD_PARTY_LICENSES /usr/share/licenses/job-radar-agent/
RUN mkdir -p /usr/share/licenses/mcp-server-linkedin \
 && cp /usr/local/lib/python3.12/site-packages/mcp_server_linkedin-*.dist-info/licenses/* /usr/share/licenses/mcp-server-linkedin/

# data/, sessions/, output/ and config files are mounted, never baked into the image.
RUN useradd --create-home runner && mkdir -p /app/data /app/sessions /app/output /app/logs && chown -R runner /app /opt/browsers
USER runner

ENTRYPOINT ["job-radar"]
CMD ["run", "--dry-run"]
