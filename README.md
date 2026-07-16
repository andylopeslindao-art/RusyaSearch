# RusyaSearch 3.0 — Motor de Busca e Navegação para Agentes de IA

[![Python 3.11+](https://img.shields.io/badge/Python-3.11%2B-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110%2B-009688.svg)](https://fastapi.tiangolo.com/)
[![MCP Ready](https://img.shields.io/badge/MCP-Server%20Enabled-8A2BE2.svg)](https://modelcontextprotocol.io/)
[![No API Keys](https://img.shields.io/badge/100%25%20Free-No%20API%20Keys-success.svg)](https://github.com/rusya/RusyaSearch)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

**RusyaSearch 3.0** é uma suíte open-source de meta-busca, navegação anti-bot e extração estruturada de dados em Markdown, projetada **exclusivamente para Agentes de IA Autônomos** (Claude Code, Hermes Agent, Cursor, Aider, LangChain, OpenCode) e engenharia de software autônoma.

O projeto foi construído sob um princípio fundamental: **100% Grátis, sem necessidade de chaves de API ou serviços pagos**. Todo o processamento é feito localmente através de engenharia reversa, análise de pacotes e extração inteligente de dados.

---

## Principais Destaques e Arquitetura

### 1. Foco 100% em API & Agentes (Zero Bloat)
Removemos interfaces web visuais pesadas e código voltado para humanos. A raiz (`/`) entrega diretamente o **Console de Status e Especificação OpenAPI** (<15 KB), otimizada para chamadas de ferramentas por IA (`Function Calling`).

### 2. Motor de Busca Avançado e Sem Chave (`BraveSearcher v6.0`)
Desenvolvemos uma arquitetura que extrai dados do ecossistema Brave Search sem precisar de chaves pagas (`BRAVE_API_KEY`):
- **Análise do Payload SvelteKit (Engenharia Reversa de AST):** Em vez de raspar elementos HTML frágeis, o motor inspeciona diretamente o objeto de inicialização do SvelteKit (`kit.start data window`) no JavaScript das respostas. Isso permite capturar títulos originais, URLs limpas e descrições sem ofuscação visual.
- **Busca Simultânea com Filtros para Desenvolvedores (Brave Goggles):** Dispara requisições paralelas combinando a busca orgânica com o filtro `tech.goggles`. Esse filtro elimina fazendas de conteúdo, agregadores de SEO e spam, priorizando repositórios no GitHub, discussões do Stack Overflow, artigos científicos (ArXiv) e documentação oficial.
- **Extração de Painéis e Perguntas Frequentes:** Identifica painéis explicativos de entidades (`Knowledge Cards`) e perguntas com respostas diretas (`Q&A`), entregando resumos instantâneos para o agente sem requisições adicionais.
- **Pontuação Multi-Camadas:** Artigos corroborados tanto na busca geral quanto no filtro técnico recebem bônus automático de pontuação, garantindo que fontes técnicas confiáveis fiquem no topo.

### 3. Sistema Multi-Camadas de Navegação Anti-Bot (`AgentBrowser`)
Para extrair conteúdo limpo em Markdown de URLs que possuem proteções complexas contra robôs ou paywalls, o sistema utiliza uma abordagem em 4 níveis de fallback automático:
- **Nível 1 (HTTPx Assíncrono):** Requisições rápidas com rotação realista de cabeçalhos Chrome/Firefox no Linux.
- **Nível 2 (Playwright + Spoofing de GPU + Auto-Clique em Cookies):** Navegador headless que simula drivers OpenGL, rola a página naturalmente e aceita modais invasivos de cookies (`Aceitar tudo`, `GDPR Consent`) de forma automática.
- **Nível 3 (Espelhamento Jina AI):** Conversão instantânea de páginas restritas ou pesadas em Markdown limpo via `r.jina.ai`.
- **Nível 4 (Histórico Wayback & Cache Web):** Caso o site esteja fora do ar ou bloqueado por IP, o sistema consulta automaticamente o snapshot mais recente na API da Wayback Machine e no cache da Web.

### 4. Pesquisa Especializada de Ícones e SVGs (`/icons`)
Busca ícones transparentes (PNG e SVG) em repositórios abertos e retorna o código exato (`<img src="..." alt="..." />`) para que agentes de engenharia front-end possam injetar recursos gráficos diretamente em aplicações React, Vue ou HTML.

---

## Integração via MCP (Model Context Protocol)

O servidor nativo (`mcp_server.py`) expõe todas as funcionalidades da v3.0 para rodar via terminal (`stdio`) diretamente no **Cursor**, **Claude Code** ou **Hermes Agent**.

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

### Lista Completa de Ferramentas MCP
| Ferramenta MCP | Descrição |
| :--- | :--- |
| `rusya_search(query, sources, max_results)` | Pesquisa integrada em múltiplos motores sem chave de API (`web`, `brave`, `tech`, `icons`, `scholar`, `github`). |
| `rusya_search_icons(query, limit)` | Busca ícones transparentes (PNG/SVG) prontos para uso em código front-end. |
| `rusya_universal_access(url, max_chars)` | Acessa e converte qualquer URL restrita em Markdown usando o sistema multi-camadas de fallback. |
| `rusya_browse(url, max_chars)` | Acessa uma URL direta e devolve o conteúdo em Markdown estruturado. |
| `rusya_research(query, browse_top_n)` | Realiza meta-busca no tema, entra nas Top N páginas na íntegra e compila um relatório técnico completo. |
| `rusya_google_deep_research(query, browse_top_n)` | Pesquisa aprofundada focada no ecossistema Web com consolidação em tabelas e referências. |
| `rusya_google_suggest(query)` | Coleta sugestões de autocompletar em tempo real para expansão de palavras-chave. |
| `rusya_scholar(query, limit)` | Busca artigos científicos e resumos de PDFs no Google Scholar e arXiv. |
| `rusya_smart_dork(intent, domain, filetype)` | Converte linguagem natural em operadores avançados de pesquisa (Google Dorks). |
| `rusya_extract(url, target)` | Extração pontual de tabelas, listas, links ou texto de páginas visuais. |
| `rusya_crawl(seed_url, max_pages)` | Indexação local de páginas para consultas e análises offline. |

---

## Instalação e Início Rápido

### 1. Instalação
```bash
git clone https://github.com/rusya/RusyaSearch.git
cd RusyaSearch

python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium
```

### 2. Gerenciamento do Servidor
Utilize o script `start.sh` para gerenciar o serviço:
```bash
# Iniciar em segundo plano
./start.sh start

# Verificar status e portas ativas
./start.sh status

# Executar suíte de testes de verificação
.venv/bin/python test_v3.py
```
O servidor estará disponível na porta `8080` para toda a rede local (Wi-Fi/LAN):
- **Console de Status e Documentação:** `http://localhost:8080`
- **Schemas OpenAPI para Agentes:** `http://localhost:8080/api/v1/agent/tools_schema`
- **Swagger UI:** `http://localhost:8080/docs`

---

## Exemplos de Consumo na API REST (`/api/v1/agent`)

### 1. Python SDK / LangChain / CrewAI
```python
import httpx

class RusyaSearchClient:
    BASE_URL = "http://localhost:8080/api/v1/agent"

    @classmethod
    def search(cls, query: str, sources: str = "all", max_results: int = 5):
        payload = {"query": query, "sources": sources, "max_results": max_results}
        return httpx.post(f"{cls.BASE_URL}/search", json=payload).json()

    @classmethod
    def search_icons(cls, query: str, limit: int = 15):
        return httpx.get(f"{cls.BASE_URL}/icons", params={"query": query, "limit": limit}).json()

    @classmethod
    def browse(cls, url: str, max_chars: int = 12000):
        return httpx.post(f"{cls.BASE_URL}/universal_browse", json={"url": url, "max_chars": max_chars}).json()
```

### 2. cURL (Terminal / Shell Scripts)
```bash
# 1. Pesquisa técnica com filtros para desenvolvedores
curl -X POST "http://localhost:8080/api/v1/agent/search" \
  -H "Content-Type: application/json" \
  -d '{"query": "asyncio error handling", "sources": "tech", "max_results": 5}'

# 2. Pesquisa de ícones transparentes
curl -G "http://localhost:8080/api/v1/agent/icons" \
  --data-urlencode "query=python logo transparent"

# 3. Extração e conversão de URL em Markdown limpo
curl -X POST "http://localhost:8080/api/v1/agent/universal_browse" \
  -H "Content-Type: application/json" \
  -d '{"url": "https://pt.wikipedia.org/wiki/Python", "max_chars": 8000}'
```

---

## Licença
Distribuído sob a licença **MIT**. Veja o arquivo [LICENSE](LICENSE) para mais detalhes.
