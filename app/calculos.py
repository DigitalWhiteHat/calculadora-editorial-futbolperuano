"""Fórmulas de negocio — núcleo idéntico a calculadora-periodistas/app/calculos.py
(colombia.com): los umbrales de dificultad de sección, la fórmula de eficiencia
normalizada y la regla de alerta NO cambian entre clientes, solo los datos de
entrada. Fase 1 (datos demo): estas mismas fórmulas corren sobre el generador
sintético de datos_reales.py hasta que se conecte el pipeline real de GA4/GSC."""

import numpy as np
import pandas as pd


def categoria_dificultad(trafico_mensual: float):
    """Fórmula central de "dificultad de sección". Secciones de alta demanda natural
    de búsqueda generan clics "más fácil", así que su tráfico se PENALIZA (×0.8) al
    comparar desempeño entre periodistas; secciones nicho de baja demanda requieren
    más mérito periodístico para el mismo volumen, así que se PREMIAN (×1.3)."""
    if trafico_mensual > 500_000:
        return "Fácil", 0.8
    if trafico_mensual >= 20_000:
        return "Media", 1.0
    return "Difícil", 1.3


def formatear_numero(n) -> str:
    if n is None or (isinstance(n, float) and np.isnan(n)):
        return "—"
    n = float(n)
    if abs(n) >= 1_000_000:
        return f"{n / 1_000_000:.2f}M"
    if abs(n) >= 1_000:
        return f"{n / 1_000:.0f}K"
    return f"{n:.0f}"


def formatear_tiempo(segundos) -> str:
    if segundos is None or (isinstance(segundos, float) and np.isnan(segundos)):
        return "—"
    segundos = int(segundos)
    return f"{segundos // 60}:{segundos % 60:02d} min"


def formatear_pct(valor, decimales: int = 0) -> str:
    if valor is None or (isinstance(valor, float) and np.isnan(valor)):
        return "—"
    return f"{valor:.{decimales}f}%"


def formatear_delta_pct(actual, anterior, decimales: int = 0):
    if anterior in (0, None) or pd.isna(anterior):
        return None
    delta = (actual - anterior) / abs(anterior) * 100
    signo = "+" if delta >= 0 else ""
    return f"{signo}{delta:.{decimales}f}%"


PESOS_RENDIMIENTO_DEFECTO = {"eficiencia": 4, "ctr": 2, "posicion": 2, "seo": 2}


def _sub_score_eficiencia(eficiencia_normalizada) -> float | None:
    """100 = mediana del equipo ese periodo -> 5.0/10. Escala logarítmica (no
    lineal) porque el índice no tiene techo -- un outlier real (ej. 1400) no debe
    aplastar la escala del resto ni hacer que todo lo demás se vea igual de bajo.
    Se recorta a [0,10] para que el puntaje final sea siempre interpretable."""
    if eficiencia_normalizada is None or (isinstance(eficiencia_normalizada, float) and np.isnan(eficiencia_normalizada)):
        return None
    e = max(float(eficiencia_normalizada), 1.0)
    return float(np.clip(5.0 + 3.0 * np.log10(e / 100.0), 0.0, 10.0))


def _sub_score_ctr(ctr_indice) -> float | None:
    """1.0 = CTR real igual al esperado por su posición (promedio del equipo) -> 5.0/10."""
    if ctr_indice is None or (isinstance(ctr_indice, float) and np.isnan(ctr_indice)):
        return None
    return float(np.clip(5.0 + 5.0 * (float(ctr_indice) - 1.0), 0.0, 10.0))


def _sub_score_posicion(posicion_promedio) -> float | None:
    """Posición SERP real, invertida (menor posición = mejor). Posición 1 -> 10,
    posición 20+ -> 0, escala lineal entre medio."""
    if posicion_promedio is None or (isinstance(posicion_promedio, float) and np.isnan(posicion_promedio)):
        return None
    return float(np.clip(10.0 - (float(posicion_promedio) - 1.0) * (10.0 / 19.0), 0.0, 10.0))


def _sub_score_seo(pct_cumplimiento_prom) -> float | None:
    """% de cumplimiento del checklist SEO on-page (0-100) -> 0-10, lineal directo."""
    if pct_cumplimiento_prom is None or (isinstance(pct_cumplimiento_prom, float) and np.isnan(pct_cumplimiento_prom)):
        return None
    return float(np.clip(float(pct_cumplimiento_prom) / 10.0, 0.0, 10.0))


def puntaje_rendimiento(fila, pesos: dict | None = None) -> dict:
    """Puntaje de rendimiento 0-10, para decidir incentivo mensual -- pedido de
    Edwin/Karen/Enrique en la reunión "Seguimiento SEO" (24-ago-2026). Combina
    señales YA reales y ya ajustadas por dificultad de sección (eficiencia_
    normalizada ya viene de categoria_dificultad()), no inventa una fórmula nueva
    de tráfico -- solo las pondera juntas en un solo número interpretable.

    Deliberadamente NO incluye volumen de notas como componente propio: Karen fue
    explícita en la reunión en que no todos hacen la misma cantidad de contenido
    (algunos tienen tareas de "servicio" no firmables, ej. mantener tablas de
    posiciones) -- el volumen ya se refleja indirectamente en trafico_ajustado
    (más notas buenas = más tráfico ajustado = mayor eficiencia_normalizada), sin
    premiar volumen por sí solo ni penalizar a quien escribe menos pero mejor.

    Cada componente puede faltar (s/d) sin que el puntaje se caiga -- se
    renormaliza sobre los pesos de los componentes SÍ disponibles, nunca se trata
    un dato faltante como un cero real (Principio 4 del espejo). Si NINGÚN
    componente tiene dato, devuelve puntaje=None explícito.

    Pesos por defecto (ajustables, ver PESOS_RENDIMIENTO_DEFECTO): eficiencia=4
    (el eje central, ya ajustado por dificultad), ctr=2 y posicion=2 (calidad real
    de SERP), seo=2 (ejecución on-page). Son un punto de partida razonable, no un
    número mágico -- se pueden recalibrar con Edwin/Karen una vez que vean
    puntajes reales de varios periodistas."""
    pesos = pesos or PESOS_RENDIMIENTO_DEFECTO
    componentes = {
        "eficiencia": _sub_score_eficiencia(fila.get("eficiencia_normalizada")),
        "ctr": _sub_score_ctr(fila.get("ctr_indice")),
        "posicion": _sub_score_posicion(fila.get("posicion_promedio")),
        "seo": _sub_score_seo(fila.get("pct_cumplimiento_prom")),
    }
    disponibles = {k: v for k, v in componentes.items() if v is not None}
    if not disponibles:
        return {"puntaje": None, "componentes": componentes, "pesos": pesos}
    peso_total = sum(pesos[k] for k in disponibles)
    puntaje = sum(disponibles[k] * pesos[k] for k in disponibles) / peso_total
    return {"puntaje": round(puntaje, 1), "componentes": componentes, "pesos": pesos}


def estado_label(eficiencia: float, en_alerta: bool):
    """Clasificación de 3 niveles que alimenta directamente los color_key del semáforo
    de estilos.py. Banda neutra 80-120 ("en rango") alrededor de la mediana normalizada
    a 100; en_alerta manda sobre el valor de eficiencia."""
    if en_alerta:
        return "EN ALERTA", "red"
    if eficiencia >= 120:
        return "SOBRE MEDIANA", "green"
    return "EN RANGO", "blue"
