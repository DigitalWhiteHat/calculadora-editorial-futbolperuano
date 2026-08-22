"""Descarga el HTML real de cada nota y extrae las señales on-page necesarias
para el Semáforo SEO -- adaptado 1:1 de
calculadora-periodistas/data/scrape_semaforo.py (colombia.com). Mismo parsing
(bs4, no un modelo de lenguaje, para conteos exactos) -- futbolperuano.com
comparte CMS/plantilla con colombia.com (mismo `div.articulo-contenido`, mismo
patrón `/tag/<slug>` para tags), confirmado inspeccionando el HTML real
22-ago-2026 antes de escribir este scraper.

Uso: python3 data/scrape_semaforo.py <archivo_notas.json> <salida.csv>
Lee un JSON tipo data/notas_2026_08.json (lista de {url, autor, seccion, ...})
Escribe un CSV con una fila por nota, todas las señales crudas.
"""

import io
import json
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import pandas as pd
import requests
from bs4 import BeautifulSoup
from PIL import Image

HEADERS = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}
SOCIAL_HOST_SNIPPETS = ("wa.me", "news.google.com", "whatsapp.com", "javascript:", "facebook.com",
                         "twitter.com", "x.com", "instagram.com", "t.me")
DOMINIO = "futbolperuano.com"
MAX_WORKERS = 8


def texto_o_none(tag):
    return tag.get_text(strip=True) if tag else None


def extraer_pagina(url: str) -> dict:
    r = requests.get(url, headers=HEADERS, timeout=20)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")

    h1 = texto_o_none(soup.find("h1"))
    title_tag = texto_o_none(soup.find("title"))
    if title_tag:
        title_tag = re.sub(r"\s*[-|]\s*Futbolperuano\.com\s*$", "", title_tag, flags=re.I).strip()
    meta_desc_tag = soup.find("meta", attrs={"name": "description"})
    meta_desc = meta_desc_tag.get("content", "").strip() if meta_desc_tag else None

    body = soup.find("div", class_="articulo-contenido")
    parrafos, h2s, tags = [], [], []
    enlaces_internos = []  # (indice_parrafo, texto_ancla, href)
    tiene_lista_tabla = False

    if body:
        idx_parrafo = 0
        for el in body.find_all(["p", "h2", "ul", "ol", "table"], recursive=True):
            if el.name == "p":
                txt = el.get_text(strip=True)
                if not txt:
                    continue
                idx_parrafo += 1
                parrafos.append(txt)
                for a in el.find_all("a", href=True):
                    href = a["href"]
                    if any(s in href for s in SOCIAL_HOST_SNIPPETS):
                        continue
                    if href.startswith("/tag/"):
                        continue
                    if href.startswith("/") or DOMINIO in href:
                        enlaces_internos.append((idx_parrafo, a.get_text(strip=True), href))
            elif el.name == "h2":
                txt = el.get_text(strip=True)
                if txt:
                    h2s.append(txt)
            elif el.name in ("ul", "ol", "table"):
                if "Comparte" not in el.get_text():
                    tiene_lista_tabla = True

        for a in body.find_all("a", href=True):
            if a["href"].startswith("/tag/"):
                tags.append(a.get_text(strip=True))

    palabras = sum(len(p.split()) for p in parrafos)
    caracteres = sum(len(p) for p in parrafos)
    primer_parrafo = parrafos[0] if parrafos else None

    og_img = soup.find("meta", property="og:image")
    img_url = og_img.get("content") if og_img else None
    img_ancho = None
    img_alt = None
    if img_url:
        try:
            resp_img = requests.get(img_url, headers=HEADERS, timeout=15)
            im = Image.open(io.BytesIO(resp_img.content))
            img_ancho = im.width
        except Exception:
            img_ancho = None
        nombre_archivo = img_url.rsplit("/", 1)[-1]
        for im_tag in soup.find_all("img"):
            src_cand = im_tag.get("data-src") or im_tag.get("src") or ""
            if nombre_archivo.split(".jpg")[0][:40] in src_cand:
                img_alt = im_tag.get("alt")
                break

    return {
        "h1": h1,
        "title_tag": title_tag,
        "meta_desc": meta_desc,
        "primer_parrafo": primer_parrafo,
        "num_parrafos": len(parrafos),
        "num_h2": len(h2s),
        "h2_textos": " | ".join(h2s),
        "tiene_lista_tabla": tiene_lista_tabla,
        "num_tags": len(tags),
        "tags_textos": ", ".join(tags),
        "num_enlaces_internos": len(enlaces_internos),
        "parrafo_primer_enlace": enlaces_internos[0][0] if enlaces_internos else None,
        "ancla_primer_enlace": enlaces_internos[0][1] if enlaces_internos else None,
        "anclas_todas": " | ".join(a[1] for a in enlaces_internos),
        "palabras_body": palabras,
        "caracteres_body": caracteres,
        "img_url": img_url,
        "img_ancho": img_ancho,
        "img_alt": img_alt,
    }


def _trabajo(nota):
    try:
        datos = extraer_pagina(nota["url"])
        datos["error"] = None
    except Exception as e:
        datos = {"error": str(e)}
    datos["url"] = nota["url"]
    datos["autor"] = nota["autor"]
    datos["seccion"] = nota["seccion"]
    return datos


def main():
    if len(sys.argv) != 3:
        print("Uso: python3 data/scrape_semaforo.py <notas.json> <salida.csv>")
        sys.exit(1)
    notas_path, salida_path = sys.argv[1], sys.argv[2]

    with open(notas_path, encoding="utf-8") as f:
        notas = json.load(f)
    notas = [n for n in notas if n.get("autor")]
    print(f"Notas a scrapear: {len(notas)}")

    filas = []
    inicio = time.time()
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
        futs = {ex.submit(_trabajo, n): i for i, n in enumerate(notas)}
        completados = 0
        for fut in as_completed(futs):
            filas.append(fut.result())
            completados += 1
            if completados % 50 == 0 or completados == len(notas):
                print(f"  {completados}/{len(notas)} ({time.time()-inicio:.0f}s)")

    df = pd.DataFrame(filas)
    df.to_csv(salida_path, index=False)
    print(f"\n{len(df)} filas -> {salida_path}")
    print(f"Errores: {df['error'].notna().sum()}")


if __name__ == "__main__":
    main()
