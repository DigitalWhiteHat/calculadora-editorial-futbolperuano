"""Aplica las reglas del Semáforo SEO sobre las señales crudas de
scrape_semaforo.py -- adaptado 1:1 de
calculadora-periodistas/data/semaforo_scoring.py (colombia.com), mismos 14
ítems automatizables con datos objetivos del HTML (longitudes, conteos,
posiciones). Los mismos 8 ítems que en colombia.com requieren keyword objetivo
o juicio editorial NO se automatizan acá tampoco -- se cuentan pero no se
fuerza un puntaje falso.

Dos adaptaciones reales de negocio (documentadas, no una copia ciega):
1. "listas_tablas" de colombia.com exige tabla/lista en secciones específicas
   (loterías, elecciones, cine, fútbol) porque esas son las que tienen datos
   enumerables SIEMPRE. En futbolperuano.com casi todo el contenido es de fútbol,
   pero no toda nota es un reporte de resultados con tabla (hay crónicas,
   fichajes, declaraciones) -- exigirlo a ciegas penalizaría injustamente notas
   que legítimamente no llevan tabla. Sin una regla editorial confirmada por
   sección, este ítem queda "no aplica" (excluido del %) para TODAS las notas.
2. "imagen_1200px" quedó TAMBIÉN excluido en este corte (22-ago-2026): el CDN de
   imágenes (cdn.futbolperuano.com) empieza a fallar/colgar las peticiones de
   ancho de imagen después de ~50 peticiones concurrentes (probado con 8 y con 3
   workers + reintentos, mismo resultado) -- no es una señal de contenido real,
   es una limitación de infraestructura del scraper. Pendiente remedir con
   throttling más agresivo (1 request secuencial con pausa) antes de reincluirlo.
Ambos se excluyen en vez de adivinar -- Principio 4 del espejo: no fabricar un
juicio sin base confiable.

Uso: python3 data/semaforo_scoring.py <entrada.csv> <sufijo_salida>
Lee <entrada.csv> (de scrape_semaforo.py)
Escribe data/semaforo_notas_<sufijo>.csv (pass/fail por ítem + score por nota)
        data/semaforo_periodistas_<sufijo>.csv (rollup con semáforo por periodista)
        data/gsc_seo... (no, ver más abajo) data/seo_por_autor_<sufijo>.json (para datos_reales.py)
"""

import json
import sys

import pandas as pd

GENERICOS_H2 = {"contexto", "detalles", "más información", "otros datos", "generalidades"}
ANCLAS_PROHIBIDAS = {"clic aquí", "aquí", "leer más", "este enlace", "click aquí", "ver más"}


def bajada_duplicada(row) -> bool:
    if pd.isna(row["h2_textos"]) or pd.isna(row["meta_desc"]):
        return False
    primer_h2 = row["h2_textos"].split(" | ")[0].strip()
    return primer_h2 == str(row["meta_desc"]).strip()


def h2_editoriales(row) -> list:
    if pd.isna(row["h2_textos"]):
        return []
    h2s = row["h2_textos"].split(" | ")
    if bajada_duplicada(row):
        h2s = h2s[1:]
    return [h for h in h2s if h.strip()]


def evaluar_nota(row: pd.Series) -> dict:
    h1 = "" if pd.isna(row["h1"]) else row["h1"]
    title_tag = "" if pd.isna(row["title_tag"]) else row["title_tag"]
    meta_desc = "" if pd.isna(row["meta_desc"]) else row["meta_desc"]
    primer_parrafo = "" if pd.isna(row["primer_parrafo"]) else row["primer_parrafo"]
    palabras = row["palabras_body"]
    h2s_reales = h2_editoriales(row)
    ancla = "" if pd.isna(row["ancla_primer_enlace"]) else row["ancla_primer_enlace"]
    alt = row["img_alt"]

    items = {}

    # H1 editorial (no confundir con el title SEO, que sí es corto): 70-170 caracteres.
    items["h1_70_170"] = 70 <= len(h1) <= 170

    # Title SEO 50-65 caracteres
    items["title_50_65"] = 50 <= len(title_tag) <= 65

    # Meta descripción 150-170 caracteres
    items["meta_desc_150_170"] = 150 <= len(meta_desc) <= 170

    # Meta descripción no repite el H1
    items["meta_desc_no_repite_h1"] = meta_desc.strip() != h1.strip() and len(meta_desc) > 0

    # Primer párrafo: respuesta inmediata, mín 180 car
    items["primer_parrafo_180"] = len(primer_parrafo) >= 180

    # H2 obligatorios: cantidad según extensión + calidad (no genéricos)
    rango_ok = (1 <= len(h2s_reales) <= 3) if palabras < 600 else (2 <= len(h2s_reales) <= 5)
    calidad_ok = all(h.strip().lower() not in GENERICOS_H2 and len(h.strip()) > 12 for h in h2s_reales) if h2s_reales else False
    items["h2_estructura"] = rango_ok and calidad_ok

    # Listas/tablas -- ver docstring del módulo: sin regla editorial confirmada
    # por sección todavía, se excluye del % para todas las notas (no se adivina).
    items["listas_tablas"] = None

    # Extensión mínima 400 palabras
    items["extension_400"] = palabras >= 400

    # Tags 1-5
    items["tags_1_5"] = 1 <= row["num_tags"] <= 5

    # Enlaces internos mínimo 2
    items["enlaces_min_2"] = row["num_enlaces_internos"] >= 2

    # Posición primer enlace en párrafos 1-3
    ppe = row["parrafo_primer_enlace"]
    items["enlace_parrafo_1_3"] = (1 <= ppe <= 3) if pd.notna(ppe) else False

    # Texto ancla 2-8 palabras, no genérico
    n_palabras_ancla = len(ancla.split())
    items["ancla_valida"] = (2 <= n_palabras_ancla <= 8) and (ancla.strip().lower() not in ANCLAS_PROHIBIDAS)

    # Imagen mínimo 1200px de ancho -- excluido este corte, ver docstring del módulo
    # (el CDN de imágenes no tolera el volumen de peticiones concurrentes del scraper).
    items["imagen_1200px"] = None

    # Imagen alt: no vacío, máx 120 car, no genérico
    if pd.isna(alt) or not str(alt).strip():
        items["imagen_alt"] = False
    else:
        alt_txt = str(alt).strip()
        items["imagen_alt"] = len(alt_txt) <= 120 and alt_txt.lower() not in {"futbolperuano.com", "futbolperuano", "imagen"}

    return items


def color_semaforo(pct: float) -> str:
    if pct >= 80:
        return "🟢"
    if pct >= 60:
        return "🟡"
    return "🔴"


def main():
    if len(sys.argv) != 3:
        print("Uso: python3 data/semaforo_scoring.py <entrada.csv> <sufijo_salida>")
        sys.exit(1)
    entrada_path, sufijo = sys.argv[1], sys.argv[2]

    raw = pd.read_csv(entrada_path)
    raw = raw[raw["error"].isna()].reset_index(drop=True) if "error" in raw else raw

    filas = []
    for _, row in raw.iterrows():
        items = evaluar_nota(row)
        aplicables = {k: v for k, v in items.items() if v is not None}
        n_pass = sum(1 for v in aplicables.values() if v)
        n_total = len(aplicables)
        pct = round(100 * n_pass / n_total, 1) if n_total else 0.0
        fila = {"url": row["url"], "autor": row["autor"], "seccion": row["seccion"],
                "items_pass": n_pass, "items_aplicables": n_total, "pct_cumplimiento": pct,
                "semaforo": color_semaforo(pct)}
        fila.update({f"item_{k}": v for k, v in items.items()})
        filas.append(fila)

    df_notas = pd.DataFrame(filas)
    df_notas.to_csv(f"data/semaforo_notas_{sufijo}.csv", index=False)

    rollup = df_notas.groupby("autor").agg(
        notas=("url", "count"),
        pct_cumplimiento_prom=("pct_cumplimiento", "mean"),
    ).reset_index()
    rollup["pct_cumplimiento_prom"] = rollup["pct_cumplimiento_prom"].round(1)
    rollup["semaforo"] = rollup["pct_cumplimiento_prom"].apply(color_semaforo)
    rollup = rollup.sort_values("pct_cumplimiento_prom", ascending=False)
    rollup.to_csv(f"data/semaforo_periodistas_{sufijo}.csv", index=False)

    # Desglose por ítem, por autor (para "¿en qué está fallando el SEO?") --
    # Principio 9 del espejo: tan importante como el % agregado.
    item_cols = [c for c in df_notas.columns if c.startswith("item_")]
    desglose_por_autor = {}
    for autor, grupo in df_notas.groupby("autor"):
        desglose_por_autor[autor] = {}
        for c in item_cols:
            serie = grupo[c].dropna()
            if len(serie) == 0:
                continue
            desglose_por_autor[autor][c.replace("item_", "")] = {
                "pct_cumple": round(100 * serie.mean(), 1), "n_evaluadas": int(len(serie)),
            }

    resultado_json = {
        autor: {
            "notas_evaluadas": int(r["notas"]), "pct_cumplimiento_prom": r["pct_cumplimiento_prom"],
            "semaforo": r["semaforo"], "desglose_items": desglose_por_autor.get(autor, {}),
        }
        for autor, r in rollup.set_index("autor").iterrows()
    }
    with open(f"data/seo_por_autor_{sufijo}.json", "w", encoding="utf-8") as f:
        json.dump(resultado_json, f, ensure_ascii=False, indent=2)

    print(f"=== Semáforo por periodista ({len(item_cols)-1} ítems automatizables, listas_tablas excluido) ===")
    print(rollup.to_string(index=False))
    print()
    print("=== Cumplimiento promedio por ítem (todas las notas) ===")
    for c in item_cols:
        serie = df_notas[c].dropna()
        if len(serie) == 0:
            print(f"  {c.replace('item_', ''):25s} -- (no aplica)")
            continue
        print(f"  {c.replace('item_', ''):25s} {serie.mean()*100:5.1f}%  (n={len(serie)})")


if __name__ == "__main__":
    main()
