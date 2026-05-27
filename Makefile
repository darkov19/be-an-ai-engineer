.PHONY: dev test db-up db-down setup

setup:
	npm install
	cd frontend && npm install
	cd backend && python3 -m venv venv && venv/bin/pip install -r requirements.txt

dev:
	npm run dev

test:
	npm run test
	npm run lint

db-up:
	docker-compose up -d

db-down:
	docker-compose down
