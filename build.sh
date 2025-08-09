#!/bin/bash
set -e

# Build script for backup manager

BASE_IMAGE="backup-manager-base"
APP_IMAGE="backup-manager"

build_base() {
    echo "🔨 Building base image (this takes a while, but only once)..."
    docker build -f Dockerfile.base -t $BASE_IMAGE:latest .
    echo "✅ Base image built: $BASE_IMAGE:latest"
}

build_app() {
    echo "🚀 Building app image (fast)..."
    docker build -t $APP_IMAGE:latest .
    echo "✅ App image built: $APP_IMAGE:latest"
}

case "${1:-app}" in
    "base")
        build_base
        ;;
    "app")
        # Check if base image exists
        if ! docker image inspect $BASE_IMAGE:latest >/dev/null 2>&1; then
            echo "❌ Base image not found. Building base image first..."
            build_base
        fi
        build_app
        ;;
    "all")
        build_base
        build_app
        ;;
    *)
        echo "Usage: $0 [base|app|all]"
        echo "  base - Build base image with dependencies (slow, run once)"
        echo "  app  - Build app image (fast, run during development)"
        echo "  all  - Build both images"
        exit 1
        ;;
esac

echo "🎉 Build complete!"
