"""Censo completo de UN mes para futbolperuano.com: recorre TODAS las URLs del
sitemap real con lastmod en ese mes, extrae autor/sección/fecha del JSON-LD
NewsArticle de cada nota, y arma el roster + conteo real de notas por periodista.

Generalización de construir_roster_agosto.py (que quedó como caso particular de
este script, mes=2026-08) -- se necesitó de nuevo para julio 2026 al pedido de
Edwin (22-ago-2026) de tener histórico ene-jul, con julio construido con el MISMO
rigor que agosto (censo completo, no muestra) para que agosto tenga un periodo
anterior real con el que comparar.

Uso: python3 data/construir_roster_mes.py 2026-07
"""

import json
import re
import sys
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; futbolperuano-roster-scraper/1.0)"}
SITEMAP_URL = "https://www.futbolperuano.com/sitemaps/sitemap.xml"
N_WORKERS = 16


def obtener_urls_del_mes(mes_prefix: str) -> list[dict]:
    r = requests.get(SITEMAP_URL, headers=HEADERS, timeout=30)
    r.raise_for_status()
    locs = re.findall(r"<loc>(.*?)</loc>", r.text)
    lastmods = re.findall(r"<lastmod>(.*?)</lastmod>", r.text)
    return [{"url": loc, "lastmod": lm} for loc, lm in zip(locs, lastmods) if lm.startswith(mes_prefix)]


def extraer_articulo(url: str, intentos: int = 3) -> dict | None:
    for intento in range(intentos):
        try:
            r = requests.get(url, headers=HEADERS, timeout=15)
            if r.status_code != 200:
                return None
            html = r.text
            break
        except requests.RequestException:
            if intento == intentos - 1:
                return None
            time.sleep(1.5 * (intento + 1))
    else:
        return None

    for m in re.finditer(r'<script type="application/ld\+json">(.*?)</script>', html, re.S):
        try:
            data = json.loads(m.group(1))
        except json.JSONDecodeError:
            continue
        if data.get("@type") == "NewsArticle":
            autor = data.get("author") or {}
            seccion = url.replace("https://www.futbolperuano.com/", "").split("/")[0]
            return {
                "url": url,
                "autor": autor.get("name"),
                "autor_url": autor.get("url"),
                "titulo": data.get("headline"),
                "seccion": seccion,
                "articleSection": data.get("articleSection"),
                "datePublished": data.get("datePublished"),
                "wordCount": data.get("wordCount"),
                "keywords": data.get("keywords"),
            }
    return None


def main():
    if len(sys.argv) != 2:
        print("Uso: python3 data/construir_roster_mes.py YYYY-MM  (ej. 2026-07)")
        sys.exit(1)
    mes_prefix = sys.argv[1]
    sufijo = mes_prefix.replace("-", "_")

    urls = obtener_urls_del_mes(mes_prefix)
    print(f"URLs de {mes_prefix} en el sitemap: {len(urls)}")

    resultados = []
    con_error = []
    with ThreadPoolExecutor(max_workers=N_WORKERS) as ex:
        futuros = {ex.submit(extraer_articulo, u["url"]): u["url"] for u in urls}
        for i, fut in enumerate(as_completed(futuros), 1):
            url = futuros[fut]
            try:
                art = fut.result()
            except Exception:
                art = None
            if art and art.get("autor"):
                resultados.append(art)
            else:
                con_error.append(url)
            if i % 100 == 0:
                print(f"  {i}/{len(urls)} procesadas...")

    print(f"Notas con autor identificado: {len(resultados)}")
    print(f"Sin autor / error de fetch: {len(con_error)}")

    with open(f"data/notas_{sufijo}.json", "w", encoding="utf-8") as f:
        json.dump(resultados, f, ensure_ascii=False, indent=2)

    roster = defaultdict(lambda: {"notas": 0, "secciones": defaultdict(int), "autor_url": None})
    for art in resultados:
        r = roster[art["autor"]]
        r["notas"] += 1
        r["secciones"][art["seccion"]] += 1
        r["autor_url"] = art["autor_url"]

    roster_list = [
        {
            "autor": nombre, "notas": v["notas"], "autor_url": v["autor_url"],
            "secciones": dict(sorted(v["secciones"].items(), key=lambda kv: -kv[1])),
        }
        for nombre, v in roster.items()
    ]
    roster_list.sort(key=lambda r: -r["notas"])

    with open(f"data/roster_{sufijo}.json", "w", encoding="utf-8") as f:
        json.dump(roster_list, f, ensure_ascii=False, indent=2)

    print(f"\nRoster real ({len(roster_list)} periodistas identificados) -- {mes_prefix}:")
    for r in roster_list:
        secciones_txt = ", ".join(f"{s}({n})" for s, n in list(r["secciones"].items())[:4])
        print(f"  {r['notas']:>4}  {r['autor']:<30} {secciones_txt}")

    if con_error:
        with open(f"data/urls_sin_autor_{sufijo}.txt", "w", encoding="utf-8") as f:
            f.write("\n".join(con_error))


if __name__ == "__main__":
    main()
