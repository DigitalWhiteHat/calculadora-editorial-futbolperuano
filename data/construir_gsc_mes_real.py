"""Cruza el censo real de notas de UN mes (data/notas_<sufijo>.json) con el
export real de Search Console por página (data/gsc_paginas_<mes>.csv, exportado a
mano desde Rendimiento > Resultados de búsqueda > Páginas, con Clics/Impresiones/
CTR/Posición activados) para agregar por periodista: clics de búsqueda,
impresiones, posición promedio y CTR real vs. esperado (ctr_indice).

GOTCHA de la plataforma (no elegido por nosotros): la UI de Search Console topa
la tabla/export en 1.000 filas por página, ordenadas por clics -- para julio 2026
cubre 518/677 notas (76.5%), no el censo completo. Se marca explícito el % de
cobertura por periodista; para quien no tiene NINGUNA nota en el top 1000 el
campo queda NaN ("s/d"), nunca 0 (Principio 4 del espejo: 0 real y "sin dato"
son estados distintos).

Fórmula ctr_esperado/ctr_indice: igual a calculadora-periodistas/app/calculos.py
(colombia.com) -- ctr_esperado = 1 / posicion_promedio^0.35 (curva estándar de
decaimiento de CTR por posición SERP); ctr_indice = (ctr / ctr_esperado)
normalizado a 1.0 = promedio del dataset (aísla calidad de titular/snippet de la
posición de ranking).

Uso: python3 data/construir_gsc_mes_real.py 2026-07 data/gsc_paginas_julio_2026.csv
"""

import csv
import json
import sys
from collections import defaultdict
from urllib.parse import urlparse


def cargar_gsc(path) -> dict:
    """pagePath -> {clics, impresiones, posicion_ponderada_num} -- CTR se
    recalcula desde los totales agregados, nunca se promedia el CTR de fila."""
    gsc = {}
    with open(path, encoding="utf-8") as f:
        r = csv.DictReader(f)
        for row in r:
            pagepath = urlparse(row["Páginas principales"]).path
            gsc[pagepath] = {
                "clics": float(row["Clics"]),
                "impresiones": float(row["Impresiones"]),
                "posicion": float(row["Posición"].replace(",", ".")),
            }
    return gsc


def main():
    if len(sys.argv) != 3:
        print("Uso: python3 data/construir_gsc_mes_real.py YYYY-MM data/gsc_paginas_mes.csv")
        sys.exit(1)
    mes_prefix, gsc_csv_path = sys.argv[1], sys.argv[2]
    sufijo = mes_prefix.replace("-", "_")

    with open(f"data/notas_{sufijo}.json", encoding="utf-8") as f:
        notas = json.load(f)
    gsc = cargar_gsc(gsc_csv_path)

    por_autor = defaultdict(lambda: {
        "notas_totales": 0, "notas_con_gsc": 0, "clics": 0.0, "impresiones": 0.0,
        "pos_ponderada_num": 0.0,
    })
    for n in notas:
        pagepath = urlparse(n["url"]).path
        r = por_autor[n["autor"]]
        r["notas_totales"] += 1
        m = gsc.get(pagepath)
        if m is None:
            continue
        r["notas_con_gsc"] += 1
        r["clics"] += m["clics"]
        r["impresiones"] += m["impresiones"]
        r["pos_ponderada_num"] += m["posicion"] * m["impresiones"]
        if m["posicion"] <= 10:
            r["notas_top10"] = r.get("notas_top10", 0) + 1

    resultado = {}
    ratios_ctr = []
    for autor, r in por_autor.items():
        if r["notas_con_gsc"] == 0:
            resultado[autor] = {
                "notas_totales": r["notas_totales"], "notas_con_gsc": 0, "pct_cobertura_gsc": 0.0,
                "clics_busqueda": None, "impresiones": None, "posicion_promedio": None, "ctr_real": None,
            }
            continue
        ctr_real = r["clics"] / r["impresiones"] if r["impresiones"] else None
        posicion_promedio = r["pos_ponderada_num"] / r["impresiones"] if r["impresiones"] else None
        resultado[autor] = {
            "notas_totales": r["notas_totales"], "notas_con_gsc": r["notas_con_gsc"],
            "pct_cobertura_gsc": round(100 * r["notas_con_gsc"] / r["notas_totales"], 1),
            "clics_busqueda": r["clics"], "impresiones": r["impresiones"],
            "posicion_promedio": posicion_promedio, "ctr_real": ctr_real,
            "notas_top10": r.get("notas_top10", 0),
        }
        if ctr_real is not None and posicion_promedio and posicion_promedio > 0:
            ctr_esperado = 1 / (posicion_promedio ** 0.35)
            resultado[autor]["ctr_esperado"] = ctr_esperado
            ratio = ctr_real / ctr_esperado if ctr_esperado else None
            resultado[autor]["_ratio_bruto"] = ratio
            if ratio is not None:
                ratios_ctr.append(ratio)

    promedio_ratio = sum(ratios_ctr) / len(ratios_ctr) if ratios_ctr else None
    for autor, r in resultado.items():
        ratio = r.pop("_ratio_bruto", None)
        r["ctr_indice"] = (ratio / promedio_ratio) if (ratio is not None and promedio_ratio) else None

    with open(f"data/gsc_por_autor_{sufijo}.json", "w", encoding="utf-8") as f:
        json.dump(resultado, f, ensure_ascii=False, indent=2)

    # Posición real por URL -- para mostrar "Posición Google" en la lista de notas
    # destacadas de cada periodista, no solo el promedio agregado.
    posicion_por_url = {n["url"]: gsc[urlparse(n["url"]).path]["posicion"]
                         for n in notas if urlparse(n["url"]).path in gsc}
    with open(f"data/gsc_posicion_por_url_{sufijo}.json", "w", encoding="utf-8") as f:
        json.dump(posicion_por_url, f, ensure_ascii=False, indent=2)

    print(f"Search Console real -- {mes_prefix} (cobertura limitada al top 1.000 de la UI de GSC):")
    print(f"{'Periodista':<20}{'Cobertura':>11}{'Clics búsq.':>13}{'Posición':>10}{'CTR real':>10}{'CTR índice':>12}")
    for autor, r in sorted(resultado.items(), key=lambda kv: -(kv[1]['clics_busqueda'] or 0)):
        if r["clics_busqueda"] is None:
            print(f"{autor:<20}{'s/d (0 en top 1000)':>30}")
            continue
        print(f"{autor:<20}{r['pct_cobertura_gsc']:>10.1f}%{r['clics_busqueda']:>13,.0f}"
              f"{r['posicion_promedio']:>10.2f}{r['ctr_real']*100:>9.1f}%{r['ctr_indice']:>12.2f}")


if __name__ == "__main__":
    main()
