.PHONY: install api ui demo test docker-up docker-down lint

install:
	python3 -m venv .venv
	. .venv/bin/activate && pip install -U pip && pip install -r requirements.txt
	cp -n .env.example .env || true
	mkdir -p data output tools

api:
	. .venv/bin/activate && PYTHONPATH=. uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

ui:
	. .venv/bin/activate && PYTHONPATH=. streamlit run ui/streamlit_app.py --server.port 8501

demo:
	. .venv/bin/activate && PYTHONPATH=. MOCK_PROVIDERS=true python scripts/demo_generate.py -n 1

test:
	. .venv/bin/activate && PYTHONPATH=. MOCK_PROVIDERS=true pytest -q

docker-up:
	docker compose up --build

docker-down:
	docker compose down
