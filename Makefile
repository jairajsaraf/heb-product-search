# Makefile
# --------
# Usage:
#   make                       # default goal: validate the real submission
#   make validate TEAM=team-git-em
#   make evaluate TEAM=<team whose submission covers the train queries>
#   make info
#   make version
#   make install               # pip installs, same lines as CI
.DEFAULT_GOAL := validate

# team-git-em is the only real submission; it covers the 191 test queries,
# so validate uses the test queries and evaluate cannot score it locally (no test labels).
TEAM ?= team-git-em
OUT_DIR ?= .
RUN ?=
TAMU25 ?= $(RUN) python -m tamu25.cli.main
SUBMISSION = teams/$(TEAM)/submission.json
PRODUCTS   = data/products.json
QSYNTH     ?= data/queries_synth_test.json
LSYNTH     = data/labels_synth_train.json
.PHONY: install validate evaluate all clean info version lint unittest

lint: ## Lint and reformat the code
	@$(RUN) python -m autoflake tamu25 tests scripts --remove-all-unused-imports --recursive --remove-unused-variables --in-place --exclude=__init__.py
	@$(RUN) python -m black tamu25 tests scripts --line-length 120 -q
	@$(RUN) python -m isort tamu25 tests scripts -q

unittest: ## Run unit-tests
	@$(RUN) python -m pytest -s -v tests

install:
	pip install torch==2.15.0 --index-url https://download.pytorch.org/whl/cpu
	pip install -r requirements.txt
	pip install -r requirements-api.txt

validate:
	$(TAMU25) validate \
		--submission $(SUBMISSION) \
		--products $(PRODUCTS) \
		--queries_synth $(QSYNTH) \
		--team $(TEAM) \
		--out $(OUT_DIR)/validation_report.json
evaluate:
	$(TAMU25) evaluate \
		--submission $(SUBMISSION) \
		--labels_synth $(LSYNTH) \
		--team $(TEAM) \
		--out $(OUT_DIR)/score_report.json
all: validate evaluate

clean:
	rm -f $(OUT_DIR)/validation_report.json $(OUT_DIR)/score_report.json

info:
	$(TAMU25) info

version:
	$(TAMU25) version
