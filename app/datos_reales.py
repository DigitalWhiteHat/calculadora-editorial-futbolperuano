"""Capa de datos — FASE 2 (datos REALES, con histórico).

Roster, notas, tráfico, canal y Search Console: 100% reales, sacados el
22-ago-2026 sin acceso manual del usuario -- roster vía sitemap público + JSON-LD
de cada nota (data/construir_roster_mes.py), tráfico y canal vía export de GA4
(propiedad 354621076, data/construir_periodistas_mes_real.py), posición SERP/CTR
real vía export de Search Console (data/construir_gsc_mes_real.py). Ver memoria
futbolperuano-roster-real-agosto2026.md y futbolperuano-app-fase1-estado.md.

Search Console: la UI de GSC topa la tabla/export en 1.000 páginas por clics
(límite de la plataforma, no elegido acá) -- cobertura real 76.5% de las notas de
julio, variable por periodista (58-100%, ver pct_cobertura_gsc). Quien tiene 0
notas en el top 1.000 queda con clics_busqueda/posicion_promedio/ctr_indice en
NaN, nunca en 0 (Principio 4). ctr_indice sigue la misma fórmula que
calculadora-periodistas/app/calculos.py (colombia.com): ctr_esperado =
1/posicion_promedio^0.35, ctr_indice = (ctr_real/ctr_esperado) normalizado a
1.0 = promedio del dataset ese periodo.

Estructura de periodos, igual patrón que colombia.com (pedido de Edwin,
22-ago-2026: "esto inicia con un histórico de enero a julio... agosto es
importantísimo que corra con todos los datos correctos" -- y luego, mismo día,
"hay que completar los otros meses, enero, febrero, marzo, abril, mayo y junio"):
- **Enero-julio 2026** ("2026-01" a "2026-07"): 7 meses CERRADOS, censo completo
  real cada uno (roster vía sitemap+JSON-LD, tráfico+canal real vía GA4, posición/
  CTR real vía Search Console) -- mismo rigor en los 7, no una muestra ni un mes
  "premium" y el resto liviano.
- **Agosto 2026** ("2026-08", mes en curso, PARCIAL -- 22 de 31 días al corte):
  mismo rigor que los 7 anteriores (censo completo, no muestra), tráfico de
  sección proyectado a mes completo con una regla de tres simple antes de
  clasificar dificultad. Es el periodo por defecto al abrir la app. Es el único
  periodo con semáforo SEO on-page real (data/scrape_semaforo.py) -- corrido una
  sola vez sobre el mes en curso, igual patrón que colombia.com.

Lo que SIGUE sin dato real, marcado explícitamente "s/d" (NUNCA fabricado --
Principio 4 del espejo): checklist SEO on-page por nota (pct_cumplimiento_prom),
auditoría de originalidad/IA (flags_ia), notas por dificultad individual.
"""

import json
import unicodedata
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

import calculos as calc

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_DATA_DIR = _PROJECT_ROOT / "data"

# ---------------------------------------------------------------------------
# Periodos con censo completo de periodistas (roster + tráfico real por nota)
# ---------------------------------------------------------------------------
def _mes_cerrado(mes: int, dias: int):
    return {
        "roster": f"roster_2026_{mes:02d}_con_trafico.json",
        "secciones": f"secciones_trafico_real_2026_{mes:02d}.json",
        "gsc": f"gsc_por_autor_2026_{mes:02d}.json",
        "inicio": date(2026, mes, 1), "fin": date(2026, mes, dias),
        "dias_transcurridos": dias, "dias_mes": dias,
    }


_PERIODOS_CONFIG = {
    "2026-01": _mes_cerrado(1, 31),
    "2026-02": _mes_cerrado(2, 28),
    "2026-03": _mes_cerrado(3, 31),
    "2026-04": _mes_cerrado(4, 30),
    "2026-05": _mes_cerrado(5, 31),
    "2026-06": _mes_cerrado(6, 30),
    "2026-07": _mes_cerrado(7, 31),
    "2026-08": {
        "roster": "roster_2026_08_con_trafico.json",
        "secciones": "secciones_trafico_real_2026_08.json",
        "gsc": "gsc_por_autor_2026_08.json",
        "seo": "seo_por_autor_2026_08.json",
        "inicio": date(2026, 8, 1), "fin": date(2026, 8, 22),
        "dias_transcurridos": 22, "dias_mes": 31,
    },
}
PERIODO_ANTERIOR = {
    "2026-08": "2026-07", "2026-07": "2026-06", "2026-06": "2026-05",
    "2026-05": "2026-04", "2026-04": "2026-03", "2026-03": "2026-02",
    "2026-02": "2026-01", "2026-01": None,
}

PERIODO_COMPLETO = "2026-08"  # periodo por defecto al abrir la app (mes en curso)
PERIODO_INICIO = _PERIODOS_CONFIG[PERIODO_COMPLETO]["inicio"]
PERIODO_FIN = _PERIODOS_CONFIG[PERIODO_COMPLETO]["fin"]

PERIODOS_DISPONIBLES = [
    ("2026-01", "Enero 2026 (real, censo completo)"),
    ("2026-02", "Febrero 2026 (real, censo completo)"),
    ("2026-03", "Marzo 2026 (real, censo completo)"),
    ("2026-04", "Abril 2026 (real, censo completo)"),
    ("2026-05", "Mayo 2026 (real, censo completo)"),
    ("2026-06", "Junio 2026 (real, censo completo)"),
    ("2026-07", "Julio 2026 (real, censo completo)"),
    ("2026-08", "Agosto 2026 (real, 1-22 ago — mes parcial)"),
]
LABEL_PERIODO = dict(PERIODOS_DISPONIBLES)

MES_CORTO = {
    "2026-01": "Ene", "2026-02": "Feb", "2026-03": "Mar", "2026-04": "Abr",
    "2026-05": "May", "2026-06": "Jun", "2026-07": "Jul", "2026-08": "Ago",
}
MES_LARGO = {
    "2026-01": "enero", "2026-02": "febrero", "2026-03": "marzo", "2026-04": "abril",
    "2026-05": "mayo", "2026-06": "junio", "2026-07": "julio", "2026-08": "agosto",
}

# ---------------------------------------------------------------------------
# Secciones reales (confirmadas en el sitemap real de www.futbolperuano.com,
# 22-ago-2026 -- más ricas que el nav visible del sitio).
# ---------------------------------------------------------------------------
# Tareas de "servicio" reales pero no firmables (ej. mantener tablas de
# posiciones, horarios de TV) -- Karen/Edwin, reunión 24-ago-2026: "cómo medir la
# firma... como la tabla de posiciones no se firma, no tendría cómo medirlo". El
# sistema no puede detectar esto solo (no hay autoría en esas páginas), así que
# queda como nota MANUAL explícita por autor, mostrada aparte del puntaje
# automático -- nunca mezclada en la fórmula ni usada para inflar/bajar el
# número. Llenar a mano cuando se confirme con el equipo editorial quién tiene
# estas tareas y qué % de su tiempo representan.
SERVICIO_NO_FIRMABLE: dict[str, str] = {
    # "Nombre Autor": "Mantiene tablas de posiciones de Liga 1 y Liga 2 -- no se refleja en notas firmadas.",
}

LABELS_SECCION = {
    "liga-1": "Liga 1", "liga-2": "Liga 2", "liga-3": "Liga 3",
    "copa-de-la-liga": "Copa de la Liga", "copa-peru": "Copa Perú",
    "futbol-femenino": "Liga Femenina", "liga-voley": "Vóley",
    "peruanos-en-el-exterior": "Peruanos en el exterior", "seleccion": "Selección",
    "copa-libertadores": "Copa Libertadores", "copa-sudamericana": "Copa Sudamericana",
    "mundial": "Mundial", "partidos-por-tv": "Partidos por TV",
    "futbol-de-menores": "Fútbol de menores", "futbol-internacional": "Fútbol internacional",
    "futsal": "Futsal", "peru": "Perú",
}

ICONO_CANAL = {
    "Organic Search": "🔍", "Direct": "🔗", "Organic Social": "📱",
    "Referral": "↪️", "Paid Search": "💰", "Email": "✉️", "Organic Video": "🎥",
    "Unassigned": "❔",
}


def _cargar_json(nombre: str):
    with open(_DATA_DIR / nombre, encoding="utf-8") as f:
        return json.load(f)


def slugify(nombre: str) -> str:
    sin_acentos = unicodedata.normalize("NFKD", nombre).encode("ascii", "ignore").decode("ascii")
    return sin_acentos.lower().replace(" ", "-")


def _roster_crudo(periodo: str) -> list[dict]:
    return _cargar_json(_PERIODOS_CONFIG[periodo]["roster"])


def _secciones_crudo(periodo: str) -> dict:
    return _cargar_json(_PERIODOS_CONFIG[periodo]["secciones"])


def _gsc_crudo(periodo: str) -> dict:
    return _cargar_json(_PERIODOS_CONFIG[periodo]["gsc"])


def _seo_crudo(periodo: str) -> dict:
    """Semáforo SEO real (data/semaforo_scoring.py) -- todavía no corrido para
    todos los periodos, así que {} (y por lo tanto s/d) es el fallback normal,
    no un error."""
    nombre = _PERIODOS_CONFIG[periodo].get("seo")
    return _cargar_json(nombre) if nombre else {}


def _posiciones_por_url(periodo: str) -> dict:
    sufijo = periodo.replace("-", "_")
    try:
        return _cargar_json(f"gsc_posicion_por_url_{sufijo}.json")
    except FileNotFoundError:
        return {}


def _eeat_crudo() -> dict:
    """EEAT real (bio /staff/, sameAs del JSON-LD, schema Person, consistencia
    temática) -- prácticamente estable mes a mes, se calculó una sola vez sobre
    la redacción completa en vez de repetirlo por periodo (ver
    data/eeat_bio_check.json + eeat_sameas_check.json, consolidados a mano en
    data/eeat_por_autor.json)."""
    try:
        return _cargar_json("eeat_por_autor.json")
    except FileNotFoundError:
        return {}


def _factor_proyeccion(periodo: str) -> float:
    cfg = _PERIODOS_CONFIG[periodo]
    return cfg["dias_mes"] / cfg["dias_transcurridos"]


def _eficiencia_por_autor(periodo: str) -> dict:
    """Eficiencia normalizada de un periodo, solo para alimentar el delta del
    periodo SIGUIENTE -- no dispara su propio lookup de periodo anterior (evita
    recursión infinita entre 2026-07 y 2026-08)."""
    roster = _roster_crudo(periodo)
    secciones = _secciones_crudo(periodo)
    factor = _factor_proyeccion(periodo)
    trafico_ajustado = {}
    for p in roster:
        meta_seccion = secciones.get(p["seccion_principal"], {"trafico_mensual": 0})
        _, ajuste = calc.categoria_dificultad(meta_seccion["trafico_mensual"] * factor)
        trafico_ajustado[p["autor"]] = p["clics"] * ajuste
    if not trafico_ajustado:
        return {}
    mediana = float(np.median(list(trafico_ajustado.values())))
    return {autor: 100 * v / mediana for autor, v in trafico_ajustado.items()} if mediana else {}


def cargar_periodistas(periodo: str | None = None) -> pd.DataFrame:
    periodo = periodo or PERIODO_COMPLETO
    roster = _roster_crudo(periodo)
    secciones = _secciones_crudo(periodo)
    gsc = _gsc_crudo(periodo)
    seo = _seo_crudo(periodo)
    eeat = _eeat_crudo()
    factor = _factor_proyeccion(periodo)

    filas = []
    for p in roster:
        seccion = p["seccion_principal"]
        meta_seccion = secciones.get(seccion, {"trafico_mensual": 0})
        trafico_mensual_proyectado = meta_seccion["trafico_mensual"] * factor
        dificultad_categoria, ajuste = calc.categoria_dificultad(trafico_mensual_proyectado)
        trafico_ajustado = p["clics"] * ajuste
        beat = ", ".join(LABELS_SECCION.get(s, s.title()) for s in list(p["secciones"].keys())[:3])
        # Search Console real, topado al top 1.000 de páginas por clics que expone
        # la UI de GSC (no elegido por nosotros) -- notas_con_gsc=0 deja todo en
        # None/NaN, nunca un 0 o un índice fabricado (Principio 4).
        g = gsc.get(p["autor"], {})
        # Semáforo SEO real (scraping del HTML + checklist, ver semaforo_scoring.py)
        # -- {} para periodos sin scraping corrido todavía, deja pct en NaN (s/d).
        s = seo.get(p["autor"], {})
        e = eeat.get(p["autor"], {})

        filas.append({
            "periodista": p["autor"],
            "autor": p["autor"],
            "slug": slugify(p["autor"]),
            "seccion": seccion,
            "seccion_raw": seccion,
            "beat": beat,
            "notas": p["notas"],
            "clics": p["clics"],
            "canal_dominante": p["canal_dominante"],
            "tiempo_pagina_seg": p["tiempo_pagina_seg"],
            "trafico_ajustado": trafico_ajustado,
            "dificultad_categoria": dificultad_categoria,
            "dificultad_ajuste": ajuste,
            "clics_busqueda": g.get("clics_busqueda") if g.get("clics_busqueda") is not None else np.nan,
            "impresiones_busqueda": g.get("impresiones") if g.get("impresiones") is not None else np.nan,
            "posicion_promedio": g.get("posicion_promedio") if g.get("posicion_promedio") is not None else np.nan,
            "ctr_real": g.get("ctr_real") if g.get("ctr_real") is not None else np.nan,
            "ctr_indice": g.get("ctr_indice") if g.get("ctr_indice") is not None else np.nan,
            "pct_cobertura_gsc": g.get("pct_cobertura_gsc", 0.0),
            "notas_top10": g.get("notas_top10", 0),
            "pct_cumplimiento_prom": s.get("pct_cumplimiento_prom", np.nan),
            "seo_notas_evaluadas": s.get("notas_evaluadas", 0),
            "seo_desglose_items": s.get("desglose_items", {}),
            "palabras_promedio": s.get("palabras_promedio", np.nan),
            "caracteres_promedio": s.get("caracteres_promedio", np.nan),
            "notas_verde": s.get("notas_verde", 0),
            "notas_amarillo": s.get("notas_amarillo", 0),
            "notas_rojo": s.get("notas_rojo", 0),
            "semaforo_verde_pct": s.get("semaforo_verde_pct", np.nan),
            "bio_verificable": e.get("bio_verificable"),
            "perfil_social_enlazado": e.get("perfil_social_enlazado"),
            "schema_autor_person": e.get("schema_autor_person"),
            "pct_consistencia_tematica": e.get("pct_consistencia_tematica", np.nan),
            # Sin dato real todavía -- nunca se fabrica, se marca explícitamente (Principio 4).
            "flags_ia": np.nan,
            "notas_facil": np.nan,
            "notas_media": np.nan,
            "notas_dificil": np.nan,
            "canibalizacion_pct": np.nan,
        })
    df = pd.DataFrame(filas)
    mediana = df["trafico_ajustado"].median()
    df["eficiencia_normalizada"] = 100 * df["trafico_ajustado"] / mediana

    # Puntaje de rendimiento (0-10, para incentivo mensual) -- pedido de la reunión
    # "Seguimiento SEO" 24-ago-2026, ver calculos.puntaje_rendimiento() para la
    # metodología completa. Se calcula DESPUÉS de tener eficiencia_normalizada
    # (depende de ella). "servicio" (tareas no firmables, ej. mantener tablas de
    # posiciones) queda como nota manual aparte -- ver SERVICIO_NO_FIRMABLE abajo,
    # NO se mezcla en la fórmula automática (Karen: no hay forma real de medirlo).
    resultado_rendimiento = df.apply(calc.puntaje_rendimiento, axis=1)
    df["puntaje_rendimiento"] = resultado_rendimiento.apply(lambda r: r["puntaje"])
    df["puntaje_rendimiento_detalle"] = resultado_rendimiento
    df["nota_servicio"] = df["autor"].map(SERVICIO_NO_FIRMABLE)

    periodo_anterior = PERIODO_ANTERIOR.get(periodo)
    if periodo_anterior:
        eficiencia_anterior = _eficiencia_por_autor(periodo_anterior)
        # np.nan explícito para quien no escribió en el periodo anterior (ej. un
        # periodista nuevo) -- nunca un 0 que se lea como "cayó a cero".
        df["eficiencia_normalizada_anterior"] = df["autor"].map(eficiencia_anterior).astype(float)
    else:
        df["eficiencia_normalizada_anterior"] = np.nan

    # en_alerta acá es un aviso de UN SOLO periodo (estado actual) -- la racha real
    # de 3+ meses vive aparte, en alertas_tendencia(), igual separación que colombia.com.
    df["en_alerta"] = df["eficiencia_normalizada"] < 55
    total_clics = df["clics"].sum()
    df["pct_trafico_total"] = 100 * df["clics"] / total_clics if total_clics else 0.0
    df["alertas"] = df.apply(generar_alertas_periodista, axis=1)
    return df


def generar_alertas_periodista(fila) -> list:
    """Alertas de ESTADO ACTUAL, reales, con lo que sí tenemos (eficiencia/SEO/CTR) --
    canibalización queda sin construir (no fabricada). Umbrales iguales a los que ya
    se usan en otras partes de la app (semáforo 80/60, estado_label 55/120)."""
    alertas = []
    if fila["en_alerta"]:
        alertas.append({
            "tipo": "Eficiencia", "severidad": "CRÍTICO",
            "mensaje": f"Eficiencia normalizada de {fila['eficiencia_normalizada']:.0f} (100 = mediana del "
                       "equipo), muy por debajo este periodo.",
        })
    if fila.get("seo_notas_evaluadas") and pd.notna(fila.get("pct_cumplimiento_prom")):
        pct = fila["pct_cumplimiento_prom"]
        if pct < 60:
            alertas.append({
                "tipo": "SEO", "severidad": "CRÍTICO",
                "mensaje": f"Semáforo SEO en {pct:.0f}% (censo completo de {int(fila['seo_notas_evaluadas'])} "
                           "notas reales) — por debajo del umbral rojo (60%).",
            })
        elif pct < 80:
            alertas.append({
                "tipo": "SEO", "severidad": "ATENCIÓN",
                "mensaje": f"Semáforo SEO en {pct:.0f}% — no llega al umbral verde (80%).",
            })
    if pd.notna(fila.get("ctr_indice")):
        ctr_idx = fila["ctr_indice"]
        if ctr_idx < 0.5:
            alertas.append({
                "tipo": "CTR", "severidad": "CRÍTICO",
                "mensaje": f"CTR índice de {ctr_idx:.2f} (Search Console real) — sus titulares/snippets "
                           "convierten menos de la mitad de lo que su posición predeciría.",
            })
        elif ctr_idx < 0.8:
            alertas.append({
                "tipo": "CTR", "severidad": "ATENCIÓN",
                "mensaje": f"CTR índice de {ctr_idx:.2f} — por debajo del promedio del equipo ese periodo.",
            })
    return alertas


def secciones_360(periodo: str | None = None) -> pd.DataFrame:
    """Panorama de TODO el portal (no solo secciones con periodista identificado) --
    espejo de secciones.py::_cargar() de colombia.com. Incluye páginas utilitarias
    reales (partidos-por-tv, en-vivo, portada) como barras "sin periodista, solo
    seguimiento agregado", igual rol que loterías en colombia.com."""
    from collections import defaultdict
    periodo = periodo or PERIODO_COMPLETO
    secciones_raw = _secciones_crudo(periodo)
    factor = _factor_proyeccion(periodo)
    roster = _roster_crudo(periodo)

    labels_360 = dict(LABELS_SECCION)
    labels_360.setdefault("en-vivo", "En vivo")
    labels_360.setdefault("home", "Portada")

    notas_por_seccion = defaultdict(lambda: {"notas": 0, "autores": set()})
    for p in roster:
        for n in p["notas_detalle"]:
            notas_por_seccion[n["seccion"]]["notas"] += 1
            notas_por_seccion[n["seccion"]]["autores"].add(p["autor"])

    total_portal = sum(m["trafico_mensual"] for seg, m in secciones_raw.items() if seg in labels_360)
    filas = []
    for seg, meta in secciones_raw.items():
        if seg not in labels_360:
            continue
        trafico = meta["trafico_mensual"] * factor
        info = notas_por_seccion.get(seg, {"notas": 0, "autores": set()})
        filas.append({
            "seccion": seg, "label": labels_360[seg], "trafico": trafico,
            "pct_del_portal": 100 * trafico / (total_portal * factor) if total_portal else 0,
            "con_periodista": info["notas"] > 0,
            "notas_identificadas": info["notas"], "periodistas_activos": len(info["autores"]),
        })
    return pd.DataFrame(filas).sort_values("trafico", ascending=False)


def especializacion_todos() -> pd.DataFrame:
    """Cruce periodista × sección con TODO el censo completo disponible (ene-ago
    2026, 8 meses reales) -- alimenta Secciones (especialización, simulador de
    escenarios) y Reemplazos. Mismos umbrales de confianza que colombia.com."""
    from collections import defaultdict
    agregado = defaultdict(lambda: {"notas": 0, "trafico": 0.0})
    for periodo, _ in PERIODOS_DISPONIBLES:
        for p in _roster_crudo(periodo):
            for n in p["notas_detalle"]:
                if n["seccion"] not in LABELS_SECCION:
                    continue
                key = (p["autor"], n["seccion"])
                agregado[key]["notas"] += 1
                agregado[key]["trafico"] += n["vistas"]
    filas = []
    for (autor, seg), v in agregado.items():
        confianza = "alta" if v["notas"] >= 10 else "media" if v["notas"] >= 3 else "baja"
        filas.append({
            "autor": autor, "seccion": seg, "notas": v["notas"], "trafico": v["trafico"],
            "trafico_por_nota": v["trafico"] / v["notas"] if v["notas"] else 0, "confianza": confianza,
        })
    df = pd.DataFrame(filas)
    if df.empty:
        return df
    medianas = df.groupby("seccion")["trafico_por_nota"].median()
    df["mediana_seccion_otros"] = df["seccion"].map(medianas)
    return df


def ritmo_diario_por_seccion() -> pd.DataFrame:
    """Tráfico REAL por día (sin proyectar a mes completo) por sección, los 8
    periodos reales disponibles (ene-ago 2026) -- para comparar el mismo tipo de
    unidad entre un mes cerrado (28-31 días reales) y uno parcial (22 días reales),
    mismo principio que colombia.com (dividir por días reales de cada fuente en
    vez de comparar totales crudos)."""
    filas = []
    for periodo, _ in PERIODOS_DISPONIBLES:
        secciones = _secciones_crudo(periodo)
        dias = _PERIODOS_CONFIG[periodo]["dias_transcurridos"]
        for seg, meta in secciones.items():
            if seg not in LABELS_SECCION:
                continue
            filas.append({"periodo": periodo, "seccion": seg, "ritmo_dia": meta["trafico_mensual"] / dias})
    return pd.DataFrame(filas)


def declive_secciones_jul_ago() -> pd.DataFrame:
    """% de cambio del ritmo diario real de cada sección, entre los DOS periodos
    reales más recientes (PERIODO_COMPLETO y su anterior -- hoy julio->agosto,
    pero se ajusta solo cuando avance el mes en curso). Señal de alerta temprana
    real (no una medición del algoritmo en sí -- ver caption de la vista Impacto
    algoritmo)."""
    periodo_actual = PERIODO_COMPLETO
    periodo_anterior = PERIODO_ANTERIOR.get(periodo_actual)
    if periodo_anterior is None:
        return pd.DataFrame()
    ritmo = ritmo_diario_por_seccion()
    piv = ritmo.pivot(index="seccion", columns="periodo", values="ritmo_dia")
    if periodo_anterior not in piv.columns or periodo_actual not in piv.columns:
        return pd.DataFrame()
    piv = piv.dropna(subset=[periodo_anterior, periodo_actual])
    piv["pct_cambio"] = 100 * (piv[periodo_actual] - piv[periodo_anterior]) / piv[periodo_anterior]
    piv = piv.reset_index().rename(columns={periodo_anterior: "ritmo_dia_anterior", periodo_actual: "ritmo_dia_actual"})
    return piv.sort_values("pct_cambio")


def notas_por_seccion_independiente(periodo: str | None = None) -> pd.DataFrame:
    """Notas por sección SIN depender de si el autor quedó identificado -- combina
    los 8 meses reales disponibles (ene-ago 2026). Espejo de secciones_7meses()
    de colombia.com, ahora con la misma profundidad de histórico."""
    from collections import defaultdict
    agregado = defaultdict(lambda: {"notas": 0, "trafico": 0.0})
    for periodo_i, _ in PERIODOS_DISPONIBLES:
        for p in _roster_crudo(periodo_i):
            for n in p["notas_detalle"]:
                if n["seccion"] not in LABELS_SECCION:
                    continue
                agregado[n["seccion"]]["notas"] += 1
                agregado[n["seccion"]]["trafico"] += n["vistas"]
    filas = []
    for seg, v in agregado.items():
        filas.append({
            "seccion": seg, "label": LABELS_SECCION.get(seg, seg.title()),
            "notas": v["notas"], "trafico": v["trafico"],
            "trafico_por_nota": v["trafico"] / v["notas"] if v["notas"] else 0,
        })
    return pd.DataFrame(filas)


def cargar_periodistas_meta() -> list[dict]:
    """Unión de periodistas reales vistos en CUALQUIER periodo con censo completo
    -- así el selector de perfil no pierde a alguien que no escribió en el periodo
    activo (ej. julio no tiene a Joaquín Vásquez, que sí escribió en agosto)."""
    vistos = {}
    for periodo in _PERIODOS_CONFIG:
        for p in _roster_crudo(periodo):
            vistos[p["autor"]] = slugify(p["autor"])
    return [{"slug": slug, "nombre": nombre} for nombre, slug in sorted(vistos.items())]


def periodista_por_slug(slug: str, periodo: str | None = None) -> dict | None:
    tabla = cargar_periodistas(periodo)
    fila = tabla[tabla["slug"] == slug]
    if fila.empty:
        return None
    return fila.iloc[0].to_dict()


def cargar_notas(periodo: str | None = None) -> pd.DataFrame:
    periodo = periodo or PERIODO_COMPLETO
    posiciones = _posiciones_por_url(periodo)
    semaforo_notas = _semaforo_por_url(periodo)
    filas = []
    for p in _roster_crudo(periodo):
        slug = slugify(p["autor"])
        total = p["clics"] or 1
        for n in p["notas_detalle"]:
            filas.append({
                "periodista": p["autor"],
                "slug": slug,
                "seccion": n["seccion"],
                "titulo": n["titulo"],
                "clics": n["vistas"],
                "pct_del_total": 100 * n["vistas"] / total,
                "posicion_promedio": posiciones.get(n["url"], np.nan),
                # ⚪ = nota real pero sin evaluar a fondo (sin match en el semáforo SEO
                # real de este periodo) -- nunca se inventa un semáforo de calidad.
                "semaforo": semaforo_notas.get(n["url"], "⚪"),
            })
    return pd.DataFrame(filas)


def _semaforo_por_url(periodo: str) -> dict:
    """🟢🟡🔴 real por nota (data/semaforo_notas_<sufijo>.csv) -- solo existe para
    periodos donde ya corrió semaforo_scoring.py (agosto, ver _seo_crudo)."""
    sufijo = periodo.replace("-", "_")
    ruta = _DATA_DIR / f"semaforo_notas_{sufijo}.csv"
    if not ruta.exists():
        return {}
    import csv
    with open(ruta, encoding="utf-8") as f:
        return {row["url"]: row["semaforo"] for row in csv.DictReader(f)}


def historial_periodista(autor: str) -> pd.DataFrame:
    """Serie real ene-ago 2026 (hasta 8 puntos -- todo el censo completo
    disponible) para las 3 gráficas históricas del perfil. Un periodista sin
    notas ese mes simplemente no aparece en la serie (no se rellena con 0) --
    Joaquín Vásquez, por ejemplo, solo aparece desde agosto (contratación nueva)."""
    filas = []
    for periodo, _ in PERIODOS_DISPONIBLES:
        tabla = cargar_periodistas(periodo)
        fila = tabla[tabla["autor"] == autor]
        if fila.empty:
            continue
        r = fila.iloc[0]
        filas.append({
            "mes": periodo, "mes_label": MES_LARGO.get(periodo, periodo).capitalize(),
            "trafico": r["clics"], "indice": r["eficiencia_normalizada"],
            "posicion_promedio": r["posicion_promedio"],
        })
    return pd.DataFrame(filas)


def alertas_tendencia() -> list[dict]:
    """Alertas de TENDENCIA reales, ahora que hay 7 meses cerrados (ene-jul 2026)
    para medirlas -- mismo criterio que colombia.com (dr.alertas_tendencia()).
    Regla: racha de meses SEGUIDOS, terminando en el más reciente CERRADO, con
    índice de eficiencia por debajo de 80 (la mediana del equipo ese mes) -- 3+
    meses = ATENCIÓN, 5+ meses = CRÍTICO. Agosto (parcial) queda fuera a
    propósito -- mezclarlo distorsionaría la racha real (un mal arranque de mes
    no es lo mismo que una tendencia sostenida)."""
    meses_cerrados = {p for p in _PERIODOS_CONFIG if _PERIODOS_CONFIG[p]["dias_transcurridos"] == _PERIODOS_CONFIG[p]["dias_mes"]}
    resultados = []
    for meta in cargar_periodistas_meta():
        hist = historial_periodista(meta["nombre"])
        hist = hist[hist["mes"].isin(meses_cerrados)].sort_values("mes")
        hist = hist[hist["indice"].notna()]
        if hist.empty:
            continue
        racha = 0
        for indice in hist["indice"].iloc[::-1]:
            if indice < 80:
                racha += 1
            else:
                break
        if racha < 3:
            continue
        severidad = "CRÍTICO" if racha >= 5 else "ATENCIÓN"
        ultimo_mes = hist["mes_label"].iloc[-1]
        fila_actual = cargar_periodistas(PERIODO_COMPLETO)
        fila_actual = fila_actual[fila_actual["autor"] == meta["nombre"]]
        seccion = fila_actual.iloc[0]["seccion"] if not fila_actual.empty else ""
        resultados.append({
            "slug": meta["slug"], "periodista": meta["nombre"], "seccion": seccion,
            "severidad": severidad,
            "mensaje": f"{racha} meses seguidos (hasta {ultimo_mes}) con eficiencia por debajo de la mediana del equipo.",
        })
    return resultados


def tendencia_periodistas() -> pd.DataFrame:
    """Tráfico real total (suma de todos los periodistas con censo completo) por
    mes -- ene-ago 2026, los 8 periodos reales (no confundir con
    trafico_real_por_mes(), que es el portal COMPLETO incluyendo páginas
    utilitarias sin autor)."""
    filas = []
    for periodo, _ in PERIODOS_DISPONIBLES:
        tabla = cargar_periodistas(periodo)
        filas.append({"mes": periodo, "trafico": tabla["clics"].sum()})
    return pd.DataFrame(filas)


def ranking_periodista(autor: str, periodo: str) -> tuple[int, int] | None:
    tabla = cargar_periodistas(periodo).sort_values("clics", ascending=False).reset_index(drop=True)
    idx = tabla.index[tabla["autor"] == autor]
    if len(idx) == 0:
        return None
    return int(idx[0]) + 1, len(tabla)


def secciones_trafico_real(periodo: str | None = None) -> dict:
    """seccion -> trafico_mensual proyectado, para el caption de _dificultad_header."""
    periodo = periodo or PERIODO_COMPLETO
    secciones = _secciones_crudo(periodo)
    factor = _factor_proyeccion(periodo)
    return {seg: meta["trafico_mensual"] * factor for seg, meta in secciones.items()}


def secciones_trafico_historico() -> pd.DataFrame:
    """Tráfico real de GA4 por sección, mes a mes (ene-ago 2026, 8 meses de censo
    completo) -- para el gráfico "General" de Impacto algoritmo. Sin proyección
    de fin de mes en agosto (dato bruto, 1-22 ago): la vista ya marca el mes
    parcial por separado, mismo criterio que _tendencia_portal() en general.py."""
    filas = []
    for periodo, _ in PERIODOS_DISPONIBLES:
        for seg, meta in _secciones_crudo(periodo).items():
            if seg not in LABELS_SECCION:
                continue
            filas.append({"mes": periodo, "seccion": seg, "trafico": meta["trafico_mensual"]})
    return pd.DataFrame(filas)


def rendimiento_por_seccion(autor: str) -> pd.DataFrame:
    """Tráfico/nota real por sección para ESTE periodista, combinando los 8 meses
    reales disponibles (ene-ago 2026) -- misma profundidad que "en qué secciones
    le rinde" de colombia.com. Confianza: alta ≥10 notas, media 3-9, baja <3
    (mismos umbrales que colombia.com)."""
    from collections import defaultdict
    agregado = defaultdict(lambda: {"notas": 0, "trafico": 0.0})
    for periodo, _ in PERIODOS_DISPONIBLES:
        for p in _roster_crudo(periodo):
            if p["autor"] != autor:
                continue
            for n in p["notas_detalle"]:
                # Solo secciones editoriales curadas -- el sitemap trae categorías
                # residuales (tags sueltos, eventos ya cerrados) que no son un beat
                # real, mismo criterio que secciones_dificultad_canal().
                if n["seccion"] not in LABELS_SECCION:
                    continue
                agregado[n["seccion"]]["notas"] += 1
                agregado[n["seccion"]]["trafico"] += n["vistas"]
    filas = []
    for seg, v in agregado.items():
        confianza = "alta" if v["notas"] >= 10 else "media" if v["notas"] >= 3 else "baja"
        filas.append({
            "seccion": seg, "notas": v["notas"], "trafico": v["trafico"],
            "trafico_por_nota": v["trafico"] / v["notas"] if v["notas"] else 0,
            "confianza": confianza,
        })
    df = pd.DataFrame(filas)
    return df.sort_values("trafico_por_nota", ascending=False) if not df.empty else df


def secciones_dificultad_canal(periodo: str | None = None) -> pd.DataFrame:
    """Solo secciones editoriales curadas en LABELS_SECCION -- el sitemap real trae
    decenas de categorías residuales (páginas utilitarias como /buscador/, /staff/,
    tags sueltos, o secciones de eventos ya cerrados como Tokio-2021/Eurocopa-2020)
    que no son un beat editorial vigente de ningún periodista actual."""
    periodo = periodo or PERIODO_COMPLETO
    secciones = _secciones_crudo(periodo)
    factor = _factor_proyeccion(periodo)
    filas = []
    for seg, meta in secciones.items():
        if seg not in LABELS_SECCION:
            continue
        trafico_proyectado = meta["trafico_mensual"] * factor
        dificultad, _ = calc.categoria_dificultad(trafico_proyectado)
        filas.append({
            "seccion": seg,
            "dificultad_categoria": dificultad,
            "canal_dominante": meta["canal"],
            "pct_canal_dominante": meta["pct_canal"],
            "trafico_total": trafico_proyectado,
        })
    return pd.DataFrame(filas).sort_values("trafico_total", ascending=False)


def trafico_real_por_mes() -> pd.DataFrame:
    """Tráfico TOTAL real del portal por mes (GA4, sin desglose por periodista) --
    enero-julio 2026 con tratamiento liviano (Principio 2 del espejo: aceptable
    para historial de meses que ya no son el foco inmediato), agosto es el mes en
    curso y por eso viene PARCIAL (1-22 ago, no proyectado acá -- la proyección de
    cierre la dibuja graficos.agregar_proyeccion sobre el propio gráfico)."""
    datos = _cargar_json("trafico_portal_por_mes_2026.json")
    df = pd.DataFrame([{"mes": mes, "trafico": v} for mes, v in datos.items()])
    return df.sort_values("mes").reset_index(drop=True)


# --- Entidades/temas reales (espejo del pipeline de colombia.com, 31-ago-2026) --

def entidades_periodista(autor: str) -> pd.DataFrame:
    """Entidades/temas reales en los que le rinde a este periodista (8 meses
    ene-ago 2026). Vigencia real (ACTIVA/CONCLUIDA) no disponible todavía --
    ver estado_vigencia == "SIN_DATOS_60D" y motivo_vigencia en cada fila."""
    df = pd.read_csv(_DATA_DIR / "entidades_periodista.csv")
    return df[df["autor"] == autor].reset_index(drop=True)


def temas_recomendados(autor: str) -> pd.DataFrame:
    """Temas recomendados reales (es_recurrente=True) para este periodista --
    misma regla que colombia.com: >=3 meses activos, span >=3 meses, demanda
    reciente >=10% del pico histórico."""
    df = pd.read_csv(_DATA_DIR / "temas_recomendados.csv")
    df = df[(df["autor"] == autor) & (df["es_recurrente"])]
    return df.sort_values("meses_activos", ascending=False).reset_index(drop=True)


def entidades_declive_portal(minimo_pct_caida: float = -15.0) -> pd.DataFrame:
    """Entidades/temas de TODO el portal que vienen cayendo julio->agosto real
    (ritmo mensual, ver data/calcular_declive_entidades.py)."""
    df = pd.read_csv(_DATA_DIR / "entidades_declive_portal.csv")
    return df[df["pct_cambio"] <= minimo_pct_caida].sort_values("pct_cambio").reset_index(drop=True)


def entidades_prioritarias_portal() -> pd.DataFrame:
    """Top entidades/temas recurrentes de TODO el portal, dedupeadas -- insumo
    real para "Temas del día" (ver seleccionar_entidades_prioritarias.py)."""
    return pd.read_csv(_DATA_DIR / "entidades_prioritarias_portal.csv")


def mes_es_parcial(mes: str) -> bool:
    return mes == "2026-08"


def proyeccion_fin_de_mes(serie: pd.DataFrame, col_valor: str, col_mes: str = "mes") -> dict | None:
    """Regla de tres simple: extrapola el ritmo diario de los días transcurridos
    del mes en curso al resto del mes. Solo aplica al último punto si es un mes
    parcial -- nunca inventa un cierre para un mes ya cerrado."""
    if serie.empty:
        return None
    ultimo_mes = serie[col_mes].iloc[-1]
    if not mes_es_parcial(ultimo_mes):
        return None
    cfg = _PERIODOS_CONFIG.get(PERIODO_COMPLETO, {})
    dias_transcurridos = cfg.get("dias_transcurridos", 22)
    dias_totales = cfg.get("dias_mes", 31)
    valor_actual = float(serie[col_valor].iloc[-1])
    valor_proyectado = valor_actual / dias_transcurridos * dias_totales
    return {
        "valor_actual": valor_actual, "valor_proyectado": valor_proyectado,
        "dias_transcurridos": dias_transcurridos, "dias_totales": dias_totales,
    }
