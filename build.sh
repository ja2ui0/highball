#!/bin/bash
set -e

# Build script for backup manager using docker compose
echo "🔨 Building backup manager with docker compose..."
docker compose build --no-cache

echo "🚀 Starting services..."
docker compose up -d

echo "🎉 Build and deployment complete!"
