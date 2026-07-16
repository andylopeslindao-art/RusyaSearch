import asyncio
import httpx
import json

BASE_URL = "http://localhost:8080"

async def main():
    print("🚀 [TEST SUITE] Iniciando bateria de testes do RusyaSearch 3.0 AI Agent Core...\n")
    async with httpx.AsyncClient(timeout=60.0) as client:
        # 1. Test Status
        print("1️⃣ Testando GET /api/status...")
        r = await client.get(f"{BASE_URL}/api/status")
        assert r.status_code == 200, f"Status falhou: {r.status_code}"
        print("   ✔ Status OK:", r.json())

        # 2. Test Tools Schema
        print("\n2️⃣ Testando GET /api/v1/agent/tools_schema...")
        r = await client.get(f"{BASE_URL}/api/v1/agent/tools_schema")
        assert r.status_code == 200
        data = r.json()
        funcs = [f["function"]["name"] for f in data["openai_functions"]]
        print("   ✔ Schemas OK. Ferramentas detectadas:", funcs)
        assert "rusyasearch_search_icons" in funcs
        assert "rusyasearch_universal_browse" in funcs

        # 3. Test Icons Search
        print("\n3️⃣ Testando GET /api/v1/agent/icons?query=python logo...")
        r = await client.get(f"{BASE_URL}/api/v1/agent/icons?query=python logo&limit=5")
        assert r.status_code == 200
        icons_data = r.json()
        print(f"   ✔ Ícones OK. Encontrados: {icons_data.get('total_icons')} ícones.")
        for ic in icons_data.get("icons", [])[:2]:
            print(f"      • [{ic['title']}] -> {ic['url']}")

        # 4. Test Universal Browse
        print("\n4️⃣ Testando POST /api/v1/agent/universal_browse (Quad-Tier Matrix)...")
        r = await client.post(f"{BASE_URL}/api/v1/agent/universal_browse", json={
            "url": "https://pt.wikipedia.org/wiki/Intelig%C3%AAncia_artificial",
            "max_chars": 2000
        })
        assert r.status_code == 200
        browse_data = r.json()
        print(f"   ✔ Universal Browse OK. Motor usado: {browse_data.get('engine_used')} | Palavras extraídas: {browse_data.get('word_count')}")
        print(f"   ✔ Preview Markdown: {browse_data.get('markdown')[:180]}...")

        # 5. Test Search across all sources
        print("\n5️⃣ Testando POST /api/v1/agent/search (Categoria: icons e web)...")
        r = await client.post(f"{BASE_URL}/api/v1/agent/search", json={
            "query": "agentes de ia automação",
            "sources": "all",
            "max_results": 4
        })
        assert r.status_code == 200
        search_data = r.json()
        print(f"   ✔ Search OK. Total retornado: {search_data.get('total')} resultados.")

    print("\n🎉 TODOS OS TESTES PASSARAM COM SUCESSO! O RUSYASEARCH 3.0 ESTÁ 100% OPERACIONAL PARA AGENTES DE IA.")

if __name__ == "__main__":
    asyncio.run(main())
