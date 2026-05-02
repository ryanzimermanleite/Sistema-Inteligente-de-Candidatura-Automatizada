"""Teste rápido do scraper corrigido para WordPress."""
import sys
sys.path.insert(0, ".")

from scraper.emprega_campinas import build_search_url, parse_job_listing_page, has_next_page
import urllib.request

# Teste 1: URLs
print("=== URLs ===")
print(f"Página 1: {build_search_url('Programador')}")
print(f"Página 2: {build_search_url('Programador', 2)}")

# Teste 2: Buscar e parsear HTML real
url = build_search_url("Programador")
print(f"\nBuscando: {url}")

req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
resp = urllib.request.urlopen(req, timeout=15)
html = resp.read().decode("utf-8")
print(f"HTML recebido: {len(html)} bytes")

jobs = parse_job_listing_page(html)
print(f"\n=== {len(jobs)} vagas encontradas ===")
for j in jobs[:5]:
    title = j["title"][:60]
    city = j["city"]
    company = j["company"][:30]
    print(f"  - {title}... | Cidade: {city} | Empresa: {company}")

print(f"\nTem próxima página: {has_next_page(html)}")
print("\n=== TESTE OK! ===")
