#!/bin/bash
set -e

echo "🚀 Spend Shelf Production Deployment Script"
echo "=============================================="

# Step 1: Validate environment
echo "📋 Step 1: Validating production environment..."
if [ ! -f .env.production ]; then
    echo "❌ .env.production not found. Copy from .env.production template and configure."
    exit 1
fi

if [ ! -f nginx.conf ]; then
    echo "❌ nginx.conf not found."
    exit 1
fi

echo "✅ Environment files present"

# Step 2: Generate Django Secret Key
echo ""
echo "🔐 Step 2: Generate secure Django secret key..."
if grep -q "change-me" .env.production; then
    echo "⚠️  WARNING: .env.production contains 'change-me' values. Please update with real values:"
    echo "   - DJANGO_SECRET_KEY (generate: python -c 'from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())')"
    echo "   - DB_PASSWORD (strong random password)"
    echo "   - DJANGO_ALLOWED_HOSTS (your domain)"
    read -p "Continue anyway? (y/N) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# Step 3: Create SSL directory
echo ""
echo "🔒 Step 3: Create SSL directory..."
mkdir -p ssl
if [ ! -f ssl/cert.pem ] || [ ! -f ssl/key.pem ]; then
    echo "⚠️  SSL certificates not found in ./ssl/"
    echo "   For Let's Encrypt + Certbot:"
    echo "   certbot certonly --standalone -d example.com -d www.example.com"
    echo "   Then copy cert.pem and privkey.pem to ./ssl/"
    echo ""
    echo "   For self-signed (testing only):"
    echo "   openssl req -x509 -newkey rsa:4096 -nodes -out ssl/cert.pem -keyout ssl/key.pem -days 365"
fi

# Step 4: Build and validate
echo ""
echo "🏗️  Step 4: Building Docker image..."
docker compose -f docker-compose.prod.yml build --no-cache

# Step 5: Prepare database and migrations
echo ""
echo "💾 Step 5: Starting services with migrations..."
docker compose -f docker-compose.prod.yml up -d db
sleep 5

echo "Waiting for database to be ready..."
docker compose -f docker-compose.prod.yml exec db pg_isready -U spendshelf || sleep 5

# Step 6: Run migrations
echo ""
echo "📦 Step 6: Running Django migrations..."
docker compose -f docker-compose.prod.yml run --rm web python manage.py migrate --noinput

# Step 7: Create superuser (optional)
echo ""
echo "👤 Step 7: Create Django superuser (optional)"
read -p "Create superuser now? (y/N) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    docker compose -f docker-compose.prod.yml run --rm web python manage.py createsuperuser
fi

# Step 8: Start all services
echo ""
echo "🚀 Step 8: Starting all services..."
docker compose -f docker-compose.prod.yml up -d

sleep 3
echo ""
echo "✅ Deployment Complete!"
echo ""
echo "📊 Service Status:"
docker compose -f docker-compose.prod.yml ps
echo ""
echo "🌐 Access points:"
echo "   Web: http://localhost (or your domain)"
echo "   API: http://localhost/api"
echo "   Admin: http://localhost/admin"
echo ""
echo "📝 Next steps:"
echo "   1. Check logs: docker compose -f docker-compose.prod.yml logs -f web"
echo "   2. Configure SSL: Update nginx.conf with your certificate paths"
echo "   3. Enable HTTPS redirect in nginx.conf"
echo "   4. Monitor with: docker stats"
echo "   5. Backup database: docker compose -f docker-compose.prod.yml exec db pg_dump -U spendshelf spendshelf_prod > backup.sql"
