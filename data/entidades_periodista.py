"""Temas/entidades reales en los que le rinde a cada periodista -- espejo del
pipeline real de colombia.com (calculadora-periodistas/data/entidades_periodista.py),
portado 1:1 en el algoritmo de extracción (Edwin, 31-ago-2026: "recuerda lo que
hicimos para colombia.com, con las entidades... aplícalo también para
futbolperuano").

IMPORTANTE -- distinción real de SEO (mismo criterio que colombia.com): en SEO,
una ENTIDAD es una cosa única e identificable -- persona, equipo, lugar,
organización, evento -- que Google puede mapear a un solo perfil sin ambigüedad
en su Knowledge Graph. Un TEMA (ej. "tabla de posiciones", "fecha del
campeonato") es relevancia semántica/temática, no una entidad única
identificable. Cada fila lleva "tipo": "entidad" o "tema".

Método (idéntico a colombia.com, dos extractores sobre el TÍTULO real de cada
nota, 8 meses ene-agosto 2026):
1. Nombres propios (tipo="entidad"): rachas de palabras con mayúscula inicial
   en el título (permite conectores en minúscula "de/la/del/los" en medio) ->
   jugadores, equipos, torneos, lugares.
2. Temas recurrentes (tipo="tema"): n-gramas de 2-4 palabras en minúscula
   (fuera de nombres propios), filtrando conectores sueltos, días/meses y
   boilerplate de formato.

Se agrega por (autor, entidad): notas, tráfico. Confianza por volumen de
muestra: alta >=10 notas, media 3-9, baja <3.

Vigencia real -- NO disponible todavía para futbolperuano (a diferencia de
colombia.com, que clasifica ACTIVA/CONCLUIDA contra 60 días de Search Console
diario vía gsc_vigencia.py): el exportador automático de GSC de futbolperuano
(activo desde 22-ago-2026) agrega por PÁGINA sobre una ventana de 35 días, no
por día -- no hay serie diaria real todavía con la que clasificar vigencia sin
inventar el dato. Se deja explícito "SIN_DATOS_60D" en vez de fabricar un
ACTIVA/CONCLUIDA -- Principio 4 del espejo: nunca fabricar lo que no se puede
medir. Se puede activar en cuanto el exportador acumule suficiente historia
diaria real (ver futbolperuano-app-fase1-estado.md).

Uso: python3 data/entidades_periodista.py
Escribe data/entidades_periodista.csv
"""
import csv
import json
import re
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path
from urllib.parse import urlparse

import pandas as pd

DIR = Path(__file__).parent

MESES = [
    ("2026_01", "enero"), ("2026_02", "febrero"), ("2026_03", "marzo"),
    ("2026_04", "abril"), ("2026_05", "mayo"), ("2026_06", "junio"),
    ("2026_07", "julio"), ("2026_08", "agosto"), ("2026_09", "septiembre"),
]

# --- Extracción de entidades desde el título (idéntico a colombia.com) -----

CONECTORES_NOMBRE = {"de", "del", "la", "las", "los", "y", "e"}

# Boilerplate universal (igual a colombia.com) + "peru"/"mundial" en el mismo
# rol que "colombia"/"mundial" allá: palabras de contexto que aparecen en casi
# cualquier título (país del medio, torneo genérico) sin ser una entidad
# identificable por sí solas. Calibrado contra el corpus real de futbolperuano
# (ver nota de calibración al final del archivo), no copiado a ciegas.
BOILERPLATE_MAYUSCULA = {
    "en", "vivo", "hoy", "ver", "donde", "cuando", "como", "cual", "cuales",
    "quien", "quienes", "que", "asi", "estos", "estas", "este", "esta", "eso", "esa",
    "fotos", "foto", "video", "videos", "television", "tv", "streaming", "peru",
    "mundial", "vs", "eeuu", "el", "la", "los", "las", "un", "una", "no", "si", "lo",
    "revelan", "revela", "confirma", "confirman", "anuncia", "anuncian",
    "sera", "seran", "dice", "dicen", "esto",
}

CONECTORES_TEMA = {
    "de", "del", "la", "las", "los", "y", "e", "en", "con", "para", "por", "su", "sus",
    "a", "ante", "bajo", "cabe", "contra", "desde", "durante", "entre", "hacia", "hasta",
    "mediante", "segun", "según", "sin", "sobre", "tras",
}
DIAS_MESES = {
    "lunes", "martes", "miercoles", "miércoles", "jueves", "viernes", "sabado", "sábado", "domingo",
    "enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto",
    "septiembre", "octubre", "noviembre", "diciembre",
}
VERBOS_GENERICOS = {
    "gracias", "puede", "pueden", "podria", "podría", "podran", "podrán", "hacer", "hizo",
    "hace", "dice", "dicen", "dijo", "asegura", "aseguran", "revela", "revelan", "confirma",
    "confirman", "anuncia", "anuncian", "circular", "rompe", "elegir",
    "paga", "pagan", "pago", "pagó", "pagaron", "sufre", "sufren", "sufrio", "sufrió",
    "fortalece", "fortalecen", "supera", "superan", "supero", "superó", "tarda", "tardan",
    "cuesta", "cuestan", "tiene", "tienen", "tuvo", "tuvieron", "va", "van", "cae", "caen",
    "cayo", "cayó", "avanza", "avanzan", "avanzo", "avanzó", "gana", "ganan", "gano", "ganó",
    "pierde", "pierden", "perdio", "perdió", "sube", "suben", "subio", "subió", "baja", "bajan",
    "bajo", "bajó", "presenta", "presentan", "presento", "presentó", "lanza", "lanzan", "lanzo",
    "lanzó", "alcanza", "alcanzan", "alcanzo", "alcanzó", "registra", "registran", "registro",
    "registró", "marca", "marcan", "marco", "marcó", "llega", "llegan", "llego", "llegó",
    "deja", "dejan", "dejo", "dejó", "busca", "buscan", "busco", "buscó", "logra", "logran",
    "logro", "logró", "enfrenta", "enfrentan", "enfrento", "enfrentó", "advierte", "advierten",
    "advirtio", "advirtió", "senala", "señala", "senalan", "señalan", "indica", "indican",
    "explica", "explican", "es", "son", "esta", "está", "estan", "están", "estara", "estará",
    "estaran", "estarán", "sera", "será", "seran", "serán", "fue", "fueron", "ser",
    "hay", "quiere", "quieren",
    "necesita", "necesitan", "permite", "permiten", "afecta", "afectan", "genera", "generan",
    "produce", "producen", "crece", "crecen", "crecio", "creció", "aumenta", "aumentan",
    "aumento", "aumentó", "disminuye", "disminuyen", "disminuyo", "disminuyó", "reduce",
    "reducen", "redujo", "mejora", "mejoran", "mejoro", "mejoró", "empeora", "empeoran",
    "empeoro", "empeoró",
    # Verbos futboleros frecuentes que no estaban en la lista de colombia.com --
    # verificados contra el corpus real de futbolperuano (ver calibración al final).
    "vence", "vencen", "empata", "empatan", "empato", "empató", "golea", "golean",
    "goleo", "goleó", "clasifica", "clasifican", "clasifico", "clasificó", "debuta",
    "debutan", "debuto", "debutó", "juega", "juegan", "jugara", "jugará", "anota",
    "anotan", "anoto", "anotó", "convoca", "convocan", "convoco", "convocó",
    "define", "definen", "definio", "definió", "recibe", "reciben", "recibio", "recibió",
    "visita", "visitan", "visito", "visitó", "cae", "caen",
}
STOPWORDS_TEMA = CONECTORES_TEMA | DIAS_MESES | VERBOS_GENERICOS | {
    "el", "los", "las", "un", "una", "unos", "unas", "que", "se", "es", "son",
    "esta", "estan", "fue", "ser", "hay", "no", "si", "por", "mas", "muy",
    "esto", "estas", "este", "estos", "asi", "todo", "toda", "todos", "todas", "peru",
    "hoy", "vivo", "ver", "video", "fotos",
}
STOPWORDS_TEMA |= {"o", "u", "al", "ya", "lo", "le", "les", "ni", "pero", "como", "era", "eran"}

_ABREVIATURAS = [
    (re.compile(r"\bEE\.?\s?UU\.?\b", re.IGNORECASE), "EEUU"),
    (re.compile(r"\bS\s?&\s?P\b", re.IGNORECASE), "SYP"),
    (re.compile(r"\bUS\$"), "USD"),
]
_DISPLAY_TOKEN = {"SYP": "S&P"}

_PALABRA = re.compile(r"[A-Za-zÁÉÍÓÚÑáéíóúñÜü]+")


def _tokens(titulo: str) -> list[str]:
    for patron, reemplazo in _ABREVIATURAS:
        titulo = patron.sub(reemplazo, titulo)
    return _PALABRA.findall(titulo)


def _norm_tema(tok: str) -> str:
    return unicodedata.normalize("NFKD", tok).encode("ascii", "ignore").decode("ascii").lower()


STOPWORDS_TEMA = {_norm_tema(w) for w in STOPWORDS_TEMA}
VERBOS_GENERICOS_NORM = {_norm_tema(w) for w in VERBOS_GENERICOS}


def _parece_verbo_conjugado(palabra_original: str) -> bool:
    p = palabra_original.lower()
    return p.endswith(("ó", "ió", "aron", "ieron"))


def construir_propios(titulos) -> set[str]:
    conteo_mayus = Counter()
    conteo_total = Counter()
    for t in titulos:
        for i, tok in enumerate(_tokens(t)):
            if i == 0:
                continue
            clave = _norm_tema(tok)
            if len(clave) < 2:
                continue
            conteo_total[clave] += 1
            if tok[0].isupper():
                conteo_mayus[clave] += 1
    propios = {w for w, total in conteo_total.items() if total >= 2 and conteo_mayus[w] / total >= 0.7}
    return propios - BOILERPLATE_MAYUSCULA


def extraer_nombres_propios(titulo: str, propios: set[str]) -> list[str]:
    toks = _tokens(titulo)
    if not toks:
        return []
    entidades = []
    i, n = 0, len(toks)
    while i < n:
        if _norm_tema(toks[i]) not in propios or not toks[i][0].isupper():
            i += 1
            continue
        racha = [toks[i]]
        j = i + 1
        while j < n:
            if _norm_tema(toks[j]) in propios and toks[j][0].isupper():
                racha.append(toks[j])
                j += 1
                continue
            if toks[j].lower() in CONECTORES_NOMBRE:
                k = j
                while k < n and toks[k].lower() in CONECTORES_NOMBRE:
                    k += 1
                conectores_en_minuscula = all(t == t.lower() for t in toks[j:k])
                if (conectores_en_minuscula and k < n
                        and _norm_tema(toks[k]) in propios and toks[k][0].isupper()):
                    racha.extend(toks[j:k + 1])
                    j = k + 1
                    continue
            break
        if racha[-1].lower() in CONECTORES_NOMBRE:
            racha = racha[:-1]
        if len(racha) == 1 and _norm_tema(racha[0]) in {"santo", "santa"}:
            i = j if j > i else i + 1
            continue
        if 1 <= len(racha) <= 5:
            entidades.append(" ".join(_DISPLAY_TOKEN.get(t, t) for t in racha))
        i = j if j > i else i + 1
    return entidades


def extraer_temas(titulo: str, palabras_entidad: set | None = None) -> list[str]:
    toks = _tokens(titulo)
    display = [t.lower() for t in toks]
    norm = [_norm_tema(t) for t in toks]
    palabras_entidad = palabras_entidad or set()
    temas = []
    n = len(norm)
    for tam in (2, 3, 4):
        for i in range(n - tam + 1):
            gram = norm[i:i + tam]
            if gram[0] in STOPWORDS_TEMA or gram[-1] in STOPWORDS_TEMA:
                continue
            if any(w in VERBOS_GENERICOS_NORM for w in gram):
                continue
            if any(_parece_verbo_conjugado(t) for t in toks[i:i + tam]):
                continue
            contenido = {w for w in gram if w not in STOPWORDS_TEMA}
            if len(contenido) < 2:
                continue
            if contenido <= palabras_entidad:
                continue
            if any(w.isdigit() for w in gram):
                continue
            temas.append(" ".join(display[i:i + tam]))
    return temas


def _fusionar_variantes(rutas_por_norma: dict) -> dict:
    formas = sorted(rutas_por_norma.keys(), key=len)
    padre = {f: f for f in formas}

    def find(x):
        while padre[x] != x:
            x = padre[x]
        return x

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra == rb:
            return
        if len(ra) > len(rb) or (len(ra) == len(rb) and len(rutas_por_norma[ra]) < len(rutas_por_norma[rb])):
            ra, rb = rb, ra
        padre[rb] = ra

    for i, a in enumerate(formas):
        patron = re.compile(r"(?:^|\s)" + re.escape(a) + r"(?:\s|$)")
        rutas_a = rutas_por_norma[a]
        for b in formas[i + 1:]:
            if len(a) >= len(b) or not patron.search(b):
                continue
            rutas_b = rutas_por_norma[b]
            solape = len(rutas_a & rutas_b) / len(rutas_a)
            if solape >= 0.8:
                union(a, b)

    return {f: find(f) for f in formas}


# --- Carga de datos reales de futbolperuano ---------------------------------

def _leer_csv_sin_comentarios(path):
    with open(path, encoding="utf-8") as f:
        lines = [l for l in f if not l.startswith("#") and l.strip()]
    return csv.DictReader(lines)


def _cargar_ga4_vistas(sufijo_mes: str) -> dict:
    """pagePath -> vistas, SUMADAS (no sobrescritas) entre filas -- los CSV de
    meses armados concatenando tramos de fecha (ej. septiembre 2026, tope de
    exportación de GA4) traen la misma ruta más de una vez, cada fila con la
    suma parcial de su ventana."""
    ga4 = defaultdict(float)
    for row in _leer_csv_sin_comentarios(DIR / f"ga4_paginas_{sufijo_mes}_2026.csv"):
        try:
            ga4[row["Ruta de página y clase de pantalla"]] += float(row["Vistas"])
        except (ValueError, KeyError):
            continue
    return dict(ga4)


def _cargar_notas() -> pd.DataFrame:
    filas = []
    for sufijo_json, sufijo_mes in MESES:
        notas = json.load(open(DIR / f"notas_{sufijo_json}.json", encoding="utf-8"))
        ga4 = _cargar_ga4_vistas(sufijo_mes)
        for n in notas:
            if not n.get("titulo") or not n.get("autor"):
                continue
            ruta = urlparse(n["url"]).path
            vistas = ga4.get(ruta)
            if vistas is None:
                continue
            filas.append({"ruta": ruta, "autor": n["autor"], "titulo": n["titulo"], "trafico": vistas})
    return pd.DataFrame(filas).drop_duplicates(subset="ruta")


def main():
    notas = _cargar_notas()
    print(f"Notas con autor, título y match de tráfico real: {len(notas)}")

    propios = construir_propios(notas["titulo"])
    print(f"Palabras reconocidas como nombre propio en el corpus: {len(propios)}")

    filas = []
    for row in notas.itertuples():
        propias = {c: "entidad" for c in extraer_nombres_propios(row.titulo, propios)}
        propias_norm = {_norm_tema(c) for c in propias}
        palabras_entidad = {w for c in propias for w in _norm_tema(c).split()} - STOPWORDS_TEMA
        temas = {c: "tema" for c in extraer_temas(row.titulo, palabras_entidad)
                 if _norm_tema(c) not in propias_norm}
        for c, tipo in {**temas, **propias}.items():
            filas.append({"ruta": row.ruta, "autor": row.autor,
                           "entidad_norm": _norm_tema(c),
                           "entidad_display": c, "trafico": row.trafico, "tipo": tipo})

    df = pd.DataFrame(filas)

    resultado = []
    for autor, grupo in df.groupby("autor"):
        rutas_por_norma = grupo.groupby("entidad_norm")["ruta"].apply(set)
        rutas_por_norma = rutas_por_norma[rutas_por_norma.apply(len) >= 2].to_dict()
        if not rutas_por_norma:
            continue
        mapa_fusion = _fusionar_variantes(rutas_por_norma)

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

        agg = grupo.groupby("entidad_canon").agg(notas=("ruta", "nunique"), trafico=("trafico", "sum")).reset_index()
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

        resultado.append(agg)

    rollup = pd.concat(resultado, ignore_index=True)

    notas_totales_autor = notas.groupby("autor").size()
    rollup["notas_totales_autor"] = rollup["autor"].map(notas_totales_autor)
    rollup = rollup[rollup["notas"] <= 0.5 * rollup["notas_totales_autor"]]

    # Calibración empírica (31-ago-2026, primera corrida real): "Liga"/"Copa" SOLAS
    # dominaban el top de casi todos los periodistas con decenas de miles de tráfico
    # -- no son ruido de extracción (sí son nombres propios reales en el título,
    # "de la Liga", "la Copa"), pero solas no distinguen nada real (¿Liga 1? ¿Liga
    # Femenina? ¿Copa Perú? ¿Copa Sudamericana?) mientras que esas formas compuestas
    # SÍ sobreviven aparte y sí son útiles. Filtro post-agregación (no tocar
    # BOILERPLATE_MAYUSCULA -- quitarlas de ahí rompería la extracción de "Liga
    # Femenina"/"Copa Perú", que necesitan "Liga"/"Copa" reconocidas para arrancar
    # la racha). Mismo criterio que colombia.com excluyendo "mundial" de pie.
    rollup = rollup[~rollup["entidad"].isin({"Liga", "Copa"})]

    rollup["trafico_por_nota"] = (rollup["trafico"] / rollup["notas"]).round(0)
    rollup["confianza"] = rollup["notas"].apply(lambda n: "alta" if n >= 10 else "media" if n >= 3 else "baja")

    # Vigencia real: sin serie diaria de Search Console todavía (ver docstring) --
    # SIN_DATOS_60D explícito, nunca ACTIVA/CONCLUIDA fabricado.
    rollup["estado_vigencia"] = "SIN_DATOS_60D"
    rollup["motivo_vigencia"] = ("el exportador automático de GSC agrega por página sobre "
                                  "35 días, todavía no hay serie diaria real con la que clasificar")
    rollup["impresiones_recientes_dia"] = pd.NA
    rollup["impresiones_pico_dia"] = pd.NA

    salida = rollup[["autor", "entidad", "tipo", "notas", "trafico", "trafico_por_nota", "confianza",
                      "estado_vigencia", "motivo_vigencia", "impresiones_recientes_dia", "impresiones_pico_dia"]]
    salida = salida.sort_values(["autor", "trafico"], ascending=[True, False])
    salida.to_csv(DIR / "entidades_periodista.csv", index=False)
    print(f"-> entidades_periodista.csv ({len(salida)} filas)")

    print("\n=== Muestra: top 8 entidades por periodista ===")
    for autor, grupo in salida.groupby("autor"):
        top = grupo.head(8)
        print(f"\n{autor}:")
        for r in top.itertuples():
            print(f"  {r.entidad:35s} {r.notas:3.0f} notas  {r.trafico:>10,.0f} tráfico  ({r.confianza})  {r.tipo}")


if __name__ == "__main__":
    main()

# Nota de calibración (31-ago-2026): BOILERPLATE_MAYUSCULA y los verbos
# futboleros añadidos a VERBOS_GENERICOS se ajustaron viendo la salida real de
# este script contra el corpus de futbolperuano (8 meses, 525-838 notas/mes) --
# mismo método que colombia.com, nunca listas inventadas sin verificar contra
# datos reales.
