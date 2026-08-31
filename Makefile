.PHONY: install install-java setup api ui run demo test smoke dataset training-corpus training-corpus-50k download-all-corpora finetune finetune-quick finetune-cuda finetune-prepare train-real train-50k train-100k train-source10k train-source30k

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

training-corpus-50k:
	. .venv/bin/activate && PYTHONPATH=. python scripts/build_training_corpus.py --target 50000 --include-flowchart

download-all-corpora:
	. .venv/bin/activate && PYTHONPATH=. python scripts/download_all_corpora.py
	. .venv/bin/activate && PYTHONPATH=. python scripts/download_datasets.py --include-gated --skip-errors || true

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

# ≥50k web/HF train path (downloads + corpus + LoRA via Open MPI-safe runner)
train-50k:
	. .venv/bin/activate && pip install -q -r requirements-finetune.txt
	. .venv/bin/activate && PYTHONPATH=. python scripts/download_all_corpora.py
	. .venv/bin/activate && PYTHONPATH=. python scripts/download_datasets.py --include-gated --skip-errors || true
	. .venv/bin/activate && PYTHONPATH=. python scripts/build_training_corpus.py --target 50000 --include-flowchart
	. .venv/bin/activate && PYTHONPATH=. python scripts/build_scenario_code_corpus.py --scenarios 5000 --codes 5000
	. .venv/bin/activate && PYTHONPATH=. python scripts/prepare_finetune_data.py --input data/training/uml_training_supplement_merged.parquet --prefer-accepted --valid-ratio 0.02 --test-ratio 0.02
	bash scripts/run_finetune_resilient.sh
	@echo "When training finishes: swap models/uml-plantuml-lora-50k → models/uml-plantuml-lora and restart API LaunchAgent"
	@echo "Enable in .env: USE_FINETUNED_CODE=true FINETUNED_ADAPTER_PATH=models/uml-plantuml-lora"

# ≥100k combined train path (50k source-code web + existing supplement)
train-100k:
	. .venv/bin/activate && pip install -q -r requirements-finetune.txt
	. .venv/bin/activate && PYTHONPATH=. python scripts/download_all_corpora.py --skip-full-stack
	env -i HOME="$$HOME" PATH="$$PWD/.venv/bin:/usr/bin:/bin" PYTHONPATH=. python scripts/build_source_code_corpus.py --target 50000
	env -i HOME="$$HOME" PATH="$$PWD/.venv/bin:/usr/bin:/bin" PYTHONPATH=. python scripts/prepare_finetune_data.py --input data/training/uml_training_combined_100k.parquet --prefer-accepted --valid-ratio 0.02 --test-ratio 0.02
	mkdir -p models/uml-plantuml-lora-100k
	@test -f models/uml-plantuml-lora-100k/adapters.safetensors || cp models/uml-plantuml-lora-50k/adapters.safetensors models/uml-plantuml-lora-100k/ 2>/dev/null || true
	ADAPTER_PATH=models/uml-plantuml-lora-100k ITERS=18000 LOG=data/training/finetune_100k.log bash scripts/run_finetune_resilient.sh
	@echo "Update .env: FINETUNED_ADAPTER_PATH=models/uml-plantuml-lora-100k && restart API"

# ≥200k combined train path (100k v2 web/synthetic + existing 102k combined)
train-200k:
	. .venv/bin/activate && pip install -q -r requirements-finetune.txt
	. .venv/bin/activate && PYTHONPATH=. python scripts/download_all_corpora.py --skip-full-stack
	env -i HOME="$$HOME" PATH="$$PWD/.venv/bin:/usr/bin:/bin" PYTHONPATH=. python scripts/build_corpus_v2_100k.py --target 100000
	env -i HOME="$$HOME" PATH="$$PWD/.venv/bin:/usr/bin:/bin" PYTHONPATH=. python scripts/prepare_finetune_data.py --input data/training/uml_training_combined_200k.parquet --prefer-accepted --valid-ratio 0.02 --test-ratio 0.02
	mkdir -p models/uml-plantuml-lora-200k
	@test -f models/uml-plantuml-lora-200k/adapters.safetensors || cp models/uml-plantuml-lora-100k/adapters.safetensors models/uml-plantuml-lora-200k/ 2>/dev/null || true
	ADAPTER_PATH=models/uml-plantuml-lora-200k ITERS=20000 LOG=data/training/finetune_200k.log bash scripts/run_finetune_resilient.sh
	@echo "Update .env: FINETUNED_ADAPTER_PATH=models/uml-plantuml-lora-200k && restart API"

# ≥10k Java/Python/C source-code LoRA fine-tune (warm-start from 200k adapter)
train-source10k:
	. .venv/bin/activate && pip install -q -r requirements-finetune.txt
	env -i HOME="$$HOME" PATH="$$PWD/.venv/bin:/usr/bin:/bin" PYTHONPATH=. python scripts/build_source_code_corpus.py --target 10000 --languages java,python,c
	env -i HOME="$$HOME" PATH="$$PWD/.venv/bin:/usr/bin:/bin" PYTHONPATH=. python scripts/prepare_finetune_data.py --input data/training/uml_source_code_10k_jpc.parquet --valid-ratio 0.05 --test-ratio 0.05
	mkdir -p models/uml-plantuml-lora-source10k
	@test -f models/uml-plantuml-lora-source10k/adapters.safetensors || cp models/uml-plantuml-lora-200k/adapters.safetensors models/uml-plantuml-lora-source10k/ 2>/dev/null || true
	ADAPTER_PATH=models/uml-plantuml-lora-source10k ITERS=4000 BATCH_SIZE=1 SAVE_EVERY=100 LOG=data/training/finetune_source10k.log bash scripts/run_finetune_resilient.sh
	@echo "Update .env: FINETUNED_ADAPTER_PATH=models/uml-plantuml-lora-source10k && restart API"

# ≥10k Java/Python/C EACH (30k+) source-code LoRA fine-tune (warm-start from 200k adapter)
train-source30k:
	. .venv/bin/activate && pip install -q -r requirements-finetune.txt
	env -i HOME="$$HOME" PATH="$$PWD/.venv/bin:/usr/bin:/bin" PYTHONPATH=. python scripts/build_language_source_corpus.py --per-language 10000 --languages java,python,c
	env -i HOME="$$HOME" PATH="$$PWD/.venv/bin:/usr/bin:/bin" PYTHONPATH=. python scripts/prepare_finetune_data.py --input data/training/uml_training_combined_sourcecode_30k.parquet --valid-ratio 0.03 --test-ratio 0.02
	mkdir -p models/uml-plantuml-lora-sourcecode-30k
	@test -f models/uml-plantuml-lora-sourcecode-30k/adapters.safetensors || cp models/uml-plantuml-lora-200k/adapters.safetensors models/uml-plantuml-lora-sourcecode-30k/ 2>/dev/null || true
	ADAPTER_PATH=models/uml-plantuml-lora-sourcecode-30k ITERS=6000 LOG=data/training/finetune_sourcecode_30k.log bash scripts/run_finetune_resilient.sh
	@echo "Update .env: FINETUNED_ADAPTER_PATH=models/uml-plantuml-lora-sourcecode-30k && restart API"

# Autonomous: wait for 100k → deploy → collect v2 → train 200k
pipeline-after-100k:
	nohup bash scripts/pipeline_after_100k.sh >> data/training/pipeline_after_100k.log 2>&1 &
	@echo "Supervisor PID $$! — tail -f data/training/pipeline_after_100k.log"

test:
	@JDK=$$(find tools -path '*/jdk-*/Contents/Home' -type d 2>/dev/null | head -1); \
	. .venv/bin/activate && \
	JAVA_HOME="$${JAVA_HOME:-$$JDK}" \
	PYTHONPATH=. MOCK_PROVIDERS=true USE_FINETUNED_CODE=false pytest -q

smoke:
	. .venv/bin/activate && PYTHONPATH=. python scripts/smoke_test.py

docker-up:
	docker compose up --build

docker-down:
	docker compose down
