#!/bin/bash
# Build script for Insurance PDF Extractor Docker image

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Default values
IMAGE_NAME="insurance-pdf-extractor"
TAG="latest"
PLATFORM=""

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -t|--tag)
            TAG="$2"
            shift 2
            ;;
        -n|--name)
            IMAGE_NAME="$2"
            shift 2
            ;;
        --platform)
            PLATFORM="--platform $2"
            shift 2
            ;;
        -h|--help)
            echo "Usage: $0 [OPTIONS]"
            echo "Options:"
            echo "  -t, --tag TAG      Set image tag (default: latest)"
            echo "  -n, --name NAME    Set image name (default: insurance-pdf-extractor)"
            echo "  --platform ARCH    Set target platform (e.g., linux/amd64, linux/arm64)"
            echo "  -h, --help         Show this help message"
            exit 0
            ;;
        *)
            echo -e "${RED}Unknown option: $1${NC}"
            exit 1
            ;;
    esac
done

echo -e "${YELLOW}Building Docker image...${NC}"
echo "Image: $IMAGE_NAME:$TAG"
echo "Platform: ${PLATFORM:-default}"
echo

# Build the image
docker build $PLATFORM -t "$IMAGE_NAME:$TAG" .

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✅ Docker image built successfully!${NC}"
    echo "Image: $IMAGE_NAME:$TAG"
    echo
    echo "To run the container:"
    echo "  docker run -p 8000:8000 $IMAGE_NAME:$TAG"
    echo
    echo "Or use docker-compose:"
    echo "  docker-compose up"
else
    echo -e "${RED}❌ Docker build failed!${NC}"
    exit 1
fi