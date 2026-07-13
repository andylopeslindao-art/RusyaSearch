# RusyaSearch 2.0 🌐 — AI Agent Search & Stealth Browsing Suite

[![Python 3.11+](https://img.shields.io/badge/Python-3.11%2B-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110%2B-009688.svg)](https://fastapi.tiangolo.com/)
[![MCP Ready](https://img.shields.io/badge/MCP-Server%20Enabled-8A2BE2.svg)](https://modelcontextprotocol.io/)
[![Playwright Stealth](https://img.shields.io/badge/Playwright-Tri--Hybrid%20Engine-FF6F00.svg)](https://playwright.dev/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

**RusyaSearch 2.0** é uma suíte open-source de busca web, navegação anti-bot e extração de Markdown otimizada especificamente para **Agentes de IA autônomos** (Claude Code, Hermes Agent, Cursor, Aider, OpenCode) e desenvolvedores.

> **Por que o RusyaSearch existe?**  
> A maioria dos agentes de IA falha ao tentar buscar na internet por três motivos:
> 1. Requisições HTTP normais caem em **CAPTCHAs e bloqueios Cloudflare/Turnstile**.
> 2. Páginas HTML pesadas gastam todo o **orçamento de tokens** do modelo.
> 3. Buscadores tradicionais não entregam **links diretos de imagens (`.png`, `.jpg`, `.svg`)** quando o agente está construindo uma interface web.
>
> O RusyaSearch resolve tudo isso rodando localmente com uma API REST limpa e um **servidor MCP (Model Context Protocol)** nativo.

---

## 🔥 Principais Funcionalidades

### 1. Motor Tri-Híbrido de Navegação Anti-Bot
O `AgentBrowser` não depende de um único método. Ele usa uma estratégia em 3 camadas:
- **Tier 1 (HTTPx Rápido):** Navegação assíncrona veloz com rotação de User-Agents modernos.
- **Tier 2 (Playwright Chromium Stealth):** Headless browser real que executa JavaScript e burla proteções anti-bot, Cloudflare e Turnstile.
- **Tier 3 (Jina Mirror Fallback):** Espelho de leitura anti-paywall para garantir 100% de taxa de sucesso na extração.

### 2. Busca Web & Imagens Diretas via Brave Search
- **Web Search sem CAPTCHA:** Resultados orgânicos limpos combinando **Brave Search** + **DuckDuckGo SafeSearch OFF**.
- **Imagens Prontas para `<img src="...">`:** O `ImageSearcher` decodifica a CDN do Brave em tempo real e retorna a **URL direta do arquivo (`.png`, `.jpg`, `.webp`, `.svg`)**, resolução e thumbnail. Agentes IA podem inserir imagens reais no código HTML/CSS na hora.

### 3. Extração de Markdown Limpo (.md)
Converte qualquer página da internet em Markdown sinteticamente limpo, removendo anúncios, scripts, modais de cookies e navegação redundante para economizar tokens do LLM.

### 4. Suporte Completo a Paginação & Filtros
- Paginação interativa na Interface Web (`Página 1`, `2`, `3...`).
- Suporte a filtros por domínio (`site:github.com`), intervalo de datas (`d`, `w`, `m`, `y`) e categoria (Web, Notícias, PDFs, ArXiv, GitHub, StackOverflow).

---

## 🔌 Integração via MCP (Model Context Protocol)

O projeto inclui o servidor `mcp_server.py` pronto para ser plugado no **Claude Code**, **Hermes Agent** ou **Cursor**.

### Configuração no Hermes Agent (`~/.hermes/config.yaml`)
```yaml
mcp_servers:
  rusyasearch:
    command: "/caminho/para/RusyaSearch/.venv/bin/python3"
    args: ["/caminho/para/RusyaSearch/mcp_server.py"]
    timeout: 180
    connect_timeout: 30
```

### Configuração no Claude Code / Claude Desktop (`claude_desktop_config.json`)
```json
{
  "mcpServers": {
    "rusyasearch": {
      "command": "/caminho/para/RusyaSearch/.venv/bin/python3",
      "args": ["/caminho/para/RusyaSearch/mcp_server.py"]
    }
  }
}
```

### Ferramentas MCP Expostas
- `rusya_search(query, sources, max_results, page)` — Busca web meta-search.
- `rusya_search_images(query, limit)` — Links diretos de arquivos de imagem (`.png`, `.jpg`).
- `rusya_browse(url, format, js_render)` — Acessa URLs com bypass anti-bot e devolve Markdown.
- `rusya_extract(url, mode)` — Extrai conteúdo estruturado/tabelas em MD.
- `rusya_research(topic, depth)` — Relatório de pesquisa profunda automatizada.
- `rusya_crawl(start_url, max_pages)` — Indexador recursivo de sites para busca local.

---

## 🚀 Instalação e Uso Local

### 1. Clonar e Instalar Dependências
```bash
git clone https://github.com/SEU-USUARIO/RusyaSearch.git
cd RusyaSearch

# Criar ambiente virtual
python3 -m venv .venv
source .venv/bin/activate

# Instalar dependências e binários do Playwright
pip install -r requirements.txt
playwright install chromium
```

### 2. Iniciar o Servidor
```bash
./start.sh
```
Ou manualmente via Uvicorn (escutando em toda a rede Wi-Fi local `0.0.0.0:8080`):
```bash
.venv/bin/uvicorn api.main:app --host 0.0.0.0 --port 8080
```

- **Painel Web:** Abra `http://localhost:8080` (ou IP da sua máquina na rede local) no navegador.
- **Documentação Interativa (Swagger):** Acesse `http://localhost:8080/docs`.

---

## 🛠️ Exemplos de API REST

```bash
# 1. Pesquisa Web (Página 1)
curl -G "http://localhost:8080/api/v1/agent/search" \
  --data-urlencode "query=inteligencia artificial" \
  --data-urlencode "sources=web"

# 2. Pesquisar Imagens Diretas (.png/.jpg)
curl -G "http://localhost:8080/api/v1/agent/search" \
  --data-urlencode "query=python logo transparent png" \
  --data-urlencode "sources=images"

# 3. Navegar em Site Protegido e Receber Markdown
curl -X POST "http://localhost:8080/api/v1/agent/browse" \
  -H "Content-Type: application/json" \
  -d '{"url": "https://pt.wikipedia.org/wiki/Python", "render_js": true}'
```

---

## ⚠️ Aviso Legal, Status Experimental & Bugs

> **Sejamos sinceros:** O **RusyaSearch** é um projeto experimental em constante evolução construído por desenvolvedores para desenvolvedores.

- **Pode conter bugs ou quebras pontuais:** Como a internet muda constantemente, scrapers e seletores CSS podem quebrar quando sites atualizam seus layouts ou proteções anti-bot.
- **Uso Responsável:** Esta ferramenta foi criada para fins educacionais, automação de fluxos de agentes de IA e pesquisa em fontes acessíveis publicamente. Respeite os termos de serviço dos sites visitados e arquivos `robots.txt` quando aplicável.
- **Contribuições & Issues:** Encontrou um bug ou tem uma melhoria? PRs e relatórios de issues no GitHub são extremamente bem-vindos!

---

## 📄 Licença

Distribuído sob a licença **MIT**. Veja o arquivo [LICENSE](LICENSE) para mais detalhes.
