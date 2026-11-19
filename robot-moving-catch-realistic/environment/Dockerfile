FROM python@sha256:935c3c5b12357a7e10caa9c1e6ca5692344d97cf229832ef584be2cec9fc03df

# System packages come from Debian's snapshot archive at a fixed time, so every build installs the same versions.
RUN sed -i -e 's|http://deb.debian.org/debian-security|http://snapshot.debian.org/archive/debian-security/20261116T212321Z|' \
    -e 's|http://deb.debian.org/debian$|http://snapshot.debian.org/archive/debian/20261116T203818Z|' /etc/apt/sources.list.d/debian.sources
# curl, nodejs, npm and procps are what agent harnesses install or use at start-up. The task itself needs only Python.
RUN apt-get -o Acquire::Check-Valid-Until=false -o Acquire::Retries=5 update && apt-get install -y --no-install-recommends curl ca-certificates nodejs npm procps \
    && rm -rf /var/lib/apt/lists/*
ENV PYTHONDONTWRITEBYTECODE=1

WORKDIR /app
COPY robot.py /usr/local/bin/robot
RUN pip install --no-cache-dir numpy==2.5.5 pillow==12.2.0
COPY docs/ /app/docs/
RUN chmod +x /usr/local/bin/robot && mkdir -p /app/output
