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


def estado_label(eficiencia: float, en_alerta: bool):
    """Clasificación de 3 niveles que alimenta directamente los color_key del semáforo
    de estilos.py. Banda neutra 80-120 ("en rango") alrededor de la mediana normalizada
    a 100; en_alerta manda sobre el valor de eficiencia."""
    if en_alerta:
        return "EN ALERTA", "red"
    if eficiencia >= 120:
        return "SOBRE MEDIANA", "green"
    return "EN RANGO", "blue"
