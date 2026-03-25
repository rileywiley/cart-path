.PHONY: up down dev logs restart status rebuild init prod ssl test lan-ip

# ── Development ──────────────────────────────────────────────────────

# Start all backend services (OSRM, API, Nginx)
up:
	docker compose -f deploy/docker-compose.yml up -d --build

# Stop all services
down:
	docker compose -f deploy/docker-compose.yml down

# Start backend + client dev server
dev: up
	cd client && npm run dev

# View backend logs
logs:
	docker compose -f deploy/docker-compose.yml logs -f

# Restart backend services
restart:
	docker compose -f deploy/docker-compose.yml restart

# Re-classify data, rebuild OSRM graph, and restart services
rebuild:
	python3 pipeline/classify_speeds.py --verbose
	python3 pipeline/classify_surfaces.py --verbose
	python3 pipeline/build_graph.py --verbose
	bash routing/scripts/build_osrm.sh
	docker compose -f deploy/docker-compose.yml restart

# Show service status
status:
	docker compose -f deploy/docker-compose.yml ps
	@echo ""
	@curl -s http://localhost:8000/api/health | python3 -m json.tool 2>/dev/null || echo "API not responding"

# Run tests
test:
	python3 -m pytest pipeline/tests/ routing/api/tests/ -v

# ── Deployment ───────────────────────────────────────────────────────

# First-deploy: run data pipeline + build OSRM graph
init:
	bash deploy/init.sh

# Production build and start
prod:
	docker compose -f deploy/docker-compose.yml up -d --build
	@echo ""
	@echo "CartPath is running. Check status with: make status"

# Show LAN IP for accessing from other devices
lan-ip:
	@echo "Your LAN IP:"
	@ipconfig getifaddr en0 2>/dev/null || ip route get 1 2>/dev/null | awk '{print $$7; exit}' || hostname -I 2>/dev/null | awk '{print $$1}'
	@echo ""
	@echo "Access CartPath from other devices at: http://$$(ipconfig getifaddr en0 2>/dev/null || hostname -I 2>/dev/null | awk '{print $$1}')"

# SSL setup instructions
ssl:
	@echo "=== SSL Setup with Let's Encrypt ==="
	@echo ""
	@echo "1. Make sure your domain points to this server's IP"
	@echo "2. Install certbot:"
	@echo "   - macOS:  brew install certbot"
	@echo "   - Linux:  sudo apt install certbot"
	@echo "3. Run certbot:"
	@echo "   sudo certbot certonly --webroot -w /var/www/certbot -d YOUR_DOMAIN"
	@echo "4. Edit deploy/nginx.conf:"
	@echo "   - Uncomment the HTTPS server block"
	@echo "   - Replace 'cartpath.app' with your domain"
	@echo "   - Add 'return 301 https://\$$host\$$request_uri;' to the HTTP block"
	@echo "5. Restart: make restart"
