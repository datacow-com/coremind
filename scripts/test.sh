#!/usr/bin/env bash
export PYTEST_DISABLE_PLUGIN_AUTOLOAD=1
python3 -m pytest -q "$@"
