# syntax=docker/dockerfile:1.7
FROM rust:1.99.0-bookworm@sha256:114c7a4425406451c2866b6aafe69fe29b1b298832db1277d411ac73c82d04d6 AS mago
ARG MAGO_REV=46df50c96d93d0ac3655c116c375574277cf0b30
WORKDIR /src
RUN --mount=type=secret,id=proxy_ca \
    if [ -s /run/secrets/proxy_ca ]; then export GIT_SSL_CAINFO=/run/secrets/proxy_ca; fi; \
    git init . && git remote add origin https://github.com/carthage-software/mago.git && \
    git fetch --depth 1 origin "$MAGO_REV" && git checkout --detach FETCH_HEAD && \
    test "$(git rev-parse HEAD)" = "$MAGO_REV"
RUN --mount=type=cache,target=/usr/local/cargo/registry \
    --mount=type=cache,target=/src/target \
    --mount=type=secret,id=proxy_ca \
    if [ -s /run/secrets/proxy_ca ]; then export CARGO_HTTP_CAINFO=/run/secrets/proxy_ca; fi; \
    cargo build --locked --release -j 6 && cp target/release/mago /mago && sha256sum Cargo.lock > /mago-cargo-lock.sha256 && \
    git rev-parse HEAD > /mago-source.sha && rustc --version > /mago-rust-version.txt && \
    mkdir -p /cargo-licenses && \
    find /usr/local/cargo/registry/src -type f \( -iname 'LICENSE*' -o -iname 'NOTICE*' -o -iname 'COPYING*' \) \
    -exec cp --parents '{}' /cargo-licenses/ \;

FROM python:3.12.12-slim-bookworm@sha256:593bd06efe90efa80dc4eee3948be7c0fde4134606dd40d8dd8dbcade98e669c AS python
FROM ghcr.io/astral-sh/uv:0.12.8@sha256:d1cbaeadc234fe19c0d93daabcf5e98738cd93c6d1dd4918ef6aa30735feb23a AS uv
FROM composer:2.9.1@sha256:7384cf9fa70b710af02c9f40bec6e44472e07138efa5ab3428a058087c0d2724 AS composer
FROM php:8.5.12-cli-bookworm@sha256:d4f6e10eb393de7e3a7a88e8b88e139072dd3ae297f6a5dada8257e6fe32c585
RUN apt-get update && apt-get install -y --no-install-recommends \
    git curl unzip libicu-dev libonig-dev libzip-dev libsqlite3-dev libexpat1 libffi8 libgdbm6 libreadline8 \
    && docker-php-ext-install -j4 intl mbstring pdo_sqlite zip \
    && rm -rf /var/lib/apt/lists/*
COPY --from=python /usr/local /usr/local
RUN ldconfig
COPY --from=uv /uv /usr/local/bin/uv
COPY --from=composer /usr/bin/composer /usr/local/bin/composer
COPY --from=mago /mago /usr/local/bin/mago
COPY --from=mago /mago-cargo-lock.sha256 /opt/mago-cargo-lock.sha256
COPY --from=mago /src/LICENSE-MIT /src/LICENSE-APACHE /opt/licenses/mago/
COPY --from=mago /src/crates/prelude/assets/extensions/rdkafka.NOTICE /opt/licenses/mago/rdkafka.NOTICE
COPY --from=mago /src/Cargo.lock /opt/licenses/mago/Cargo.lock
COPY --from=mago /cargo-licenses /opt/licenses/cargo/
COPY --from=mago /mago-source.sha /mago-rust-version.txt /opt/
COPY licenses /opt/licenses/tools/
COPY LICENSE /opt/licenses/poc/LICENSE
RUN mkdir -p /opt/licenses/php /opt/licenses/python-runtime && \
    tar -xOf /usr/src/php.tar.xz php-8.5.12/LICENSE > /opt/licenses/php/LICENSE && \
    cp /usr/local/lib/python3.12/LICENSE.txt /opt/licenses/python-runtime/LICENSE.txt
ENV UV_PROJECT_ENVIRONMENT=/opt/venv UV_PYTHON_DOWNLOADS=never
WORKDIR /opt/poc
COPY pyproject.toml uv.lock .python-version ./
COPY adapter ./adapter
RUN --mount=type=secret,id=proxy_ca \
    if [ -s /run/secrets/proxy_ca ]; then export SSL_CERT_FILE=/run/secrets/proxy_ca GIT_SSL_CAINFO=/run/secrets/proxy_ca; fi; \
    uv sync --frozen --no-dev --python /usr/local/bin/python3
COPY config ./config
COPY fixtures ./fixtures
COPY tests ./tests
COPY toolchain.lock.json ./toolchain.lock.json
COPY docker ./docker
RUN python3 /opt/poc/docker/identity.py > /opt/toolchain-runtime.json \
    && /opt/venv/bin/python /opt/poc/docker/collect-licenses \
    && dpkg-query -W > /opt/os-packages.txt \
    && groupadd -g 1000 poc && useradd -m -u 1000 -g poc poc \
    && mkdir -p /state /evidence && chown poc:poc /state /evidence
ENV PATH=/opt/venv/bin:$PATH HOME=/state SERENA_HOME=/state/serena \
    POC_EVIDENCE=/evidence MAGO_EXPERIMENTAL_SERVER=1 PYTHONUNBUFFERED=1
WORKDIR /app
USER poc
ENTRYPOINT ["/opt/poc/docker/entrypoint"]
CMD ["php", "-S", "0.0.0.0:8000", "-t", "public", "/opt/poc/docker/router.php"]
