FROM postgres:17-bookworm@sha256:837bed18782820fe967067cb5328b02b0d9992c1be9a37ee0c9c492cfc03af3b

ENV POSTGIS_VERSION=3.6.4+dfsg-2.pgdg12+1

ADD --chmod=0644 --checksum=sha256:0144068502a1eddd2a0280ede10ef607d1ec592ce819940991203941564e8e76 https://www.postgresql.org/media/keys/ACCC4CF8.asc /usr/share/keyrings/pgdg-archive.asc

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates \
    && printf '%s\n' 'deb [signed-by=/usr/share/keyrings/pgdg-archive.asc] https://apt-archive.postgresql.org/pub/repos/apt bookworm-pgdg-archive main' > /etc/apt/sources.list.d/postgis.list \
    && apt-get -o APT::Update::Error-Mode=any update \
    && apt-get install -y --no-install-recommends \
        "postgresql-17-postgis-3=$POSTGIS_VERSION" \
        "postgresql-17-postgis-3-scripts=$POSTGIS_VERSION" \
    && rm -rf /var/lib/apt/lists/*
