PY=python

test:
	$(PY) -m pytest -q tests

smoke:
	PYTHONPATH=src $(PY) -m revres.run --backend scripted --seeds 3 --out results/smoke

experiments:
	bash experiments/01_main_grid/run.sh
	bash experiments/02_ablation_early_revoke/run.sh
	bash experiments/03_ablation_strict_notice/run.sh
	bash experiments/04_ablation_no_citation/run.sh
	bash experiments/05_ablation_no_second_source/run.sh

analysis:
	bash experiments/analysis/run.sh

deck:
	cd deck && $(PY) build_deck.py

.PHONY: test smoke experiments analysis deck
