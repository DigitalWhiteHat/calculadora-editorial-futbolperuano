"""Qué entidades/temas vienen BAJANDO, a nivel de todo el portal -- espejo de
colombia.com/data/calcular_declive_entidades.py.

Adaptación real frente a colombia.com (documentada, no oculta): allá compara dos
ventanas de ~17 días extraídas de un export especial de GA4
(ga4_pages_screens_periodos_*.csv, pageTitle a nivel de TODO el portal). Acá no
existe ese export a nivel portal con título -- el insumo real más amplio con
título es el censo de notas con autor identificado (notas_2026_MM.json, 525-838
notas/mes). Se compara julio (mes cerrado) vs. agosto (parcial, 1-22 ago) --
mismo principio que colombia.com (tráfico QUE OCURRIÓ en cada ventana, nunca
acumulado-a-la-fecha por publicación), a granularidad MENSUAL en vez de ~17
días -- una ventana más ancha, no un método distinto.

Uso: python3 data/calcular_declive_entidades.py
Escribe data/entidades_declive_portal.csv
"""
import json
import sys
from pathlib import Path
from urllib.parse import urlparse

import pandas as pd

DIR = Path(__file__).parent
sys.path.insert(0, str(DIR))
from entidades_periodista import (  # noqa: E402
    _cargar_ga4_vistas, _fusionar_variantes, _norm_tema, construir_propios,
    extraer_nombres_propios, extraer_temas,
)

UMBRAL_VOLUMEN = 50  # piso de tráfico en el mes "anterior" -- portal mucho más chico que colombia.com


def _cargar_periodo(sufijo_json: str, sufijo_mes: str) -> pd.DataFrame:
    notas = json.load(open(DIR / f"notas_{sufijo_json}.json", encoding="utf-8"))
    ga4 = _cargar_ga4_vistas(sufijo_mes)
    filas = []
    for n in notas:
        if not n.get("titulo"):
            continue
        ruta = urlparse(n["url"]).path
        vistas = ga4.get(ruta)
        if vistas is None:
            continue
        filas.append({"pagina": ruta, "titulo": n["titulo"], "trafico": vistas})
    return pd.DataFrame(filas).drop_duplicates(subset="pagina")


def _extraer_por_periodo(df: pd.DataFrame, propios: set[str]) -> pd.DataFrame:
    filas = []
    vistos = set()
    for row in df.itertuples():
        titulo = row.titulo
        if not isinstance(titulo, str) or not titulo.strip():
            continue
        propias = {c: "entidad" for c in extraer_nombres_propios(titulo, propios)}
        propias_norm = {_norm_tema(c) for c in propias}
        palabras_entidad = {w for c in propias for w in _norm_tema(c).split()}
        temas = {c: "tema" for c in extraer_temas(titulo, palabras_entidad)
                 if _norm_tema(c) not in propias_norm}
        for c, tipo in {**temas, **propias}.items():
            clave = (row.pagina, _norm_tema(c))
            if clave in vistos:
                continue
            vistos.add(clave)
            filas.append({"pagina": row.pagina, "entidad_norm": _norm_tema(c),
                           "entidad_display": c, "trafico": row.trafico, "tipo": tipo})

    df_ent = pd.DataFrame(filas)
    if df_ent.empty:
        return pd.DataFrame(columns=["entidad", "tipo", "paginas", "trafico"])

    paginas_por_norma = df_ent.groupby("entidad_norm")["pagina"].apply(set)
    paginas_por_norma = paginas_por_norma[paginas_por_norma.apply(len) >= 2].to_dict()
    if not paginas_por_norma:
        return pd.DataFrame(columns=["entidad", "tipo", "paginas", "trafico"])
    mapa_fusion = _fusionar_variantes(paginas_por_norma)

    df_ent = df_ent[df_ent["entidad_norm"].isin(mapa_fusion)].copy()
    df_ent["entidad_canon"] = df_ent["entidad_norm"].map(mapa_fusion)
    df_ent = df_ent.drop_duplicates(subset=["entidad_canon", "pagina"])

    display_propio = (
        df_ent[df_ent["entidad_norm"] == df_ent["entidad_canon"]]
        .groupby("entidad_canon")["entidad_display"].agg(lambda s: s.value_counts().idxmax())
    )
    display_fallback = df_ent.groupby("entidad_canon")["entidad_display"].agg(lambda s: min(s, key=len))
    tipo_mayoritario = df_ent.groupby("entidad_canon")["tipo"].agg(
        lambda s: "entidad" if "entidad" in set(s) else "tema")

    agg = df_ent.groupby("entidad_canon").agg(
        paginas=("pagina", "nunique"), trafico=("trafico", "sum")).reset_index()
    agg["entidad"] = agg["entidad_canon"].map(display_propio).fillna(agg["entidad_canon"].map(display_fallback))
    agg["tipo"] = agg["entidad_canon"].map(tipo_mayoritario)

    # Boilerplate de portal: umbral relativo, igual criterio que colombia.com
    # (15% de las páginas del periodo), portal mucho más chico acá.
    agg = agg[agg["paginas"] <= 0.15 * df["pagina"].nunique()]
    return agg[["entidad", "tipo", "paginas", "trafico"]]


def main():
    actual_df = _cargar_periodo("2026_08", "agosto")
    anterior_df = _cargar_periodo("2026_07", "julio")
    print(f"Notas con título y tráfico real -- agosto: {len(actual_df)}, julio: {len(anterior_df)}")

    todos_titulos = pd.concat([actual_df["titulo"], anterior_df["titulo"]])
    propios = construir_propios(todos_titulos)
    print(f"Palabras reconocidas como nombre propio en el corpus: {len(propios)}")

    actual = _extraer_por_periodo(actual_df, propios)
    anterior = _extraer_por_periodo(anterior_df, propios)
    print(f"Entidades/temas detectados -- actual (agosto): {len(actual)}, anterior (julio): {len(anterior)}")

    comparado = actual.merge(anterior, on=["entidad", "tipo"], how="outer",
                              suffixes=("_actual", "_anterior")).fillna(0)
    comparado = comparado[(comparado["trafico_anterior"] >= UMBRAL_VOLUMEN)
                           & (comparado["trafico_actual"] > 0) & (comparado["trafico_anterior"] > 0)]
    comparado["pct_cambio"] = 100 * (
        comparado["trafico_actual"] - comparado["trafico_anterior"]) / comparado["trafico_anterior"]
    comparado = comparado.sort_values("pct_cambio")

    columnas = ["entidad", "tipo", "trafico_actual", "trafico_anterior", "pct_cambio",
                "paginas_actual", "paginas_anterior"]
    comparado[columnas].to_csv(DIR / "entidades_declive_portal.csv", index=False)
    print(f"\nGuardado -> entidades_declive_portal.csv ({len(comparado)} filas)")

    print("\n=== Top 15 en mayor declive ===")
    for r in comparado.head(15).itertuples():
        print(f"  {r.entidad:35s} ({r.tipo}) {r.trafico_anterior:>8,.0f} -> {r.trafico_actual:>8,.0f}  ({r.pct_cambio:+.0f}%)")
    print("\n=== Top 10 en mayor subida ===")
    for r in comparado.sort_values('pct_cambio', ascending=False).head(10).itertuples():
        print(f"  {r.entidad:35s} ({r.tipo}) {r.trafico_anterior:>8,.0f} -> {r.trafico_actual:>8,.0f}  ({r.pct_cambio:+.0f}%)")


if __name__ == "__main__":
    main()
