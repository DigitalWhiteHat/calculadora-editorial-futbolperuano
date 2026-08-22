"""Cruza el censo real de notas de agosto 2026 (data/notas_agosto_2026.json, sacado
del sitemap + JSON-LD de cada nota) con el tráfico REAL de GA4 por pagePath
(data/ga4_paginas_agosto_2026.csv) y el canal de adquisición real por pagePath
(data/ga4_paginas_canal_agosto_2026.csv, ambos exportados a mano desde la propiedad
354621076, 1-22 ago 2026) para armar la tabla real de periodistas -- reemplaza el
roster demo de app/datos_reales.py.

Metodología: por URL exacta, no por sección agregada -- así el tráfico de cada
periodista es el de SUS notas reales, no un promedio de sección. El tráfico y canal
de sección (para categoria_dificultad / seccion_dificultad_row) sí usan el CSV
completo (11.661 / 18.499 filas), no solo las 526 notas con autor identificado --
una sección puede tener mucho tráfico en páginas utilitarias (tablas de
posiciones, partidos por TV) que no son notas de ningún periodista, y esa demanda
real de la sección es justamente lo que hace que sea "fácil" generar clics ahí."""

import csv
import json
from collections import defaultdict
from urllib.parse import urlparse

NOTAS_PATH = "data/notas_agosto_2026.json"
GA4_CSV_PATH = "data/ga4_paginas_agosto_2026.csv"
GA4_CANAL_CSV_PATH = "data/ga4_paginas_canal_agosto_2026.csv"


def _leer_csv_sin_comentarios(path):
    with open(path, encoding="utf-8") as f:
        lines = [l for l in f if not l.startswith("#") and l.strip()]
    return csv.DictReader(lines)


def cargar_ga4() -> dict:
    """pagePath -> {vistas, usuarios_activos, tiempo_interaccion_seg}"""
    ga4 = {}
    for row in _leer_csv_sin_comentarios(GA4_CSV_PATH):
        path = row["Ruta de página y clase de pantalla"]
        try:
            ga4[path] = {
                "vistas": float(row["Vistas"]),
                "usuarios_activos": float(row["Usuarios activos"]),
                "tiempo_interaccion_seg": float(row["Tiempo de interacción medio por usuario activo"]),
            }
        except ValueError:
            continue
    return ga4


def cargar_ga4_canal() -> dict:
    """pagePath -> {canal: vistas} -- una página puede tener varias filas, una por canal."""
    por_pagina = defaultdict(dict)
    for row in _leer_csv_sin_comentarios(GA4_CANAL_CSV_PATH):
        path = row["Ruta de página y clase de pantalla"]
        canal = row["Grupo de canales predeterminado de la sesión"]
        try:
            vistas = float(row["Vistas"])
        except ValueError:
            continue
        por_pagina[path][canal] = por_pagina[path].get(canal, 0.0) + vistas
    return dict(por_pagina)


def canal_dominante(distribucion_canales: dict) -> tuple[str, float]:
    if not distribucion_canales:
        return "—", 0.0
    total = sum(distribucion_canales.values())
    canal, vistas = max(distribucion_canales.items(), key=lambda kv: kv[1])
    return canal, (100 * vistas / total if total else 0.0)


def trafico_y_canal_real_por_seccion(ga4: dict, ga4_canal: dict) -> dict:
    """Suma TODO el tráfico del CSV completo (11.661 filas) agrupado por primer
    segmento de pagePath -- incluye páginas utilitarias sin autor (tablas de
    posiciones, partidos por TV), que es justo lo que determina cuán 'fácil' es
    generar tráfico en esa sección. El canal dominante se sale del CSV con
    desglose por canal, sumado también a nivel de sección."""
    trafico = defaultdict(float)
    canales_por_seccion = defaultdict(lambda: defaultdict(float))
    for path, m in ga4.items():
        seg = path.strip("/").split("/")[0] if path.strip("/") else "home"
        trafico[seg] += m["vistas"]
    for path, canales in ga4_canal.items():
        seg = path.strip("/").split("/")[0] if path.strip("/") else "home"
        for canal, vistas in canales.items():
            canales_por_seccion[seg][canal] += vistas

    resultado = {}
    for seg, total in trafico.items():
        canal, pct = canal_dominante(canales_por_seccion.get(seg, {}))
        resultado[seg] = {"trafico_mensual": total, "canal": canal, "pct_canal": round(pct, 1)}
    return resultado


def main():
    with open(NOTAS_PATH, encoding="utf-8") as f:
        notas = json.load(f)
    ga4 = cargar_ga4()
    ga4_canal = cargar_ga4_canal()

    notas_con_trafico = []
    sin_match = 0
    for n in notas:
        path = urlparse(n["url"]).path
        m = ga4.get(path)
        if m is None:
            sin_match += 1
            continue
        n2 = dict(n)
        n2.update(m)
        n2["canales"] = ga4_canal.get(path, {})
        notas_con_trafico.append(n2)

    print(f"Notas con match exacto en GA4: {len(notas_con_trafico)} / {len(notas)} (sin match: {sin_match})")

    roster = defaultdict(lambda: {
        "notas": 0, "clics": 0.0, "tiempo_ponderado_num": 0.0, "tiempo_ponderado_den": 0.0,
        "secciones": defaultdict(float), "canales": defaultdict(float), "notas_detalle": [],
    })
    for n in notas_con_trafico:
        r = roster[n["autor"]]
        r["notas"] += 1
        r["clics"] += n["vistas"]
        r["tiempo_ponderado_num"] += n["tiempo_interaccion_seg"] * n["vistas"]
        r["tiempo_ponderado_den"] += n["vistas"]
        r["secciones"][n["seccion"]] += n["vistas"]
        for canal, vistas in n["canales"].items():
            r["canales"][canal] += vistas
        r["notas_detalle"].append({
            "titulo": n["titulo"], "url": n["url"], "seccion": n["seccion"],
            "vistas": n["vistas"], "datePublished": n["datePublished"],
        })

    roster_final = []
    for autor, r in roster.items():
        seccion_principal = max(r["secciones"].items(), key=lambda kv: kv[1])[0]
        tiempo_pagina_seg = r["tiempo_ponderado_num"] / r["tiempo_ponderado_den"] if r["tiempo_ponderado_den"] else None
        canal, pct_canal = canal_dominante(dict(r["canales"]))
        roster_final.append({
            "autor": autor,
            "notas": r["notas"],
            "clics": r["clics"],
            "tiempo_pagina_seg": tiempo_pagina_seg,
            "seccion_principal": seccion_principal,
            "canal_dominante": canal,
            "pct_canal_dominante": pct_canal,
            "secciones": dict(sorted(r["secciones"].items(), key=lambda kv: -kv[1])),
            "notas_detalle": sorted(r["notas_detalle"], key=lambda x: -x["vistas"]),
        })
    roster_final.sort(key=lambda r: -r["clics"])

    with open("data/roster_agosto_2026_con_trafico.json", "w", encoding="utf-8") as f:
        json.dump(roster_final, f, ensure_ascii=False, indent=2)

    secciones = trafico_y_canal_real_por_seccion(ga4, ga4_canal)
    with open("data/secciones_trafico_real_agosto_2026.json", "w", encoding="utf-8") as f:
        json.dump(dict(sorted(secciones.items(), key=lambda kv: -kv[1]["trafico_mensual"])), f, ensure_ascii=False, indent=2)

    print("\nRoster real con tráfico y canal (agosto 2026, 1-22 ago):")
    print(f"{'Periodista':<20}{'Notas':>7}{'Clics':>12}{'Tiempo pág.':>14}  {'Canal':<15}Sección principal")
    for r in roster_final:
        tiempo_txt = f"{int(r['tiempo_pagina_seg'])}s" if r["tiempo_pagina_seg"] else "—"
        canal_txt = f"{r['canal_dominante']} ({r['pct_canal_dominante']:.0f}%)"
        print(f"{r['autor']:<20}{r['notas']:>7}{r['clics']:>12,.0f}{tiempo_txt:>14}  {canal_txt:<18}{r['seccion_principal']}")

    print("\nTráfico y canal real por sección (TODO el portal, 1-22 ago 2026, top 15):")
    for seg, v in sorted(secciones.items(), key=lambda kv: -kv[1]["trafico_mensual"])[:15]:
        print(f"  {seg:<28}{v['trafico_mensual']:>12,.0f}   {v['canal']} ({v['pct_canal']:.0f}%)")


if __name__ == "__main__":
    main()
