#!/bin/bash
# RusyaSearch 2.0 - Startup script
# Roda em 0.0.0.0 permitindo acesso de toda a rede Wi-Fi local

set -e

DIR="$(cd "$(dirname "$0")" && pwd)"
VENV_DIR="$DIR/.venv"

if [ ! -d "$VENV_DIR" ]; then
    echo "Criando ambiente virtual..."
    python3 -m venv "$VENV_DIR"
    "$VENV_DIR/bin/pip" install --upgrade pip -q
    "$VENV_DIR/bin/pip" install -r "$DIR/requirements.txt" -q
fi

WIFI_IP=$(hostname -I 2>/dev/null | awk '{print $1}')
if [ -z "$WIFI_IP" ]; then
    WIFI_IP="Seu_IP_Local"
fi

echo "================================================================"
echo " 🚀 RUSYASEARCH 2.0 — SERVIDOR ATIVO EM TODA A REDE WI-FI"
echo "================================================================"
echo " 💻 Neste computador:          http://localhost:8080"
echo " 📱 No Celular / Wi-Fi local:  http://$WIFI_IP:8080"
echo " 🤖 Endpoints para Agentes:    http://$WIFI_IP:8080/api/v1/agent"
echo "================================================================"

exec "$VENV_DIR/bin/uvicorn" api.main:app --host 0.0.0.0 --port 8080 --app-dir "$DIR"
