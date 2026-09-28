"""Cruza el censo real de notas de UN mes (data/notas_<sufijo>.json, sacado del
sitemap + JSON-LD de cada nota) con el tráfico REAL de GA4 por pagePath y el canal
de adquisición real por pagePath (ambos exportados a mano desde la propiedad
354621076) para armar la tabla real de periodistas de ese mes.

Generalización de construir_periodistas_agosto_real.py (que quedó como caso
particular, mes=2026-08) -- reusado para julio 2026 al pedido de Edwin de tener
un mes anterior real (mismo rigor que agosto) para comparar deltas.

Uso: python3 data/construir_periodistas_mes_real.py 2026-07 \
       data/ga4_paginas_julio_2026.csv data/ga4_paginas_canal_julio_2026.csv
"""

import csv
import json
import sys
from collections import defaultdict
from urllib.parse import urlparse


def _leer_csv_sin_comentarios(path):
    with open(path, encoding="utf-8") as f:
        lines = [l for l in f if not l.startswith("#") and l.strip()]
    return csv.DictReader(lines)


def cargar_ga4(path) -> dict:
    """pagePath -> {vistas, usuarios_activos, tiempo_interaccion_seg}. Suma
    (no sobrescribe) cuando la misma ruta aparece en más de una fila -- pasa
    real con los CSV armados concatenando varios tramos de fecha (necesario
    cuando un mes completo supera el tope de exportación de GA4, ver
    septiembre 2026): cada tramo trae su propia fila con la suma PARCIAL de
    esa ruta en su ventana, nunca el total del mes. tiempo_interaccion_seg se
    pondera por usuarios_activos de cada tramo (no se puede promediar un
    promedio sin peso)."""
    acumulado = defaultdict(lambda: {"vistas": 0.0, "usuarios_activos": 0.0, "_tiempo_num": 0.0})
    for row in _leer_csv_sin_comentarios(path):
        pagepath = row["Ruta de página y clase de pantalla"]
        try:
            vistas = float(row["Vistas"])
            usuarios_activos = float(row["Usuarios activos"])
            tiempo = float(row["Tiempo de interacción medio por usuario activo"])
        except ValueError:
            continue
        a = acumulado[pagepath]
        a["vistas"] += vistas
        a["usuarios_activos"] += usuarios_activos
        a["_tiempo_num"] += tiempo * usuarios_activos

    ga4 = {}
    for pagepath, a in acumulado.items():
        tiempo_prom = a["_tiempo_num"] / a["usuarios_activos"] if a["usuarios_activos"] else 0.0
        ga4[pagepath] = {
            "vistas": a["vistas"], "usuarios_activos": a["usuarios_activos"],
            "tiempo_interaccion_seg": tiempo_prom,
        }
    return ga4


def cargar_ga4_canal(path) -> dict:
    por_pagina = defaultdict(dict)
    for row in _leer_csv_sin_comentarios(path):
        pagepath = row["Ruta de página y clase de pantalla"]
        canal = row["Grupo de canales predeterminado de la sesión"]
        try:
            vistas = float(row["Vistas"])
        except ValueError:
            continue
        por_pagina[pagepath][canal] = por_pagina[pagepath].get(canal, 0.0) + vistas
    return dict(por_pagina)


def canal_dominante(distribucion_canales: dict) -> tuple[str, float]:
    if not distribucion_canales:
        return "—", 0.0
    total = sum(distribucion_canales.values())
    canal, vistas = max(distribucion_canales.items(), key=lambda kv: kv[1])
    return canal, (100 * vistas / total if total else 0.0)


def trafico_y_canal_real_por_seccion(ga4: dict, ga4_canal: dict) -> dict:
    trafico = defaultdict(float)
    canales_por_seccion = defaultdict(lambda: defaultdict(float))
    for pagepath, m in ga4.items():
        seg = pagepath.strip("/").split("/")[0] if pagepath.strip("/") else "home"
        trafico[seg] += m["vistas"]
    for pagepath, canales in ga4_canal.items():
        seg = pagepath.strip("/").split("/")[0] if pagepath.strip("/") else "home"
        for canal, vistas in canales.items():
            canales_por_seccion[seg][canal] += vistas

    resultado = {}
    for seg, total in trafico.items():
        canal, pct = canal_dominante(canales_por_seccion.get(seg, {}))
        resultado[seg] = {"trafico_mensual": total, "canal": canal, "pct_canal": round(pct, 1)}
    return resultado


def main():
    if len(sys.argv) != 4:
        print("Uso: python3 data/construir_periodistas_mes_real.py YYYY-MM ga4_paginas.csv ga4_paginas_canal.csv")
        sys.exit(1)
    mes_prefix, ga4_csv_path, ga4_canal_csv_path = sys.argv[1], sys.argv[2], sys.argv[3]
    sufijo = mes_prefix.replace("-", "_")

    with open(f"data/notas_{sufijo}.json", encoding="utf-8") as f:
        notas = json.load(f)
    ga4 = cargar_ga4(ga4_csv_path)
    ga4_canal = cargar_ga4_canal(ga4_canal_csv_path)

    notas_con_trafico = []
    sin_match = 0
    for n in notas:
        pagepath = urlparse(n["url"]).path
        m = ga4.get(pagepath)
        if m is None:
            sin_match += 1
            continue
        n2 = dict(n)
        n2.update(m)
        n2["canales"] = ga4_canal.get(pagepath, {})
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
            "autor": autor, "notas": r["notas"], "clics": r["clics"],
            "tiempo_pagina_seg": tiempo_pagina_seg, "seccion_principal": seccion_principal,
            "canal_dominante": canal, "pct_canal_dominante": pct_canal,
            "secciones": dict(sorted(r["secciones"].items(), key=lambda kv: -kv[1])),
            "notas_detalle": sorted(r["notas_detalle"], key=lambda x: -x["vistas"]),
        })
    roster_final.sort(key=lambda r: -r["clics"])

    with open(f"data/roster_{sufijo}_con_trafico.json", "w", encoding="utf-8") as f:
        json.dump(roster_final, f, ensure_ascii=False, indent=2)

    secciones = trafico_y_canal_real_por_seccion(ga4, ga4_canal)
    with open(f"data/secciones_trafico_real_{sufijo}.json", "w", encoding="utf-8") as f:
        json.dump(dict(sorted(secciones.items(), key=lambda kv: -kv[1]["trafico_mensual"])), f, ensure_ascii=False, indent=2)

    print(f"\nRoster real con tráfico y canal -- {mes_prefix}:")
    print(f"{'Periodista':<20}{'Notas':>7}{'Clics':>12}{'Tiempo pág.':>14}  {'Canal':<18}Sección principal")
    for r in roster_final:
        tiempo_txt = f"{int(r['tiempo_pagina_seg'])}s" if r["tiempo_pagina_seg"] else "—"
        canal_txt = f"{r['canal_dominante']} ({r['pct_canal_dominante']:.0f}%)"
        print(f"{r['autor']:<20}{r['notas']:>7}{r['clics']:>12,.0f}{tiempo_txt:>14}  {canal_txt:<18}{r['seccion_principal']}")


if __name__ == "__main__":
    main()
