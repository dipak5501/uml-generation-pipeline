.PHONY: install install-java setup api ui run demo test smoke dataset training-corpus finetune finetune-quick finetune-prepare

install:
	python3 -m venv .venv
	. .venv/bin/activate && pip install -U pip && pip install -r requirements.txt
	. .venv/bin/activate && pip install -q -r requirements-finetune.txt || true
	cp -n .env.example .env || true
	mkdir -p data output tools models
	@test -f tools/plantuml.jar || curl -fsSL -o tools/plantuml.jar https://github.com/plantuml/plantuml/releases/download/v1.2024.7/plantuml-1.2024.7.jar

install-java:
	chmod +x scripts/install_java.sh && ./scripts/install_java.sh

setup: install
	. .venv/bin/activate && PYTHONPATH=. python scripts/build_training_corpus.py --target 8000 || true
	@test -d models/uml-plantuml-lora || echo "Run: make finetune-quick (optional, ~800 iters)"

api:
	. .venv/bin/activate && set -a && [ -f .env ] && . ./.env; set +a && PYTHONPATH=. uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

ui:
	. .venv/bin/activate && set -a && [ -f .env ] && . ./.env; set +a && PYTHONPATH=. streamlit run ui/streamlit_app.py --server.port 8501

run:
	./scripts/run_local.sh

demo:
	. .venv/bin/activate && PYTHONPATH=. MOCK_PROVIDERS=true python scripts/demo_generate.py -n 1

dataset:
	. .venv/bin/activate && PYTHONPATH=. MOCK_PROVIDERS=true python scripts/generate_dataset.py -n 50

training-corpus:
	. .venv/bin/activate && PYTHONPATH=. python scripts/build_training_corpus.py --target 8000

finetune-prepare:
	. .venv/bin/activate && PYTHONPATH=. python scripts/prepare_finetune_data.py

finetune:
	. .venv/bin/activate && pip install -q -r requirements-finetune.txt && PYTHONPATH=. python scripts/finetune_plantuml.py --iters 2000 --resume

finetune-quick:
	. .venv/bin/activate && pip install -q -r requirements-finetune.txt && PYTHONPATH=. python scripts/finetune_plantuml.py --quick

test:
	. .venv/bin/activate && PYTHONPATH=. MOCK_PROVIDERS=true USE_FINETUNED_CODE=false pytest -q

smoke:
	. .venv/bin/activate && PYTHONPATH=. python scripts/smoke_test.py

docker-up:
	docker compose up --build

docker-down:
	docker compose down
