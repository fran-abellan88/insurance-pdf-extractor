# Docker Setup for Insurance PDF Extractor

This document explains how to run the Insurance PDF Extractor using Docker.

## Quick Start

### 1. Setup Environment Variables

Copy the environment template and configure your API keys:

```bash
cp .env.example .env
# Edit .env with your Gemini API key and other settings
```

### 2. Run with Docker Compose (Recommended)

```bash
# Start the application
docker-compose up

# Or run in background
docker-compose up -d

# View logs
docker-compose logs -f

# Stop the application
docker-compose down
```

The application will be available at: http://localhost:8000

### 3. Run with Docker (Manual)

```bash
# Build the image
./docker-build.sh

# Run the container
docker run -p 8000:8000 \
  -e GEMINI_API_KEY="your-api-key" \
  -e API_KEY="your-secure-key" \
  insurance-pdf-extractor:latest
```

## Configuration

### Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `GEMINI_API_KEY` | Yes | - | Google Gemini API key |
| `API_KEY` | Yes | - | Comma-separated API keys for authentication |
| `ENVIRONMENT` | No | `production` | Environment mode |
| `LOG_LEVEL` | No | `INFO` | Logging level |
| `DEFAULT_MODEL` | No | `gemini-1.5-flash` | Default Gemini model |
| `MAX_FILE_SIZE_MB` | No | `50` | Maximum file size limit |
| `RATE_LIMIT_REQUESTS` | No | `100` | Rate limiting threshold |

### Volume Mounts

The docker-compose setup includes persistent volumes:

- `pdf_data`: Application data and database
- `pdf_logs`: Application logs

## Development Setup

For development with live code reloading:

```bash
# The override file enables development mode automatically
docker-compose up

# Or explicitly use development compose file
docker-compose -f docker-compose.yml -f docker-compose.dev.yml up
```

Development features:
- Live code reloading
- Debug logging
- Faster health checks
- Source code mounted as volume

## Build Options

### Build Script

Use the provided build script for customized builds:

```bash
# Build with default settings
./docker-build.sh

# Build with custom tag
./docker-build.sh --tag v1.0.0

# Build for specific platform
./docker-build.sh --platform linux/arm64

# Build with custom name
./docker-build.sh --name my-pdf-extractor --tag latest
```

### Manual Build

```bash
# Standard build
docker build -t insurance-pdf-extractor .

# Multi-platform build
docker buildx build --platform linux/amd64,linux/arm64 -t insurance-pdf-extractor .
```

## Health Checks

The container includes built-in health checks:

```bash
# Check container health
docker ps

# Manual health check
curl http://localhost:8000/health/live
```

Health check endpoints:
- `/health/live` - Liveness probe
- `/health/ready` - Readiness probe  
- `/health` - Full health status

## API Usage

Once running, test the API:

```bash
# Check health
curl http://localhost:8000/health

# Extract from PDF (requires API key)
curl -X POST "http://localhost:8000/api/v1/extract" \
  -H "X-API-Key: your-api-key" \
  -F "file=@document.pdf" \
  -F "document_type=quote"
```

## Production Deployment

### Security Considerations

1. **Environment Variables**: Use secrets management instead of plain text
2. **API Keys**: Generate strong, unique API keys
3. **HTTPS**: Use a reverse proxy (nginx) for SSL termination
4. **Network**: Run on isolated Docker network
5. **User**: Container runs as non-root user

### Recommended Production Setup

```yaml
# docker-compose.prod.yml
version: '3.8'
services:
  insurance-pdf-extractor:
    image: insurance-pdf-extractor:latest
    restart: unless-stopped
    environment:
      - ENVIRONMENT=production
      - LOG_LEVEL=WARNING
    secrets:
      - gemini_api_key
      - api_keys
    networks:
      - internal
    
  nginx:
    image: nginx:alpine
    ports:
      - "443:443"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf:ro
      - ./ssl:/etc/ssl:ro
    depends_on:
      - insurance-pdf-extractor
    networks:
      - internal

secrets:
  gemini_api_key:
    external: true
  api_keys:
    external: true

networks:
  internal:
    driver: bridge
```

## Troubleshooting

### Common Issues

1. **Port already in use**
   ```bash
   # Use different port
   docker-compose run -p 8001:8000 insurance-pdf-extractor
   ```

2. **Permission denied**
   ```bash
   # Fix file permissions
   sudo chown -R $USER:$USER .
   ```

3. **Build failures**
   ```bash
   # Clean build cache
   docker system prune -a
   docker-compose build --no-cache
   ```

4. **Memory issues**
   ```bash
   # Increase Docker memory limit
   # Check Docker Desktop settings
   ```

### Logs

View application logs:

```bash
# Docker Compose
docker-compose logs -f insurance-pdf-extractor

# Docker
docker logs -f <container-id>

# Inside container
docker exec -it <container-id> tail -f /app/logs/app.log
```

## Image Information

- **Base Image**: `python:3.11-slim`
- **User**: Non-root user (`appuser`)
- **Working Directory**: `/app`
- **Exposed Port**: `8000`
- **Health Check**: Enabled
- **Multi-stage Build**: Yes (optimized size)

## Performance

The Docker image is optimized for:
- **Size**: Multi-stage build reduces image size
- **Security**: Non-root user execution
- **Caching**: Efficient layer caching for dependencies
- **Health**: Built-in health monitoring
- **Scalability**: Stateless design for horizontal scaling