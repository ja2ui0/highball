FROM backup-manager-base:latest

WORKDIR /app

# Copy application files (fast - just file copies)
COPY *.py /app/
COPY handlers/ /app/handlers/
COPY services/ /app/services/
COPY templates/ /app/templates/
COPY static/ /app/static/

# Copy default config files to /config
COPY config/ /config/

# Copy nginx and supervisor configs
COPY nginx.conf /etc/nginx/sites-available/default
COPY supervisord.conf /etc/supervisor/conf.d/supervisord.conf

# Fix permissions (fast)
RUN chown -R backupuser:backupuser /app /config

# Expose port
EXPOSE 80

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost/ || exit 1

# Run supervisor to manage nginx + python app
CMD ["/usr/bin/supervisord", "-c", "/etc/supervisor/conf.d/supervisord.conf"]
