#!/bin/bash
set -e

# Build script for highball using docker compose
echo "🔨 Building highball with docker compose..."
docker compose build --no-cache

echo "🚀 Starting services..."
docker compose up -d

echo "🎉 Build and deployment complete!"
