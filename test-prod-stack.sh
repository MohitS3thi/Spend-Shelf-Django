#!/bin/bash
# Quick local testing of production stack before cloud deployment

echo "🧪 Testing Production Stack Locally"
echo "===================================="

# Set test environment variables
export DB_PASSWORD=test-password-12345
export DJANGO_SECRET_KEY=test-secret-key-for-local-testing-min-50-chars
export DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1

echo "✅ Test environment variables set"
echo ""

# Step 1: Build image
echo "🏗️  Building Docker image..."
docker compose -f docker-compose.prod.yml build || exit 1
echo "✅ Build successful"
echo ""

# Step 2: Start services
echo "🚀 Starting services..."
docker compose -f docker-compose.prod.yml up -d || exit 1
sleep 5
echo "✅ Services started"
echo ""

# Step 3: Check service status
echo "📊 Service Status:"
docker compose -f docker-compose.prod.yml ps
echo ""

# Step 4: Verify database health
echo "🔍 Checking database health..."
docker compose -f docker-compose.prod.yml exec db pg_isready -U spendshelf && echo "✅ Database ready" || echo "❌ Database not ready"
echo ""

# Step 5: Test web service
echo "🌐 Testing web service..."
sleep 3
curl -s -o /dev/null -w "HTTP Status: %{http_code}\n" http://localhost/ && echo "✅ Web service responding" || echo "❌ Web service not responding"
echo ""

# Step 6: View logs
echo "📋 Application Logs:"
echo "-------------------"
docker compose -f docker-compose.prod.yml logs web --tail=20
echo ""

# Step 7: Resource usage
echo "💾 Resource Usage:"
docker stats --no-stream --format "table {{.Container}}\t{{.CPUPerc}}\t{{.MemUsage}}"
echo ""

# Step 8: Cleanup option
echo "🧹 Cleanup Commands:"
echo "-------------------"
echo "Stop services:  docker compose -f docker-compose.prod.yml down"
echo "Remove volumes: docker compose -f docker-compose.prod.yml down -v"
echo "View logs:      docker compose -f docker-compose.prod.yml logs -f web"
echo ""

echo "✅ Test complete! Services available at:"
echo "   🌐 Web:   http://localhost"
echo "   📊 Admin: http://localhost/admin"
echo "   📦 DB:    localhost:5432"
