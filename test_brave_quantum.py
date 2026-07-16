import asyncio
import httpx
import json

BASE_URL = "http://localhost:8080"

async def main():
    print("🚀 [TEST SUITE] Testando o Hyper-Brave Quantum Search Engine (v5.0 - 1000x Melhorado)...\n")
    async with httpx.AsyncClient(timeout=35.0) as client:
        # 1. Test Brave Quantum specifically (`sources="brave"`)
        print("1️⃣ Testando POST /api/v1/agent/search com sources='brave' (Query: python programming)...")
        r = await client.post(f"{BASE_URL}/api/v1/agent/search", json={
            "query": "python programming",
            "sources": "brave",
            "max_results": 10
        })
        assert r.status_code == 200, f"Falha no status: {r.status_code}"
        data = r.json()
        print(f"   ✔ Brave Quantum OK! Total retornado: {data.get('total')} resultados.")
        for idx, res in enumerate(data.get("results", [])[:5], 1):
            title = res.get("title", "")
            url = res.get("url", "")
            score = res.get("score", 0)
            desc = res.get("description", "")[:120]
            print(f"      [{idx}] {title} (Score: {score:.2f}) -> {url}")
            if "Sitelinks:" in desc or "💡" in title or "💬" in title or "🕒" in desc:
                print(f"          🔥 Recurso Quântico Detectado: {desc[:80]}...")

        # 2. Test Tech Goggles / Tech dimension (`sources="tech"`)
        print("\n2️⃣ Testando POST /api/v1/agent/search com sources='tech' (Brave Goggles + StackOverflow)...")
        r = await client.post(f"{BASE_URL}/api/v1/agent/search", json={
            "query": "asyncio python error handling",
            "sources": "tech",
            "max_results": 8
        })
        assert r.status_code == 200
        data_tech = r.json()
        print(f"   ✔ Tech Goggles OK! Total retornado: {data_tech.get('total')} resultados.")
        for res in data_tech.get("results", [])[:3]:
            print(f"      • [{res.get('source')}] {res.get('title')} -> {res.get('url')}")

    print("\n🎉 TODOS OS TESTES DO BRAVE QUANTUM PASSARAM COM SUCESSO ABSOLUTO!")

if __name__ == "__main__":
    asyncio.run(main())
