#!/usr/bin/env bash
set -euo pipefail

if [[ -z "${LLAMA_CPP_DIR:-}" ]]; then
    echo "ERROR: LLAMA_CPP_DIR is not set."
    echo "Set LLAMA_CPP_DIR before starting the standalone llm compose stack."
    exit 1
fi

if [[ ! -d "$LLAMA_CPP_DIR" ]]; then
    echo "ERROR: LLAMA_CPP_DIR does not exist: $LLAMA_CPP_DIR"
    exit 1
fi

if [[ ! -x "$LLAMA_CPP_DIR/llama-server" ]]; then
    echo "ERROR: llama-server not found/executable at: $LLAMA_CPP_DIR/llama-server"
    exit 1
fi

echo "OK: standalone llm compose environment preflight passed"
echo "LLAMA_CPP_DIR=$LLAMA_CPP_DIR"
