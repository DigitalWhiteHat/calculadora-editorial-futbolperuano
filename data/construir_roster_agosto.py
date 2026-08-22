"""Censo completo de agosto 2026 para futbolperuano.com: recorre TODAS las URLs del
sitemap real con lastmod en agosto 2026, extrae autor/sección/fecha del JSON-LD
NewsArticle de cada nota, y arma el roster + conteo real de notas por periodista.

Metodología igual a colombia.com (ver memoria prompt-espejo-colombiacom-calculadora-
editorial.md, Principio 2 y 3): censo completo del mes en curso, no muestra --
paralelo con ThreadPoolExecutor porque el volumen mensual (~700 notas) lo permite
en minutos. Reintentos con backoff en cada petición (Principio 3: no confiar en un
solo intento por fallo transitorio de red)."""

import json
import re
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; futbolperuano-roster-scraper/1.0)"}
SITEMAP_URL = "https://www.futbolperuano.com/sitemaps/sitemap.xml"
MES_EN_CURSO_PREFIX = "2026-08"
N_WORKERS = 16


def obtener_urls_mes_en_curso() -> list[dict]:
    r = requests.get(SITEMAP_URL, headers=HEADERS, timeout=30)
    r.raise_for_status()
    locs = re.findall(r"<loc>(.*?)</loc>", r.text)
    lastmods = re.findall(r"<lastmod>(.*?)</lastmod>", r.text)
    urls = []
    for loc, lastmod in zip(locs, lastmods):
        if lastmod.startswith(MES_EN_CURSO_PREFIX):
            urls.append({"url": loc, "lastmod": lastmod})
    return urls


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
    urls = obtener_urls_mes_en_curso()
    print(f"URLs de agosto 2026 en el sitemap: {len(urls)}")

    resultados = []
    con_error = []
    with ThreadPoolExecutor(max_workers=N_WORKERS) as ex:
        futuros = {ex.submit(extraer_articulo, u["url"]): u["url"] for u in urls}
        for i, fut in enumerate(as_completed(futuros), 1):
            url = futuros[fut]
            try:
                art = fut.result()
            except Exception as e:
                art = None
            if art and art.get("autor"):
                resultados.append(art)
            else:
                con_error.append(url)
            if i % 100 == 0:
                print(f"  {i}/{len(urls)} procesadas...")

    print(f"Notas con autor identificado: {len(resultados)}")
    print(f"Sin autor / error de fetch: {len(con_error)}")

    with open("data/notas_agosto_2026.json", "w", encoding="utf-8") as f:
        json.dump(resultados, f, ensure_ascii=False, indent=2)

    roster = defaultdict(lambda: {"notas": 0, "secciones": defaultdict(int), "autor_url": None})
    for art in resultados:
        r = roster[art["autor"]]
        r["notas"] += 1
        r["secciones"][art["seccion"]] += 1
        r["autor_url"] = art["autor_url"]

    roster_list = [
        {
            "autor": nombre,
            "notas": v["notas"],
            "autor_url": v["autor_url"],
            "secciones": dict(sorted(v["secciones"].items(), key=lambda kv: -kv[1])),
        }
        for nombre, v in roster.items()
    ]
    roster_list.sort(key=lambda r: -r["notas"])

    with open("data/roster_agosto_2026.json", "w", encoding="utf-8") as f:
        json.dump(roster_list, f, ensure_ascii=False, indent=2)

    print(f"\nRoster real ({len(roster_list)} periodistas identificados):")
    for r in roster_list:
        secciones_txt = ", ".join(f"{s}({n})" for s, n in list(r["secciones"].items())[:4])
        print(f"  {r['notas']:>4}  {r['autor']:<30} {secciones_txt}")

    if con_error:
        with open("data/urls_sin_autor_agosto_2026.txt", "w", encoding="utf-8") as f:
            f.write("\n".join(con_error))


if __name__ == "__main__":
    main()
