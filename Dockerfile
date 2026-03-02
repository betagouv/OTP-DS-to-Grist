FROM python:3.12-slim

ARG UID=1000
ARG GID=1000

RUN pip install poetry

RUN addgroup --gid $GID appgroup && \
    adduser --uid $UID --gid $GID appuser

USER appuser
WORKDIR /app

COPY --chown=appuser:appgroup pyproject.toml poetry.lock ./
RUN poetry config virtualenvs.in-project false && \
    poetry install --with dev --no-root

USER root
RUN echo '#!/bin/bash' > /usr/local/bin/run-dev && \
    echo 'exec /home/appuser/.cache/pypoetry/virtualenvs/otp-ds-to-grist-9TtSrW0h-py3.12/bin/poe dev' >> /usr/local/bin/run-dev && \
    chmod +x /usr/local/bin/run-dev

USER appuser

CMD ["run-dev"]
