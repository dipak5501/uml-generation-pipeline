.PHONY: install install-java setup api ui run demo test smoke dataset training-corpus finetune finetune-quick finetune-cuda finetune-prepare train-real

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
	@test -d models/uml-plantuml-lora || echo "Run: make finetune-quick (Apple) or make finetune-cuda (NVIDIA)"

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
	. .venv/bin/activate && PYTHONPATH=. python scripts/build_training_corpus.py --target 8000 --include-flowchart

scenario-corpus:
	. .venv/bin/activate && PYTHONPATH=. python scripts/build_scenario_code_corpus.py --scenarios 1000 --codes 1000
	. .venv/bin/activate && PYTHONPATH=. python scripts/prepare_finetune_data.py --input data/training/uml_training_supplement_merged.parquet --prefer-accepted

eval-batch:
	. .venv/bin/activate && PYTHONPATH=. python scripts/eval_scenario_code_batch.py --all --out data/eval/batch_report.json

eval-smoke:
	. .venv/bin/activate && PYTHONPATH=. python scripts/eval_scenario_code_batch.py --limit 100 --out data/eval/batch_report_smoke100.json

finetune-prepare:
	. .venv/bin/activate && PYTHONPATH=. python scripts/prepare_finetune_data.py \
		--input data/training/uml_training_supplement_merged.parquet --prefer-accepted

finetune:
	. .venv/bin/activate && pip install -q -r requirements-finetune.txt && PYTHONPATH=. python scripts/finetune_plantuml.py --iters 2000 --resume

finetune-quick:
	. .venv/bin/activate && pip install -q -r requirements-finetune.txt && PYTHONPATH=. python scripts/finetune_plantuml.py --quick

finetune-cuda:
	. .venv/bin/activate && pip install -q -r requirements-finetune-cuda.txt && PYTHONPATH=. python scripts/finetune_plantuml_cuda.py --iters 2000 --resume

# Full real-data train path: HF corpus → JSONL → LoRA (MLX on Apple, PEFT on NVIDIA)
train-real:
	@test -f data/training/uml_training_8000.parquet || (echo "Building 8k HF corpus..." && PYTHONPATH=. python scripts/build_training_corpus.py --target 8000 --include-flowchart)
	@test -f data/training/uml_training_supplement_merged.parquet || (echo "Building supplement..." && $(MAKE) scenario-corpus)
	$(MAKE) finetune-prepare
	@backend=$$(PYTHONPATH=. python scripts/detect_compute.py || true); \
	if [ "$$backend" = "nvidia-cuda" ]; then \
	  echo "CUDA GPU detected — PEFT LoRA (not mlx_lm)"; \
	  . .venv/bin/activate && pip install -q -r requirements-finetune-cuda.txt && PYTHONPATH=. python scripts/finetune_plantuml_cuda.py --iters 3000 --resume --skip-prepare; \
	  echo "Enable in .env: USE_FINETUNED_CODE=true FINETUNED_BASE_MODEL=Qwen/Qwen2.5-0.5B-Instruct FINETUNED_ADAPTER_PATH=models/uml-plantuml-lora"; \
	else \
	  echo "Apple/MLX path (no NVIDIA)"; \
	  . .venv/bin/activate && pip install -q -r requirements-finetune.txt && PYTHONPATH=. python scripts/finetune_plantuml.py --iters 3000 --resume --skip-prepare; \
	  echo "Enable in .env: USE_FINETUNED_CODE=true FINETUNED_ADAPTER_PATH=models/uml-plantuml-lora"; \
	fi
	@echo "Then restart: ./scripts/run_local.sh"
test:
	. .venv/bin/activate && PYTHONPATH=. MOCK_PROVIDERS=true USE_FINETUNED_CODE=false pytest -q

smoke:
	. .venv/bin/activate && PYTHONPATH=. python scripts/smoke_test.py

docker-up:
	docker compose up --build

docker-down:
	docker compose down
