FROM nikolaik/python-nodejs:python3.12-nodejs22

RUN pip install poetry

RUN groupadd -g 1001 appgroup && \
    useradd -m -u 1001 -g appgroup appuser

RUN mkdir /app && chown appuser:appgroup /app

WORKDIR /app

COPY --chown=appuser:appgroup pyproject.toml poetry.lock ./
COPY --chown=appuser:appgroup . .

RUN apt-get update && \
    apt-get install -y zsh curl git && \
    rm -rf /var/lib/apt/lists/*

USER appuser

RUN mkdir -p /home/appuser/build && \
    echo 'source /home/appuser/build/.zshrc' >> ~/.zshenv

RUN poetry config virtualenvs.in-project true && poetry install --with dev
RUN npm install

CMD ["poetry", "run", "poe", "dev"]
