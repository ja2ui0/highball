FROM python:3.11-slim

# Install system dependencies and Python packages
COPY requirements.txt /tmp/requirements.txt

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        nginx \
        rsync \
        restic \
        rclone \
        openssh-client \
        curl \
        supervisor \
        tzdata \
        jq \
        netcat-openbsd && \
    pip install --no-cache-dir -r /tmp/requirements.txt && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/* /tmp/requirements.txt /root/.cache

# Prepare runtime directories and users
RUN mkdir -p /app /config /restore && \
    useradd -r -s /bin/false backupuser && \
    chown -R www-data:www-data /var/log/nginx /var/lib/nginx

WORKDIR /app

# Copy application files
COPY nginx.conf /etc/nginx/sites-available/default
COPY supervisord.conf /etc/supervisor/conf.d/supervisord.conf
COPY config/ /config/
COPY favicon.ico /app/
COPY *.py /app/
COPY handlers/ /app/handlers/
COPY services/ /app/services/
COPY templates/ /app/templates/
COPY static/ /app/static/

# Fix ownership
RUN chown -R root:root /app /config

EXPOSE 80

HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost/ || exit 1

CMD ["/usr/bin/supervisord", "-c", "/etc/supervisor/conf.d/supervisord.conf"]

