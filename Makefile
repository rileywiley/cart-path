.PHONY: up down dev logs restart status rebuild

# Start all backend services (OSRM, API, Nginx)
up:
	docker compose -f deploy/docker-compose.yml up -d

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
