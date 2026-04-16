VENV := .venv
PYTHON := $(VENV)/bin/python
PIP := $(VENV)/bin/pip
BLACK := $(VENV)/bin/black
ISORT := $(VENV)/bin/isort
FLAKE8 := $(VENV)/bin/flake8
BANDIT := $(VENV)/bin/bandit
DETECT_SECRETS := $(VENV)/bin/detect-secrets
RCC ?= rcc
DESIGNER ?= /opt/homebrew/bin/designer
PLUGIN_NAME := AtlasPress
DIST_DIR := dist
PACKAGE_DIR := $(DIST_DIR)/$(PLUGIN_NAME)
ZIP_PATH := $(DIST_DIR)/$(PLUGIN_NAME).zip
RSYNC := rsync
RESOURCES_QRC := resources.qrc
RESOURCES_PY := resources.py

PACKAGE_EXCLUDES := \
	--exclude ".DS_Store" \
	--exclude "__MACOSX" \
	--exclude "__pycache__" \
	--exclude "*.pyc" \
	--exclude "*.pyo" \
	--exclude ".git" \
	--exclude ".github" \
	--exclude ".gitignore" \
	--exclude ".venv" \
	--exclude ".venv-*" \
	--exclude ".vscode" \
	--exclude ".pytest_cache" \
	--exclude ".mypy_cache" \
	--exclude ".ruff_cache" \
	--exclude ".idea" \
	--exclude "dist" \
	--exclude "build" \
	--exclude "tests" \
	--exclude "Makefile" \
	--exclude "requirements-dev.txt" \
	--exclude "pyproject.toml" \
	--exclude ".flake8" \
	--exclude ".env" \
	--exclude ".python-version"

.PHONY: help install-dev format lint scan check designer resources clean-dist package

help:
	@echo "Available targets:"
	@echo "  make install-dev  Install development dependencies into .venv"
	@echo "  make format       Sort imports and format Python code"
	@echo "  make lint         Run Flake8 checks"
	@echo "  make scan         Run Bandit and detect-secrets"
	@echo "  make check        Run format, lint, and scan steps"
	@echo "  make designer     Open Qt Designer"
	@echo "  make resources    Compile Qt resources into resources.py"
	@echo "  make package      Build a QGIS plugin zip in dist/"
	@echo "  make clean-dist   Remove built package artifacts"

install-dev:
	$(PIP) install -r requirements-dev.txt

format:
	$(ISORT) .
	$(BLACK) .

lint:
	$(FLAKE8) .

scan:
	$(BANDIT) -r . -x ./.venv,./.venv-*,./dist,./build,./.git,./.vscode
	$(DETECT_SECRETS) scan --exclude-files '(^\.venv/|^dist/|^build/|^\.git/|^\.vscode/|\.DS_Store$$)'

check: format lint scan

designer:
	$(DESIGNER)

resources: $(RESOURCES_PY)

$(RESOURCES_PY): $(RESOURCES_QRC)
	$(RCC) -g python -o $(RESOURCES_PY) $(RESOURCES_QRC)

clean-dist:
	rm -rf $(DIST_DIR)

package: clean-dist resources
	mkdir -p $(PACKAGE_DIR)
	$(RSYNC) -a ./ $(PACKAGE_DIR)/ $(PACKAGE_EXCLUDES)
	cd $(DIST_DIR) && zip -r $(PLUGIN_NAME).zip $(PLUGIN_NAME) \
		-x "*.DS_Store" \
		-x "*__MACOSX*" \
		-x "*__pycache__*" \
		-x "*.pyc" \
		-x "*.pyo"
	@echo "Created $(ZIP_PATH)"
