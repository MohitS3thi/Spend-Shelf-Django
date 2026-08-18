# Production Deployment Guide: Spend Shelf

## Overview
This guide covers deploying Spend Shelf to production with PostgreSQL, Nginx, SSL, and monitoring.

---

## Prerequisites

### Local Setup (for testing)
- Docker & Docker Compose installed
- 4GB+ RAM available
- Ports 80, 443, 5432 available (or configure in docker-compose.prod.yml)

### Cloud Deployment (AWS, GCP, Azure, DigitalOcean)
- Ubuntu 22.04 LTS or similar
- Docker & Docker Compose pre-installed
- Domain name with DNS pointing to server IP

---

## Step-by-Step Deployment

### Step 1: Generate Secrets
```bash
# Generate secure Django secret key
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"

# Generate strong DB password (32 chars)
openssl rand -base64 32
```

### Step 2: Configure Production Environment
```bash
# Copy template and edit with real values
cp .env.production.example .env.production
nano .env.production  # Edit with:
# - DJANGO_SECRET_KEY (from Step 1)
# - DB_PASSWORD (from Step 1)
# - DJANGO_ALLOWED_HOSTS=yourdomain.com,www.yourdomain.com
# - SECURE_SSL_REDIRECT=True (after SSL setup)
```

### Step 3: Setup SSL Certificates

#### Option A: Let's Encrypt (Recommended for Production)
```bash
# Install Certbot
sudo apt-get update && sudo apt-get install -y certbot python3-certbot-nginx

# Get certificate (stop Nginx first if running)
sudo certbot certonly --standalone -d yourdomain.com -d www.yourdomain.com

# Copy certificates to project
mkdir -p ssl
sudo cp /etc/letsencrypt/live/yourdomain.com/fullchain.pem ssl/cert.pem
sudo cp /etc/letsencrypt/live/yourdomain.com/privkey.pem ssl/key.pem
sudo chown $USER:$USER ssl/*.pem
```

#### Option B: Self-Signed (Testing Only)
```bash
mkdir -p ssl
openssl req -x509 -newkey rsa:4096 -nodes \
  -out ssl/cert.pem -keyout ssl/key.pem -days 365 \
  -subj "/CN=yourdomain.com"
```

### Step 4: Enable HTTPS in Nginx
Edit `nginx.conf`:
```bash
# Uncomment the HTTPS server block and update:
# - server_name yourdomain.com www.yourdomain.com
# - ssl_certificate paths (should match above)
# - Uncomment HTTP->HTTPS redirect (return 301...)
```

### Step 5: Build & Deploy

#### Quick Deploy (All-in-One)
```bash
chmod +x deploy-prod.sh
./deploy-prod.sh
```

#### Manual Deploy
```bash
# 1. Start database
docker compose -f docker-compose.prod.yml up -d db
sleep 10

# 2. Check DB health
docker compose -f docker-compose.prod.yml exec db pg_isready -U spendshelf

# 3. Run migrations
docker compose -f docker-compose.prod.yml run --rm web python manage.py migrate --noinput

# 4. Collect static files
docker compose -f docker-compose.prod.yml run --rm web python manage.py collectstatic --noinput

# 5. Create superuser
docker compose -f docker-compose.prod.yml run --rm web python manage.py createsuperuser

# 6. Start all services
docker compose -f docker-compose.prod.yml up -d
```

### Step 6: Verify Deployment
```bash
# Check service status
docker compose -f docker-compose.prod.yml ps

# Test health endpoints
curl http://localhost/admin  # Should return 200 or redirect
curl http://localhost/static/admin/css/base.css

# View logs
docker compose -f docker-compose.prod.yml logs -f web
docker compose -f docker-compose.prod.yml logs -f nginx

# Monitor resources
docker stats
```

---

## Production Configuration

### Performance Tuning

**Gunicorn Workers:**
- 4 workers (current) for 2 vCPU / 2GB RAM
- Formula: `(2 × CPU_count) + 1`
- For 4 vCPU: `(2 × 4) + 1 = 9 workers`

Edit `docker-compose.prod.yml`:
```yaml
--workers 9
--worker-class gevent  # or sync (default)
--max-requests 1000    # Restart worker after 1000 requests to prevent memory leaks
--timeout 60           # 60s timeout for long-running requests
```

**Database Connection Pool:**
Add to `.env.production`:
```
DATABASES_CONN_MAX_AGE=600
DATABASE_POOL_SIZE=20
```

### SSL/TLS Renewal

**Auto-renewal with Certbot:**
```bash
# Certbot auto-renewal runs daily via systemd timer
sudo systemctl status certbot.timer
sudo certbot renew --dry-run  # Test renewal
```

**Manual renewal before expiry:**
```bash
sudo certbot renew --force-renewal
# Then copy renewed certs to ./ssl/
```

### Backups

**Automated daily backups:**
```bash
# Create backup script
cat > backup.sh << 'EOF'
#!/bin/bash
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="./backups"
mkdir -p $BACKUP_DIR

# Backup database
docker compose -f docker-compose.prod.yml exec -T db \
  pg_dump -U spendshelf spendshelf_prod \
  | gzip > $BACKUP_DIR/db_$DATE.sql.gz

# Backup app data and static files
tar -czf $BACKUP_DIR/app_data_$DATE.tar.gz ./volumes/app_data ./volumes/app_static

echo "Backup completed: $DATE"
EOF

chmod +x backup.sh

# Schedule with crontab
# 0 2 * * * cd /path/to/spend-shelf && ./backup.sh
```

**Restore from backup:**
```bash
# Restore database
gunzip < backups/db_20250117_020000.sql.gz | \
  docker compose -f docker-compose.prod.yml exec -T db \
  psql -U spendshelf spendshelf_prod

# Restore app data
tar -xzf backups/app_data_20250117_020000.tar.gz
```

---

## Monitoring & Logging

### View Logs
```bash
# Real-time logs
docker compose -f docker-compose.prod.yml logs -f

# Filter by service
docker compose -f docker-compose.prod.yml logs -f web
docker compose -f docker-compose.prod.yml logs -f nginx

# Last 100 lines
docker compose -f docker-compose.prod.yml logs --tail=100 web
```

### Resource Monitoring
```bash
# Container stats
docker stats

# Check disk usage
docker system df

# Cleanup unused images/volumes
docker system prune -a --volumes
```

### Health Checks
```bash
# Check all service health
docker compose -f docker-compose.prod.yml ps

# Manual health test
curl -I http://localhost/admin
curl -I http://localhost/static/
```

---

## Troubleshooting

### Services won't start
```bash
# Check compose errors
docker compose -f docker-compose.prod.yml up --no-detach

# Check logs
docker compose -f docker-compose.prod.yml logs -f

# Validate environment
docker compose -f docker-compose.prod.yml config
```

### Database connection fails
```bash
# Check if DB is running and healthy
docker compose -f docker-compose.prod.yml exec db pg_isready -U spendshelf

# Test connection directly
docker compose -f docker-compose.prod.yml exec web \
  python -c "import os; from django.db import connection; connection.ensure_connection(); print('✅ DB connected')"
```

### Static files not serving
```bash
# Collect static files again
docker compose -f docker-compose.prod.yml exec web python manage.py collectstatic --noinput --clear

# Check volume mount
docker compose -f docker-compose.prod.yml exec web ls -la /app/staticfiles/
```

### Out of memory
```bash
# Increase resource limits in docker-compose.prod.yml:
deploy:
  resources:
    limits:
      memory: 2G

# Restart services
docker compose -f docker-compose.prod.yml down
docker compose -f docker-compose.prod.yml up -d
```

---

## Cloud Deployment Examples

### AWS EC2
```bash
# 1. Launch Ubuntu 22.04 t3.medium (2 vCPU, 4GB RAM)
# 2. SSH into instance
ssh -i key.pem ubuntu@instance-ip

# 3. Install Docker
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker ubuntu

# 4. Clone repo
git clone https://github.com/yourname/spend-shelf.git
cd spend-shelf

# 5. Follow deployment steps above
```

### DigitalOcean App Platform
```yaml
# app.yaml
services:
- name: web
  github:
    branch: main
    deploy_on_push: true
    repo: yourname/spend-shelf
  build_command: docker build -t spend-shelf:prod .
  http_port: 8000
- name: db
  image:
    registry: digitalocean
    registry_type: DOCKER_HUB
    repository: postgres
    tag: "16-alpine"
  envs:
  - key: POSTGRES_DB
    value: spendshelf_prod
```

### Docker Hub Registry Push
```bash
# Tag image
docker tag spend-shelf:prod yourname/spend-shelf:latest
docker tag spend-shelf:prod yourname/spend-shelf:1.0.0

# Login and push
docker login
docker push yourname/spend-shelf:latest
docker push yourname/spend-shelf:1.0.0

# Pull on production server
docker pull yourname/spend-shelf:latest
```

---

## Security Checklist

- ✅ DJANGO_DEBUG=False in .env.production
- ✅ Strong DJANGO_SECRET_KEY (50+ chars)
- ✅ Strong DB password (32+ chars)
- ✅ HTTPS enabled with valid certificate
- ✅ ALLOWED_HOSTS configured for your domain
- ✅ CSRF_COOKIE_SECURE=True
- ✅ SESSION_COOKIE_SECURE=True
- ✅ HSTS headers enabled in nginx
- ✅ Database backups automated
- ✅ Non-root user (django) running app
- ✅ Firewall rules: allow 80, 443 only (restrict 5432 to internal)
- ✅ Regular security updates: `docker pull postgres:16-alpine && docker compose up -d`

---
