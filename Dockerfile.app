FROM highball-base:latest

WORKDIR /app

# Copy application files in optimal order (most stable first)
COPY nginx.conf /etc/nginx/sites-available/default
COPY supervisord.conf /etc/supervisor/conf.d/supervisord.conf
COPY config/ /config/
COPY favicon.ico /app/
COPY *.py /app/
COPY handlers/ /app/handlers/
COPY services/ /app/services/
COPY templates/ /app/templates/
COPY static/ /app/static/

# Fix permissions in single layer
RUN chown -R root:root /app /config

EXPOSE 80

HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost/ || exit 1

CMD ["/usr/bin/supervisord", "-c", "/etc/supervisor/conf.d/supervisord.conf"]
