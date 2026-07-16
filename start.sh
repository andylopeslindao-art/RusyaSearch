#!/bin/bash
# ==============================================================================
# RusyaSearch 2.0 - Advanced Startup & Management Script
# ==============================================================================

DIR="$(cd "$(dirname "$0")" && pwd)"
VENV_DIR="$DIR/.venv"
LOG_FILE="$DIR/server.log"
PID_FILE="$DIR/.rusyasearch.pid"
PORT="${PORT:-8080}"
HOST="${HOST:-0.0.0.0}"

# Cores para terminal
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Obtém IP da rede Wi-Fi/local
get_wifi_ip() {
    WIFI_IP=$(hostname -I 2>/dev/null | awk '{print $1}')
    if [ -z "$WIFI_IP" ]; then
        WIFI_IP="127.0.0.1"
    fi
    echo "$WIFI_IP"
}

# Verifica e cria ambiente virtual se não existir
setup_venv() {
    if [ ! -d "$VENV_DIR" ]; then
        echo -e "${YELLOW}[!] Ambiente virtual não encontrado em $VENV_DIR. Criando...${NC}"
        python3 -m venv "$VENV_DIR"
        echo -e "${CYAN}[i] Instalando dependências...${NC}"
        "$VENV_DIR/bin/pip" install --upgrade pip -q
        "$VENV_DIR/bin/pip" install -r "$DIR/requirements.txt" -q
        if [ -f "$VENV_DIR/bin/playwright" ]; then
            echo -e "${CYAN}[i] Verificando navegadores do Playwright...${NC}"
            "$VENV_DIR/bin/playwright" install chromium -q 2>/dev/null || true
        fi
        echo -e "${GREEN}[✔] Ambiente configurado com sucesso!${NC}"
    fi
}

# Verifica se o servidor já está rodando
get_running_pid() {
    if [ -f "$PID_FILE" ]; then
        PID=$(cat "$PID_FILE")
        if ps -p "$PID" > /dev/null 2>&1; then
            echo "$PID"
            return
        else
            rm -f "$PID_FILE"
        fi
    fi
    # Tenta achar pelo nome do processo caso o arquivo PID não exista
    PID=$(pgrep -f "api.main:app" | head -n 1)
    if [ -n "$PID" ]; then
        echo "$PID" > "$PID_FILE"
        echo "$PID"
        return
    fi
    echo ""
}

show_banner() {
    local IP=$(get_wifi_ip)
    echo -e "${CYAN}================================================================${NC}"
    echo -e "${GREEN} 🚀 RUSYASEARCH 2.0 — SERVIDOR ATIVO EM TODA A REDE WI-FI${NC}"
    echo -e "${CYAN}================================================================${NC}"
    echo -e " 💻 Neste computador:          ${GREEN}http://localhost:${PORT}${NC}"
    echo -e " 📱 No Celular / Wi-Fi local:  ${GREEN}http://${IP}:${PORT}${NC}"
    echo -e " 🤖 Endpoints para Agentes:    ${GREEN}http://${IP}:${PORT}/api/v1/agent${NC}"
    echo -e " 📚 Documentação (Swagger):    ${GREEN}http://localhost:${PORT}/docs${NC}"
    echo -e "${CYAN}================================================================${NC}"
}

# Para o servidor
stop_server() {
    PID=$(get_running_pid)
    if [ -z "$PID" ]; then
        echo -e "${YELLOW}[i] RusyaSearch não está rodando.${NC}"
        return 0
    fi
    echo -e "${YELLOW}[!] Parando RusyaSearch (PID: $PID)...${NC}"
    kill "$PID" 2>/dev/null || true
    for i in {1..5}; do
        if ! ps -p "$PID" > /dev/null 2>&1; then
            break
        fi
        sleep 0.5
    done
    if ps -p "$PID" > /dev/null 2>&1; then
        echo -e "${RED}[!] Forçando parada do processo $PID...${NC}"
        kill -9 "$PID" 2>/dev/null || true
    fi
    rm -f "$PID_FILE"
    echo -e "${GREEN}[✔] RusyaSearch parado com sucesso.${NC}"
}

# Inicia no modo Background (segundo plano)
start_background() {
    PID=$(get_running_pid)
    if [ -n "$PID" ]; then
        echo -e "${YELLOW}[!] RusyaSearch já está rodando em segundo plano (PID: $PID).${NC}"
        show_banner
        return 0
    fi

    setup_venv
    echo -e "${BLUE}[i] Iniciando RusyaSearch em segundo plano (porta ${PORT})...${NC}"
    
    nohup "$VENV_DIR/bin/uvicorn" api.main:app \
        --host "$HOST" \
        --port "$PORT" \
        --app-dir "$DIR" </dev/null > "$LOG_FILE" 2>&1 &
    
    NEW_PID=$!
    echo "$NEW_PID" > "$PID_FILE"
    disown "$NEW_PID" 2>/dev/null

    echo -e "${CYAN}[i] Aguardando o servidor subir...${NC}"
    sleep 2

    if ps -p "$NEW_PID" > /dev/null 2>&1; then
        echo -e "${GREEN}[✔] RusyaSearch iniciado em background com PID $NEW_PID!${NC}"
        show_banner
        echo -e "${YELLOW}[i] Logs sendo salvos em: $LOG_FILE${NC}"
        echo -e "${YELLOW}[i] Para acompanhar os logs: ./start.sh logs${NC}"
        echo -e "${YELLOW}[i] Para parar o servidor:   ./start.sh stop${NC}"
    else
        echo -e "${RED}[✖] Falha ao iniciar o servidor. Verifique os logs abaixo:${NC}"
        tail -n 15 "$LOG_FILE"
        rm -f "$PID_FILE"
        exit 1
    fi
}

# Inicia no modo Foreground (primeiro plano)
start_foreground() {
    PID=$(get_running_pid)
    if [ -n "$PID" ]; then
        echo -e "${RED}[✖] RusyaSearch já está rodando em segundo plano (PID: $PID). Use './start.sh stop' antes se quiser rodar no terminal.${NC}"
        exit 1
    fi

    setup_venv
    show_banner
    echo -e "${YELLOW}[i] Pressione CTRL+C para parar.${NC}"
    exec "$VENV_DIR/bin/uvicorn" api.main:app --host "$HOST" --port "$PORT" --app-dir "$DIR"
}

# Mostra status
status_server() {
    PID=$(get_running_pid)
    if [ -n "$PID" ]; then
        echo -e "${GREEN}[✔] RusyaSearch está RODANDO (PID: $PID)${NC}"
        show_banner
        echo -e "${CYAN}--- Últimas 5 linhas do log ($LOG_FILE) ---${NC}"
        tail -n 5 "$LOG_FILE" 2>/dev/null || echo "(Sem logs disponíveis)"
    else
        echo -e "${RED}[✖] RusyaSearch está PARADO.${NC}"
    fi
}

# Modo de uso
case "${1:-}" in
    -b|--background|start|bg)
        start_background
        ;;
    -f|--foreground|fg)
        start_foreground
        ;;
    stop)
        stop_server
        ;;
    restart)
        stop_server
        sleep 1
        start_background
        ;;
    status)
        status_server
        ;;
    logs)
        if [ -f "$LOG_FILE" ]; then
            echo -e "${CYAN}Acompanhando logs de $LOG_FILE (CTRL+C para sair)...${NC}"
            tail -f "$LOG_FILE"
        else
            echo -e "${RED}[✖] Arquivo de log não encontrado em $LOG_FILE${NC}"
        fi
        ;;
    -h|--help|help)
        echo -e "${CYAN}RusyaSearch 2.0 - Script de Gerenciamento${NC}"
        echo -e "Uso: ${GREEN}./start.sh [comando]${NC}"
        echo ""
        echo -e "Comandos disponíveis:"
        echo -e "  ${GREEN}-b, --background, start${NC}  Inicia o servidor em segundo plano (background)"
        echo -e "  ${GREEN}-f, --foreground (ou sem)${NC}  Inicia o servidor interativo no terminal"
        echo -e "  ${GREEN}stop${NC}                     Para o servidor que está rodando em background"
        echo -e "  ${GREEN}restart${NC}                  Reinicia o servidor em background"
        echo -e "  ${GREEN}status${NC}                   Verifica o status atual do servidor"
        echo -e "  ${GREEN}logs${NC}                     Mostra e acompanha os logs em tempo real"
        ;;
    *)
        # Comportamento padrão ao rodar `./start.sh` sem argumentos no terminal: Foreground (ou avisa as opções)
        start_foreground
        ;;
esac
