"""Temas recomendados por periodista -- en qué entidad/tema seguir escribiendo,
excluyendo coyunturas ya cerradas. Espejo de
colombia.com/data/construir_temas_recomendados.py.

Regla final "es_recurrente" (dos condiciones, las dos necesarias, idéntico a
colombia.com):
1) meses_activos >= 3 Y span (mes_reciente - mes_primero) >= 3 meses.
2) demanda_reciente_ratio >= 0.10 -- share de impresiones (normalizado contra
   el portal ese mes) del último mes con datos, dividido entre el share PICO
   histórico de esa entidad.

Adaptación real frente a colombia.com (documentada): allá solo ene-jun eran
"comparables" (jul/ago venían de un pull de GSC con metodología distinta).
Acá los 8 meses reales de futbolperuano (gsc_paginas_<mes>_2026.csv) vienen
TODOS del mismo export manual de la UI de Search Console (mismo tope real de
1.000 filas cada uno) -- se usan los 8, no solo 6, porque de verdad son
comparables entre sí.

evento_concluido (aporte marginal diario) NO está disponible -- necesita
snapshots diarios de GSC que futbolperuano no tiene todavía (ver
entidades_periodista.py). Queda siempre None, que por diseño de la regla de
abajo (`!= True`) no excluye nada -- "no penalizar por falta de datos", mismo
comportamiento que colombia.com ya tiene para ese caso.

Uso: python3 data/construir_temas_recomendados.py
Escribe data/temas_recomendados.csv
"""
import csv
import json
import re
import sys
from pathlib import Path
from urllib.parse import urlparse

import pandas as pd

DIR = Path(__file__).parent
sys.path.insert(0, str(DIR))
import entidades_periodista as ep  # noqa: E402

MESES_IMPRESIONES_COMPARABLES = [
    "2026-01", "2026-02", "2026-03", "2026-04", "2026-05", "2026-06", "2026-07", "2026-08",
]
_MES_A_SUFIJO = {
    "2026-01": "enero", "2026-02": "febrero", "2026-03": "marzo", "2026-04": "abril",
    "2026-05": "mayo", "2026-06": "junio", "2026-07": "julio", "2026-08": "agosto",
}


def _cargar_notas_con_mes() -> pd.DataFrame:
    filas = []
    for sufijo_json, sufijo_mes in ep.MESES:
        mes = f"20{sufijo_json[2:4]}-{sufijo_json[5:7]}"
        notas = json.load(open(DIR / f"notas_{sufijo_json}.json", encoding="utf-8"))
        for n in notas:
            if not n.get("titulo") or not n.get("autor"):
                continue
            filas.append({"ruta": urlparse(n["url"]).path, "autor": n["autor"],
                           "titulo": n["titulo"], "mes": mes})
    return pd.DataFrame(filas).drop_duplicates(subset="ruta")


def _cargar_impresiones_por_ruta_mes() -> pd.DataFrame:
    filas = []
    for mes, sufijo_mes in _MES_A_SUFIJO.items():
        with open(DIR / f"gsc_paginas_{sufijo_mes}_2026.csv", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                try:
                    impresiones = float(row["Impresiones"])
                except (ValueError, KeyError):
                    continue
                ruta = urlparse(row["Páginas principales"]).path
                filas.append({"ruta": ruta, "mes": mes, "impresiones": impresiones})
    return pd.DataFrame(filas)


def main():
    notas = _cargar_notas_con_mes()
    print(f"Notas con autor, título y mes real: {len(notas)}")

    impresiones = _cargar_impresiones_por_ruta_mes()
    portal_impresiones_mes = impresiones.groupby("mes")["impresiones"].sum()
    ultimo_mes = [MESES_IMPRESIONES_COMPARABLES[-1]]
    print(f"Meses con impresiones reales (los 8, mismo export en todos): {MESES_IMPRESIONES_COMPARABLES}")

    def _demanda_reciente_ratio(rutas_entidad: set) -> float:
        sub = impresiones[impresiones["ruta"].isin(rutas_entidad)]
        serie = sub.groupby("mes")["impresiones"].sum()
        if serie.empty:
            return 0.0
        share = (serie / portal_impresiones_mes.reindex(serie.index)).fillna(0)
        pico = share.max()
        if pico <= 0:
            return 0.0
        reciente = share.reindex(ultimo_mes).fillna(0).mean()
        return float(reciente / pico)

    propios = ep.construir_propios(notas["titulo"])
    print(f"Palabras reconocidas como nombre propio en el corpus: {len(propios)}")

    filas = []
    for row in notas.itertuples():
        propias = {c: "entidad" for c in ep.extraer_nombres_propios(row.titulo, propios)}
        propias_norm = {ep._norm_tema(c) for c in propias}
        palabras_entidad = {w for c in propias for w in ep._norm_tema(c).split()} - ep.STOPWORDS_TEMA
        temas = {c: "tema" for c in ep.extraer_temas(row.titulo, palabras_entidad)
                 if ep._norm_tema(c) not in propias_norm}
        for c, tipo in {**temas, **propias}.items():
            filas.append({"ruta": row.ruta, "autor": row.autor, "mes": row.mes,
                           "entidad_norm": ep._norm_tema(c), "entidad_display": c, "tipo": tipo})

    df = pd.DataFrame(filas)

    resultado = []
    for autor, grupo in df.groupby("autor"):
        rutas_por_norma = grupo.groupby("entidad_norm")["ruta"].apply(set)
        rutas_por_norma = rutas_por_norma[rutas_por_norma.apply(len) >= 2].to_dict()
        if not rutas_por_norma:
            continue
        mapa_fusion = ep._fusionar_variantes(rutas_por_norma)

        grupo = grupo[grupo["entidad_norm"].isin(mapa_fusion)].copy()
        grupo["entidad_canon"] = grupo["entidad_norm"].map(mapa_fusion)
        grupo = grupo.drop_duplicates(subset=["entidad_canon", "ruta"])

        display_propio = (
            grupo[grupo["entidad_norm"] == grupo["entidad_canon"]]
            .groupby("entidad_canon")["entidad_display"].agg(lambda s: s.value_counts().idxmax())
        )
        display_fallback = grupo.groupby("entidad_canon")["entidad_display"].agg(lambda s: min(s, key=len))
        tipo_mayoritario = grupo.groupby("entidad_canon")["tipo"].agg(
            lambda s: "entidad" if "entidad" in set(s) else "tema")

        agg = grupo.groupby("entidad_canon").agg(notas=("ruta", "nunique")).reset_index()
        agg["autor"] = autor
        agg["entidad"] = agg["entidad_canon"].map(display_propio)
        agg["entidad"] = agg["entidad"].fillna(agg["entidad_canon"].map(display_fallback))
        agg["tipo"] = agg["entidad_canon"].map(tipo_mayoritario)

        canon_vals = list(agg["entidad_canon"])
        for a in canon_vals:
            patron_a = re.compile(r"(?:^|\s)" + re.escape(a) + r"(?:\s|$)")
            for b in canon_vals:
                if a == b or len(a) >= len(b) or not patron_a.search(b):
                    continue
                tipo_a = agg.loc[agg["entidad_canon"] == a, "tipo"].iloc[0]
                tipo_b = agg.loc[agg["entidad_canon"] == b, "tipo"].iloc[0]
                if "entidad" in (tipo_a, tipo_b):
                    agg.loc[agg["entidad_canon"].isin([a, b]), "tipo"] = "entidad"

        meses_por_entidad = grupo.groupby("entidad_canon")["mes"]
        agg["meses_activos"] = agg["entidad_canon"].map(meses_por_entidad.nunique())
        agg["mes_reciente"] = agg["entidad_canon"].map(meses_por_entidad.apply(lambda s: s.dropna().max()))
        agg["mes_primero"] = agg["entidad_canon"].map(meses_por_entidad.apply(lambda s: s.dropna().min()))

        rutas_por_entidad_canon = grupo.groupby("entidad_canon")["ruta"].apply(set)
        agg["demanda_reciente_ratio"] = agg["entidad_canon"].map(rutas_por_entidad_canon).apply(_demanda_reciente_ratio)
        agg["evento_concluido"] = None  # sin snapshots diarios todavía -- ver docstring
        resultado.append(agg)

    rollup = pd.concat(resultado, ignore_index=True)

    notas_totales_autor = notas.groupby("autor").size()
    rollup["notas_totales_autor"] = rollup["autor"].map(notas_totales_autor)
    rollup = rollup[rollup["notas"] <= 0.5 * rollup["notas_totales_autor"]]
    rollup = rollup[~rollup["entidad"].isin({"Liga", "Copa"})]  # ver entidades_periodista.py

    rollup["confianza"] = rollup["notas"].apply(lambda n: "alta" if n >= 10 else "media" if n >= 3 else "baja")

    span_meses = rollup.apply(
        lambda r: ((pd.Period(r["mes_reciente"], freq="M") - pd.Period(r["mes_primero"], freq="M")).n
                   if pd.notna(r["mes_reciente"]) and pd.notna(r["mes_primero"]) else -1),
        axis=1,
    )
    _UMBRAL_DEMANDA_RECIENTE = 0.10
    es_recurrente_base = (
        (rollup["meses_activos"] >= 3)
        & (span_meses >= 3)
        & (rollup["demanda_reciente_ratio"] >= _UMBRAL_DEMANDA_RECIENTE)
    )
    rollup["es_recurrente"] = es_recurrente_base & (rollup["evento_concluido"] != True)  # noqa: E712

    columnas = ["autor", "entidad", "tipo", "notas", "confianza", "meses_activos",
                "mes_primero", "mes_reciente", "demanda_reciente_ratio", "evento_concluido", "es_recurrente"]
    salida = rollup[columnas].sort_values(["autor", "es_recurrente", "meses_activos"], ascending=[True, False, False])
    salida.to_csv(DIR / "temas_recomendados.csv", index=False)
    print(f"\n-> temas_recomendados.csv ({len(salida)} filas, {int(salida['es_recurrente'].sum())} marcadas recurrentes)")

    print("\n=== Muestra: temas recomendados por periodista ===")
    for autor, grupo in salida[salida["es_recurrente"]].groupby("autor"):
        print(f"\n{autor}:")
        for r in grupo.head(5).itertuples():
            print(f"  🎯 {r.entidad:35s} ({r.tipo}) {r.meses_activos} meses, demanda={r.demanda_reciente_ratio:.0%}")


if __name__ == "__main__":
    main()
