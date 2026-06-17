FROM node:18-alpine

LABEL maintainer="AI Learning System"
LABEL description="Grafana JSON Datasource API for AI Learning System metrics"

WORKDIR /app

# Install dependencies
COPY package*.json ./
RUN npm ci --only=production

# Copy application
COPY grafana-api.js .
COPY db/learning.db ./db/

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
  CMD node -e "require('http').get('http://localhost:3000/health', (r) => process.exit(r.statusCode === 200 ? 0 : 1))"

# Expose port
EXPOSE 3000

# Run server
CMD ["node", "grafana-api.js"]
