"""Selecciona las entidades/temas prioritarias a nivel de TODO el portal,
deduplicadas, para alimentar "Temas del día". Espejo de
colombia.com/data/seleccionar_entidades_prioritarias.py -- reutiliza
temas_recomendados.csv (ya construido por-autor) en vez de rehacer la
extracción."""
from pathlib import Path

import pandas as pd

DIR = Path(__file__).parent
ORDEN_CONFIANZA = {"alta": 0, "media": 1, "baja": 2}


def seleccionar(top_n: int = 10) -> pd.DataFrame:
    df = pd.read_csv(DIR / "temas_recomendados.csv")
    sub = df[df["es_recurrente"]].copy()
    sub["_orden"] = sub["confianza"].map(ORDEN_CONFIANZA)
    agg = (
        sub.groupby("entidad")
        .agg(n_autores=("autor", "nunique"), confianza_top=("_orden", "min"), tipo=("tipo", "first"))
        .reset_index()
        .sort_values(["confianza_top", "n_autores"], ascending=[True, False])
    )

    elegidas = []
    for _, fila in agg.iterrows():
        nombre = fila["entidad"]
        nombre_norm = nombre.lower()
        es_variante = any(
            nombre_norm in e.lower() or e.lower() in nombre_norm for e in elegidas
        )
        if es_variante:
            continue
        elegidas.append(nombre)
        if len(elegidas) >= top_n:
            break

    return agg[agg["entidad"].isin(elegidas)].sort_values(["confianza_top", "n_autores"], ascending=[True, False])


if __name__ == "__main__":
    resultado = seleccionar()
    resultado.to_csv(DIR / "entidades_prioritarias_portal.csv", index=False)
    print(resultado.to_string(index=False))
