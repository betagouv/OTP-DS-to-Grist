FROM python:3.12-slim

ARG UID=1000
ARG GID=1000

RUN pip install poetry

RUN addgroup --gid $GID appgroup && \
    adduser --uid $UID --gid $GID appuser

RUN mkdir /app && chown appuser:appgroup /app

WORKDIR /app

COPY --chown=appuser:appgroup pyproject.toml poetry.lock ./
COPY --chown=appuser:appgroup . .

USER appuser

RUN poetry config virtualenvs.in-project true && poetry install --with dev

CMD ["poetry", "run", "poe", "dev"]
