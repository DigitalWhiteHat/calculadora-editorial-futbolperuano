"""Perfil del periodista — espejo de calculadora-periodistas/app/individual.py
(colombia.com), adaptado a los datos reales disponibles de futbolperuano.com.

Misma estructura y mismos campos que colombia.com donde hay dato real
(tráfico/eficiencia/posición histórica ene-sep, EEAT vía JSON-LD+/staff/,
semáforo SEO real de septiembre, notas destacadas con posición real). Lo que
colombia.com calcula con pipelines de minería de texto que acá no existen
todavía (temas/entidades recurrentes, canibalización, ecuación de titulares)
se muestra como tarjeta "pendiente" explícita -- nunca fabricado (Principio 4
del espejo); ya NO es un problema de falta de historial (hay los mismos 8
meses reales que colombia.com), sino de pipeline sin construir."""

import math

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import calculos as calc
import datos_reales as dr
from avatares import avatar_data_uri
from estilos import card_value, delta_html, info_banner, metrica_card, nota_row, pill, trafico_card
from graficos import agregar_proyeccion, marcar_mes_parcial, texto_metodologia_proyeccion

COLOR_ESTADO = {"green": "#16A34A", "blue": "#3457D5", "red": "#DC2626"}
ICONO_ESTADO = {"green": "📈", "blue": "➡️", "red": "🔻"}

ACCION_ITEM_SEO = {
    "h1_70_170": "Ajusta el H1 editorial a 70-170 caracteres — se está saliendo de ese rango.",
    "title_50_65": "Ajusta el title SEO a 50-65 caracteres (fuera de ese rango, Google lo corta).",
    "meta_desc_150_170": "Escribe la meta descripción con 150-170 caracteres — si no, Google la reescribe.",
    "meta_desc_no_repite_h1": "No copies el H1 en la meta descripción — debe sumar información nueva.",
    "primer_parrafo_180": "El primer párrafo debe responder la pregunta del titular en los primeros 180 caracteres.",
    "h2_estructura": "Organiza el cuerpo con subtítulos H2 (cantidad y jerarquía correctas).",
    "extension_400": "La nota debe tener mínimo 400 palabras — se está quedando corta.",
    "tags_1_5": "Agrega entre 1 y 5 tags a la nota.",
    "enlaces_min_2": "Incluye mínimo 2 enlaces internos a otras notas del sitio.",
    "enlace_parrafo_1_3": "Pon el primer enlace interno en los primeros 3 párrafos, no hasta el final.",
    "ancla_valida": "Usa texto ancla descriptivo en los enlaces — nada de \"aquí\" o \"clic aquí\".",
    "imagen_alt": "Escribe el alt de la imagen describiendo lo que se ve — no lo dejes vacío o genérico.",
}

ITEMS_EEAT = [
    ("schema_autor_person", "Autor con schema Person", "El JSON-LD del artículo tipa al autor como \"Person\" — identidad formalmente reconocible por Google."),
    ("bio_verificable", "Bio de autor real", "La página /staff/ del periodista tiene una biografía real, no el texto genérico por defecto."),
    ("perfil_social_enlazado", "Perfil social verificable", "El JSON-LD enlaza una red social real del autor (LinkedIn, Instagram, X) — identidad verificable."),
    ("pct_consistencia_tematica", "Consistencia temática (Expertise)", "% del tráfico del periodista concentrado en su sección más fuerte (ene-sep) — publicar dentro de un cluster definido es señal real de expertise."),
]
ITEMS_EEAT_PENDIENTES = [
    ("Atribución explícita de la información", "% de notas con frases como \"según\", \"informó\", \"confirmó\" — necesita analizar el texto completo del cuerpo, no solo las señales que ya se scrapean para el checklist SEO."),
    ("Cita fuentes externas", "% de notas con enlace saliente a un sitio externo real — el scraper actual descarta enlaces externos a propósito (solo cuenta internos para el checklist SEO), habría que sumar esa extracción."),
    ("Actualiza notas publicadas", "% de notas con fecha de actualización posterior a la de publicación — el scraper de septiembre no capturó dateModified todavía, solo datePublished."),
]


def _diagnostico_dificultad(fila):
    dificultad = fila["dificultad_categoria"]
    eficiencia = fila["eficiencia_normalizada"]
    bajo = pd.notna(eficiencia) and eficiencia < 70
    if not bajo:
        return "✅", "Rendimiento saludable", "Tráfico acorde o mejor a lo esperado para la dificultad de esta sección."
    if dificultad == "Fácil":
        return "⚠️", "Revisar al periodista", "Sección fácil pero rendimiento bajo — la sección no es la limitante aquí."
    if dificultad == "Difícil":
        return "ℹ️", "Puede ser la sección", "Sección difícil — el bajo tráfico se explica en parte por eso, no solo por el periodista."
    return "🟡", "Revisar caso a caso", "Rendimiento bajo en una sección de dificultad media."


def _dificultad_header(fila, periodo):
    with st.container(border=True, key="card_dificultad_header"):
        st.markdown('<div class="cp-card-title">Dificultad de la sección</div>', unsafe_allow_html=True)
        badge_color = {"Fácil": "green", "Media": "blue", "Difícil": "red"}[fila["dificultad_categoria"]]
        st.markdown(pill(fila["dificultad_categoria"].upper(), badge_color) +
                    f" &nbsp;{dr.LABELS_SECCION.get(fila['seccion_raw'], fila['seccion_raw'])}",
                    unsafe_allow_html=True)
        icono, titulo, detalle = _diagnostico_dificultad(fila)
        st.markdown(f"{icono} **{titulo}**")
        st.markdown(f'<div class="cp-card-desc">{detalle}</div>', unsafe_allow_html=True)
        trafico_mensual = dr.secciones_trafico_real(periodo).get(fila["seccion_raw"], 0)
        st.caption(f"Tráfico real de la sección ({dr.LABEL_PERIODO.get(periodo, periodo)}): "
                   f"{calc.formatear_numero(trafico_mensual)} vistas · ajuste de eficiencia ×{fila['dificultad_ajuste']:.1f}")


def _fmt(valor, patron="{:.0f}", vacio="s/d"):
    if valor is None or (isinstance(valor, float) and math.isnan(valor)):
        return vacio
    return patron.format(valor)


def _header(meta, ranking=None):
    with st.container(border=True, key="card_header"):
        col_foto, col_info = st.columns([1, 3], vertical_alignment="center")
        with col_foto:
            st.markdown(
                f'<img class="cp-avatar-perfil" src="{avatar_data_uri(meta["nombre"], "#1A1A1A", 320)}">',
                unsafe_allow_html=True,
            )
        with col_info:
            st.markdown(f"### {meta['nombre']}")
            st.markdown(f'<div class="cp-header-beat">{meta.get("seccion","")} · Beat: {meta.get("beat","")}</div>',
                        unsafe_allow_html=True)
            if ranking:
                st.write("")
                _ranking_pill(ranking)


def _ranking_pill(ranking):
    pos, total = ranking
    tercio = max(1, round(total / 3))
    color_key = "green" if pos <= tercio else "red" if pos > total - tercio else "blue"
    st.markdown(pill(f"🏆 #{pos} de {total} este periodo", color_key), unsafe_allow_html=True)


def _trafico(fila, historial):
    serie = historial.sort_values("mes")
    trafico_actual = float(fila["clics"])
    trafico_anterior = float(serie.iloc[-2]["trafico"]) if len(serie) >= 2 else None
    secundario = f"{fila['notas']:.0f} notas · {fila['pct_trafico_total']:.1f}% del tráfico del equipo"
    html_card = trafico_card(calc.formatear_numero(trafico_actual),
                              delta_html(trafico_actual, trafico_anterior), secundario)
    st.markdown(html_card, unsafe_allow_html=True)


def _estado_card(label, color_key, descripcion, key="card_estado"):
    bg = "#DCFCE7" if color_key == "green" else "#FEE2E2" if color_key == "red" else "#DBEAFE"
    with st.container(border=True, key=key):
        st.markdown(
            f'<div style="display:flex;align-items:center;gap:12px;margin-bottom:8px">'
            f'<div style="width:44px;height:44px;min-width:44px;border-radius:50%;'
            f'display:flex;align-items:center;justify-content:center;background:{bg};'
            f'font-size:1.3rem;flex-shrink:0">{ICONO_ESTADO[color_key]}</div>'
            f'<div style="min-width:0"><div class="cp-card-title" style="margin-bottom:2px">ESTADO ACTUAL</div>'
            f'<div style="font-weight:700;font-size:1.15rem;color:{COLOR_ESTADO[color_key]}">{label}</div></div>'
            f'</div>'
            f'<div class="cp-card-desc">{descripcion}</div>',
            unsafe_allow_html=True,
        )


def _estado_actual(fila):
    label, color_key = calc.estado_label(fila["eficiencia_normalizada"], fila["en_alerta"])
    descripciones = {
        "SOBRE MEDIANA": "Rendimiento por encima de la mediana del equipo en el periodo seleccionado.",
        "EN RANGO": "Rendimiento dentro del rango esperado del equipo.",
        "EN ALERTA": "Eficiencia muy por debajo de la mediana del equipo este periodo (aviso de un solo "
                     "periodo — si además hay una racha real de 3+ meses seguidos así, aparece por separado "
                     "en Alertas → Alertas de tendencia).",
    }
    _estado_card(label, color_key, descripciones[label])


def _trafico_historico(historial, nombre_display, meta, periodistas_meta):
    with st.container(border=True, key="card_trafico_historico"):
        col_titulo, col_comparar = st.columns([2, 1])
        n_meses = len(historial)
        with col_titulo:
            st.subheader("Tráfico por mes")
            st.caption(
                f"Tráfico real generado cada mes ({n_meses} meses reales disponibles: ene-sep 2026, septiembre "
                "parcial) — el número bruto, sin ajustar por dificultad de sección."
            )
        otros = [p for p in periodistas_meta if p["slug"] != meta["slug"]]
        with col_comparar:
            comparar_con = st.selectbox("Comparar con", ["Ninguno"] + [p["nombre"] for p in otros],
                                         key="comparar_periodista")

        serie = historial.sort_values("mes")
        if serie.empty:
            st.caption("Sin notas identificadas de este periodista en ningún periodo con censo completo.")
            return
        fig = go.Figure(go.Scatter(
            x=serie["mes_label"], y=serie["trafico"], mode="lines+markers+text",
            line=dict(color="#16A34A", width=3), marker=dict(size=9, color="#16A34A"),
            text=[calc.formatear_numero(v) for v in serie["trafico"]], textposition="top center",
            hovertemplate="%{x}<br>Tráfico: %{y:,.0f}<extra></extra>", name=nombre_display,
        ))

        mostrar_leyenda = comparar_con != "Ninguno"
        if mostrar_leyenda:
            otro_meta = next(p for p in otros if p["nombre"] == comparar_con)
            otro_historial = dr.historial_periodista(otro_meta["nombre"]).sort_values("mes")
            fig.add_trace(go.Scatter(
                x=otro_historial["mes_label"], y=otro_historial["trafico"], mode="lines+markers+text",
                line=dict(color="#F59E0B", width=3, dash="dash"), marker=dict(size=9, color="#F59E0B"),
                text=[calc.formatear_numero(v) for v in otro_historial["trafico"]], textposition="bottom center",
                hovertemplate="%{x}<br>Tráfico: %{y:,.0f}<extra></extra>", name=comparar_con,
            ))

        tickvals, ticktext = list(serie["mes_label"]), list(serie["mes_label"])
        ultima_fila = serie.iloc[-1]
        if dr.mes_es_parcial(ultima_fila["mes"]):
            proyeccion = dr.proyeccion_fin_de_mes(serie, "trafico")
            if proyeccion:
                x_proy = f"{ultima_fila['mes_label']}-proy"
                agregar_proyeccion(fig, proyeccion, x_actual=ultima_fila["mes_label"], x_proyectado=x_proy,
                                    color="#E5152A")
                tickvals.append(x_proy)
                ticktext.append(f"{ultima_fila['mes_label']} (proy.)")

        fig.update_layout(
            height=320, margin=dict(l=10, r=10, t=50, b=10), showlegend=mostrar_leyenda,
            legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0),
            plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
            yaxis=dict(showgrid=True, gridcolor="#E2E6ED", rangemode="tozero"),
            xaxis=dict(type="category", showgrid=False, tickmode="array", tickvals=tickvals, ticktext=ticktext),
        )
        st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})
        proyeccion = dr.proyeccion_fin_de_mes(serie, "trafico") if dr.mes_es_parcial(ultima_fila["mes"]) else None
        if proyeccion:
            st.caption(texto_metodologia_proyeccion(proyeccion))


def _eficiencia_historica(historial, nombre_display):
    with st.container(border=True, key="card_eficiencia"):
        st.subheader("Eficiencia normalizada (índice) en el tiempo")
        st.caption("Datos reales (ene-sep 2026): tráfico ajustado por dificultad de sección de cada mes "
                   "contra la mediana del equipo ese mes = 100.")
        serie = historial.sort_values("mes")
        if serie.empty:
            st.caption("Sin notas identificadas de este periodista.")
            return
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=serie["mes_label"], y=[100] * len(serie), mode="lines",
                                  line=dict(color="#94A3B8", dash="dash", width=1), name="Mediana del equipo (100)"))
        fig.add_trace(go.Scatter(x=serie["mes_label"], y=serie["indice"], mode="lines+markers+text",
                                  line=dict(color="#3457D5", width=3), marker=dict(size=7),
                                  text=[f"{v:.0f}" for v in serie["indice"]], textposition="top center",
                                  name=nombre_display))
        ultima_fila = serie.iloc[-1]
        if dr.mes_es_parcial(ultima_fila["mes"]):
            marcar_mes_parcial(fig, ultima_fila["mes_label"], ultima_fila["indice"])
        fig.update_layout(
            height=320, margin=dict(l=10, r=10, t=10, b=10), showlegend=True,
            legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0),
            plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
            yaxis=dict(showgrid=True, gridcolor="#E2E6ED", rangemode="tozero"),
            xaxis=dict(showgrid=False),
        )
        st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})


VELOCIDAD_LECTURA_PPM = 200


def _metricas_clave(fila):
    engagement = calc.formatear_tiempo(fila["tiempo_pagina_seg"])
    tarjetas = [
        metrica_card("Volumen de notas publicadas", f"{fila['notas']:.0f}",
                     "<span class='cp-delta' style='color:#64748B'>notas del periodo, conteo directo</span>", "📝", "purple"),
        metrica_card("Eficiencia normalizada", f"{fila['eficiencia_normalizada']:.0f}",
                     "<span class='cp-delta' style='color:#64748B'>índice · 100 = mediana del equipo</span>", "📈", "teal"),
        metrica_card("Canal dominante", f"{fila['canal_dominante']}", "", "🔍", "blue"),
        metrica_card("CTR de titulares (real vs. esperado)", _fmt(fila["ctr_indice"], "{:.2f}x"), "", "🎯", "blue"),
        metrica_card("Engagement (tiempo en página)", engagement, "", "👥", "purple"),
        metrica_card("Canibalización interna", "s/d",
                     "<span class='cp-delta' style='color:#94A3B8'>pendiente — necesita detección de "
                     "títulos duplicados, no construida todavía</span>", "🧭", "teal"),
        metrica_card("Extensión promedio (palabras)", _fmt(fila["palabras_promedio"]), "", "📄", "blue"),
        metrica_card("Tiempo de lectura promedio",
                     f"{max(1.0, fila['palabras_promedio']/VELOCIDAD_LECTURA_PPM):.1f} min"
                     if pd.notna(fila["palabras_promedio"]) else "s/d",
                     "<span class='cp-delta' style='color:#64748B'>a 200 palabras/min</span>", "⏱️", "purple"),
        metrica_card("Notas con semáforo SEO verde", _fmt(fila["semaforo_verde_pct"], "{:.0f}%"),
                     f"<span class='cp-delta' style='color:#64748B'>{int(fila['notas_verde'])}🟢 "
                     f"{int(fila['notas_amarillo'])}🟡 {int(fila['notas_rojo'])}🔴</span>"
                     if fila["seo_notas_evaluadas"] else "", "✅", "green"),
    ]
    with st.container(border=True, key="card_metricas"):
        st.subheader("Métricas clave del periodo")
        st.markdown(f'<div class="cp-metric-grid">{"".join(tarjetas)}</div>', unsafe_allow_html=True)


def _posicion_google(historial, meta):
    with st.container(border=True, key="card_posicion"):
        st.subheader(f"Posición promedio en Google — {meta.get('beat','')}")
        serie = historial.sort_values("mes").dropna(subset=["posicion_promedio"])
        if serie.empty:
            st.caption("Sin notas con datos de posición de Search Console en ningún periodo "
                       "(top 1.000 páginas por clics de la UI de GSC, ver banner del Dashboard).")
            return
        fig = go.Figure(go.Scatter(x=serie["mes_label"], y=serie["posicion_promedio"], mode="lines+markers+text",
                                    text=[f"{v:.1f}" for v in serie["posicion_promedio"]], textposition="top center",
                                    line=dict(color="#3457D5", width=3), marker=dict(size=10)))
        ultima_fila = serie.iloc[-1]
        if dr.mes_es_parcial(ultima_fila["mes"]):
            marcar_mes_parcial(fig, ultima_fila["mes_label"], ultima_fila["posicion_promedio"])
        fig.update_layout(
            height=260, margin=dict(l=10, r=10, t=10, b=10),
            yaxis=dict(autorange="reversed", title="Posición", showgrid=True, gridcolor="#E2E6ED"),
            xaxis=dict(showgrid=False), plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
        )
        st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})
        st.caption("↓ Descendente = mejora (menor posición es mejor). Ponderada por impresiones reales de cada nota.")


def _eeat(fila):
    with st.container(border=True, key="card_eeat"):
        st.subheader("Autoridad en Google")
        st.caption("Top 10 y posición en Search Console, de las notas con dato de posición.")
        tarjetas = [
            metrica_card("Notas en Top 10 Google", f"{fila['notas_top10']:.0f}", "", "🏆", "green"),
            metrica_card("Posición promedio", _fmt(fila["posicion_promedio"], "{:.1f}"), "", "🔍", "blue"),
        ]
        st.markdown(f'<div class="cp-metric-grid" style="grid-template-columns:repeat(2,1fr)">'
                    f'{"".join(tarjetas)}</div>', unsafe_allow_html=True)


def _eeat_checklist(fila):
    with st.container(border=True, key="card_eeat_checklist"):
        st.subheader("EEAT — checklist de confianza y autoridad")
        st.caption(
            "Mejor práctica de Google para medios de noticias (Search Quality Rater Guidelines + checklist "
            "de Google News). 4 ítems con dato real (JSON-LD + página /staff/ + distribución real de tráfico "
            "ene-sep); 3 quedan \"s/d\" porque necesitan extender el scraper — ver detalle abajo, nunca "
            "fabricados."
        )
        for clave, titulo, detalle in ITEMS_EEAT:
            valor = fila.get(clave)
            if isinstance(valor, (bool, np.bool_)):
                ok, texto = bool(valor), ("Sí" if valor else "No")
            elif valor is None or (isinstance(valor, float) and pd.isna(valor)):
                ok, texto = None, "s/d"
            else:
                ok, texto = (valor or 0) >= 50, f"{valor:.0f}%"
            icono = "✅" if ok else "⚪" if ok is None else "⚠️"
            st.markdown(f"{icono} **{titulo}** — {texto}")
            st.caption(detalle)
        st.write("")
        for titulo, detalle in ITEMS_EEAT_PENDIENTES:
            st.markdown(f"⚪ **{titulo}** — s/d")
            st.caption(detalle)
        st.write("")
        st.caption(
            "No automatizable, requiere revisión editorial o una herramienta paga que este pipeline no "
            "tiene: precisión factual verificable, evidencia de reporteo propio, diversidad y calidad de "
            "fuentes citadas, objetividad/balance, backlinks y menciones en medios externos."
        )


NOMBRE_COMPONENTE = {
    "eficiencia": "Eficiencia (tráfico ajustado)",
    "ctr": "CTR de titulares (real vs. esperado por posición)",
    "posicion": "Posición promedio en Google",
    "seo": "Cumplimiento del checklist SEO on-page",
}
def _valor_real_eficiencia(f):
    """Texto largo a propósito -- pedido de Edwin (25-ago-2026): mostrar la sección,
    su dificultad y el ajuste explícito, no solo el índice ya calculado, para que
    quede claro CÓMO la dificultad le sube o le baja puntos, no solo el resultado."""
    if pd.isna(f["eficiencia_normalizada"]):
        return "s/d"
    seccion_label = dr.LABELS_SECCION.get(f["seccion_raw"], f["seccion_raw"])
    veces_mediana = f["eficiencia_normalizada"] / 100
    return (
        f"{calc.formatear_numero(f['clics'])} clics reales en **{seccion_label}** "
        f"({f['dificultad_categoria']}, ×{f['dificultad_ajuste']:.1f}) → "
        f"{calc.formatear_numero(f['trafico_ajustado'])} ajustado → índice {f['eficiencia_normalizada']:.0f} "
        f"({veces_mediana:.1f}x la mediana del equipo)"
    )


VALOR_REAL_COMPONENTE = {
    "eficiencia": _valor_real_eficiencia,
    "ctr": lambda f: _fmt(f["ctr_indice"], "{:.2f}x (1.00x = promedio del equipo)"),
    "posicion": lambda f: _fmt(f["posicion_promedio"], "{:.1f} (posición real en Google)"),
    "seo": lambda f: _fmt(f["pct_cumplimiento_prom"], "{:.0f}% del checklist SEO"),
}

ICONO_COMPONENTE = {"eficiencia": "📈", "ctr": "🎯", "posicion": "🔍", "seo": "✅"}
# Orden FIJO siempre igual (no por valor) -- a propósito, para que de un mes a otro
# el mismo componente quede siempre en la misma fila y se pueda comparar de un
# vistazo sin tener que releer las etiquetas cada vez.
ORDEN_COMPONENTES = ["eficiencia", "ctr", "posicion", "seo"]


def _puntaje_rendimiento(fila):
    """Puntaje 0-10 para decidir incentivo mensual -- pedido de la reunión
    "Seguimiento SEO" (24-ago-2026). A propósito NO compara contra otros
    periodistas en esta tarjeta (pedido explícito de Karen en la reunión: "no nos
    gusta que se le esté poniendo al periodista a compararse con él") -- solo
    muestra el número propio y CÓMO se calculó, con datos reales. La comparación
    entre periodistas sigue existiendo como herramienta interna del equipo (ver
    la tabla principal del Dashboard), no en el perfil individual.

    Rediseño 25-ago-2026: Edwin vio la primera versión (lista de texto plano) y
    dijo explícito "no siento que sea fácil de entender por qué sacó ese puntaje"
    -- se reemplaza el bloque de texto por un gráfico de barras (mismo lenguaje
    visual que "¿En qué está fallando el SEO?" más abajo, ya validado en la app)
    + una línea de fórmula con la aritmética real, para que el "por qué" se lea
    de un vistazo, no se deduzca leyendo cuatro líneas de texto."""
    detalle = fila["puntaje_rendimiento_detalle"]
    with st.container(border=True, key="card_puntaje_rendimiento"):
        st.subheader("🎯 Puntaje de rendimiento del periodo")
        st.caption(
            "Combina, con datos reales de este periodo, qué tan bien le fue considerando la dificultad de "
            "su sección (no todos parten con la misma facilidad para generar tráfico) — pensado para decidir "
            "el incentivo mensual, no para compararse contra el resto del equipo."
        )
        if fila["puntaje_rendimiento"] is None:
            st.caption("s/d — sin suficientes componentes con dato real todavía este periodo.")
            return

        puntaje = fila["puntaje_rendimiento"]
        color = "#16A34A" if puntaje >= 7 else "#F59E0B" if puntaje >= 4 else "#DC2626"
        bg = "#DCFCE7" if puntaje >= 7 else "#FEF3C7" if puntaje >= 4 else "#FEE2E2"
        st.markdown(
            f'<div class="cp-card-title">Puntaje (0-10)</div>'
            f'<div style="display:inline-block;background:{bg};color:{color};border-radius:14px;'
            f'padding:6px 22px;font-size:2.6rem;font-weight:800;margin-top:4px">{puntaje:.1f}</div>',
            unsafe_allow_html=True,
        )
        st.write("")

        pesos = detalle["pesos"]
        componentes = detalle["componentes"]
        claves = [k for k in ORDEN_COMPONENTES if componentes.get(k) is not None]
        if claves:
            subs = [componentes[k] for k in claves]
            # La dificultad de sección NO es una barra aparte -- ya está metida adentro
            # de "Eficiencia" (el multiplicador ×0.8/1.0/1.3 se aplica ANTES de calcular
            # el índice). Ponerla como quinta barra con su propio peso la contaría DOS
            # VECES y dejaría de ser justo. En vez de eso, se muestra el badge real de
            # dificultad directo en la etiqueta de Eficiencia -- pedido de Edwin,
            # 25-ago-2026: "que también sea gráfico que consigue buen punto por la
            # dificultad de la sección en la que escribe".
            ICONO_DIFICULTAD = {"Fácil": "🟢", "Media": "🔵", "Difícil": "🔴"}
            badge_dificultad = (
                f" · {ICONO_DIFICULTAD.get(fila['dificultad_categoria'], '⚪')} {fila['dificultad_categoria']} "
                f"×{fila['dificultad_ajuste']:.1f}"
                if pd.notna(fila.get("dificultad_categoria")) else ""
            )
            labels = [
                f"{ICONO_COMPONENTE[k]} {NOMBRE_COMPONENTE[k]} (peso {pesos[k]})"
                + (badge_dificultad if k == "eficiencia" else "")
                for k in claves
            ]
            colores = ["#DC2626" if s < 4 else "#F59E0B" if s < 7 else "#16A34A" for s in subs]
            textos = [f"{s:.1f}/10" for s in subs]
            fig = go.Figure(go.Bar(
                x=subs, y=labels, orientation="h", marker_color=colores, text=textos,
                textposition="outside", textfont=dict(size=16, color="#0F172A"),
                hovertemplate="%{y}<br>%{x:.1f}/10<extra></extra>",
            ))
            fig.update_layout(
                height=max(180, 68 * len(claves)), margin=dict(l=0, r=55, t=6, b=6),
                xaxis=dict(title=None, range=[0, 11.8], showgrid=True, gridcolor="#E2E6ED",
                           tickfont=dict(size=13)),
                yaxis=dict(title=None, automargin=True, autorange="reversed", tickfont=dict(size=14)),
                showlegend=False, plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
                font=dict(size=14),
            )
            st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})
            st.caption(
                "La dificultad de su sección no es una barra aparte: ya está adentro de \"Eficiencia\" "
                "(el ×0.8/×1.0/×1.3 se aplica antes de calcular ese número) — separarla la contaría dos veces."
            )

            # Fórmula real, con la aritmética a la vista -- Edwin, 25-ago-2026: el
            # st.caption (gris, chico) se leía mal -- se reemplaza por un bloque HTML
            # propio, tamaño de cuerpo normal, con cada término separado visualmente
            # en vez de una sola línea densa de texto.
            peso_usado = sum(pesos[k] for k in claves)
            terminos_html = " + ".join(
                f'<span style="white-space:nowrap"><b>{componentes[k]:.1f}</b>×{pesos[k]}</span>' for k in claves
            )
            st.markdown(
                f'<div style="background:#F8FAFC;border-radius:10px;padding:12px 16px;'
                f'font-size:1.05rem;line-height:1.8;margin-top:4px">'
                f'<b>Cómo se sumó:</b><br>({terminos_html}) ÷ {peso_usado} = '
                f'<span style="font-size:1.3rem;font-weight:800;color:{color}">{puntaje:.1f}</span>'
                f'</div>',
                unsafe_allow_html=True,
            )

        st.write("")
        st.markdown("**El dato real detrás de cada barra:**")
        for clave in claves:
            st.caption(f"{ICONO_COMPONENTE[clave]} **{NOMBRE_COMPONENTE[clave]}** — {VALOR_REAL_COMPONENTE[clave](fila)}")
        faltantes = [k for k in ORDEN_COMPONENTES if componentes.get(k) is None]
        if faltantes:
            st.caption(f"s/d este periodo (no cuenta en el cálculo): {', '.join(NOMBRE_COMPONENTE[k] for k in faltantes)}")

        if pd.notna(fila.get("nota_servicio")):
            st.info(f"📋 Nota de servicio (no entra en el cálculo automático): {fila['nota_servicio']}")

        with st.expander("📖 ¿Cómo se calcula exactamente? (tabla de referencia)"):
            st.markdown(
                "**Paso 1 — el tráfico se ajusta por qué tan difícil es su sección** "
                "(según el tráfico mensual real de esa sección, no una opinión):\n\n"
                "| Dificultad | Tráfico mensual de la sección | Ajuste |\n"
                "|---|---|---|\n"
                "| 🟢 Fácil | más de 500K | ×0.8 (se exige más, porque generar tráfico ahí es más fácil) |\n"
                "| 🔵 Media | entre 20K y 500K | ×1.0 (sin ajuste) |\n"
                "| 🔴 Difícil | menos de 20K | ×1.3 (se premia, porque generar tráfico ahí cuesta más) |\n\n"
                "**Paso 2 — cada señal se pasa a una escala de 0 a 10** (nunca se usa el número "
                "crudo directo, para que un mes excepcional de una persona no aplaste la escala "
                "de todo el equipo):\n\n"
                "| Componente | 0/10 | 5/10 (punto neutral) | 10/10 |\n"
                "|---|---|---|---|\n"
                "| Eficiencia | tráfico ajustado ≈0 | igual a la mediana del equipo (índice 100) | ~4.6x la mediana o más |\n"
                "| CTR de titulares | 1.5x por debajo de lo esperado | exactamente lo esperado por su posición | 1.0x por encima de lo esperado |\n"
                "| Posición en Google | posición 20 o peor | — | posición 1 |\n"
                "| Checklist SEO | 0% de cumplimiento | 50% | 100% de cumplimiento |\n\n"
                "**Paso 3 — se combinan con su peso** (peso más alto = pesa más en el total):\n\n"
                + "\n".join(f"- **{NOMBRE_COMPONENTE[k]}**: peso {v} de {sum(pesos.values())}"
                             for k, v in pesos.items()) +
                "\n\nNi el número de notas ni las tareas de servicio (ej. mantener tablas de posiciones) "
                "entran en esta fórmula — a propósito, no todos producen la misma cantidad de contenido "
                "firmable."
            )


def _cumplimiento_seo(fila):
    with st.container(border=True, key="card_seo"):
        st.caption("Cumplimiento SEO promedio (13 ítems automatizados)")
        st.markdown(card_value("", _fmt(fila["pct_cumplimiento_prom"], "{:.0f}%", "s/d — sin notas evaluadas")),
                    unsafe_allow_html=True)
        if fila["seo_notas_evaluadas"]:
            st.caption("Notas por semáforo (umbral 80% / 60%):")
            st.markdown(f"🟢 **{int(fila['notas_verde'])}**&nbsp;&nbsp;"
                        f"🟡 **{int(fila['notas_amarillo'])}**&nbsp;&nbsp;"
                        f"🔴 **{int(fila['notas_rojo'])}**", unsafe_allow_html=True)
            evaluadas, total = int(fila["seo_notas_evaluadas"]), int(fila["notas"])
            if evaluadas >= total:
                st.caption(f"Las {total} notas del periodo fueron evaluadas a fondo con el checklist SEO completo.")
        else:
            st.caption("Semáforo SEO real solo corrido para septiembre 2026 por ahora.")


def _diagnostico_seo(fila):
    with st.container(border=True, key="card_diagnostico_seo"):
        st.subheader("¿En qué está fallando el SEO? — desglose por ítem")
        desglose = fila.get("seo_desglose_items") or {}
        if not desglose:
            st.caption("Sin semáforo SEO real corrido para este periodo todavía.")
            return
        st.caption(f"% sobre las {int(fila['seo_notas_evaluadas'])} notas reales evaluadas, de peor a mejor.")

        etiquetas = {
            "h1_70_170": "H1 editorial (70-170 car.)", "title_50_65": "Title SEO (50-65 car.)",
            "meta_desc_150_170": "Meta descripción (150-170 car.)", "meta_desc_no_repite_h1": "Meta no repite H1",
            "primer_parrafo_180": "Primer párrafo ≥180 car.", "h2_estructura": "Estructura de H2",
            "extension_400": "Extensión ≥400 palabras", "tags_1_5": "Tags (1-5)",
            "enlaces_min_2": "Enlaces internos (≥2)", "enlace_parrafo_1_3": "Primer enlace en párrafos 1-3",
            "ancla_valida": "Texto ancla válido", "imagen_alt": "Imagen con alt válido",
        }
        items_ordenados = sorted(desglose.items(), key=lambda kv: kv[1]["pct_cumple"])
        en_pantalla = list(reversed(items_ordenados))
        colores = ["#DC2626" if v["pct_cumple"] < 50 else "#F59E0B" if v["pct_cumple"] < 80 else "#16A34A"
                   for _, v in en_pantalla]
        textos = [f"{v['pct_cumple']:.0f}%" for _, v in en_pantalla]
        fig = go.Figure(go.Bar(
            x=[v["pct_cumple"] for _, v in en_pantalla], y=[etiquetas.get(k, k) for k, _ in en_pantalla],
            orientation="h", marker_color=colores, text=textos, textposition="outside",
            hovertemplate="%{y}<br>Cumplimiento: %{x:.0f}%<extra></extra>",
        ))
        fig.update_layout(
            height=max(320, 26 * len(en_pantalla)), margin=dict(l=0, r=40, t=10, b=10),
            xaxis=dict(title=None, range=[0, 108], showgrid=True, gridcolor="#E2E6ED"),
            yaxis_title=None, showlegend=False,
            plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
            yaxis=dict(automargin=True),
        )
        st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})
        peores = [etiquetas.get(k, k) for k, _ in items_ordenados[:3]]
        st.caption(f"🔴 Sus 3 puntos más débiles: {'; '.join(peores)}.")

        pendientes = [(k, v) for k, v in items_ordenados if v["pct_cumple"] < 80]
        st.write("")
        st.markdown("**Qué debe mejorar — instrucciones concretas**")
        if not pendientes:
            st.success("Cumple con 80%+ del checklist en todos los ítems evaluados. Nada urgente que corregir.")
            return
        filas = []
        for k, v in pendientes:
            pct = v["pct_cumple"]
            severidad = "🔴 Nunca lo hace" if pct == 0 else "🔴 Rara vez" if pct < 50 else "🟡 A veces"
            filas.append({
                "Ítem": etiquetas.get(k, k), "Cumplimiento": f"{pct:.0f}%", "Frecuencia": severidad,
                "Qué hacer": ACCION_ITEM_SEO.get(k, "Revisar este punto del checklist SEO."),
            })
        st.dataframe(
            pd.DataFrame(filas), hide_index=True, width="stretch",
            column_config={
                "Ítem": st.column_config.TextColumn(width="medium"),
                "Cumplimiento": st.column_config.TextColumn(width="small"),
                "Frecuencia": st.column_config.TextColumn(width="small"),
                "Qué hacer": st.column_config.TextColumn(width="large"),
            },
        )


def _rendimiento_por_seccion(meta):
    with st.container(border=True, key="card_entidades_fuertes"):
        st.subheader("En qué secciones le rinde escribir")
        st.caption(
            "Tráfico/nota real por sección, combinando ene-sep 2026 (9 meses de censo completo). "
            "Confianza: 🟢 alta (≥10 notas) · 🟡 media "
            "(3-9) · ⚪ baja (<3, indicativo)."
        )
        df = dr.rendimiento_por_seccion(meta["nombre"])
        if df.empty:
            st.caption("Sin datos suficientes para calcular rendimiento por sección.")
            return
        icono_conf = {"alta": "🟢", "media": "🟡", "baja": "⚪"}
        badge_dificultad = {"Fácil": "green", "Media": "blue", "Difícil": "red"}
        for _, r in df.iterrows():
            label = dr.LABELS_SECCION.get(r["seccion"], r["seccion"].title())
            icono = icono_conf.get(r["confianza"], "⚪")
            dif_categoria = "—"
            trafico_seccion = dr.secciones_trafico_real().get(r["seccion"])
            if trafico_seccion is not None:
                dif_categoria, _ = calc.categoria_dificultad(trafico_seccion)
            dif_color = badge_dificultad.get(dif_categoria, "blue")
            st.markdown(
                f"{icono} **{label}** &nbsp; " + pill(dif_categoria.upper(), dif_color) +
                f" — {r['trafico_por_nota']:,.0f} tráfico/nota ({int(r['notas'])} notas en ene-sep)".replace(",", "."),
                unsafe_allow_html=True,
            )
            st.write("")


def _entidades_y_temas(meta):
    autor = meta["nombre"]
    entidades = dr.entidades_periodista(autor)
    recomendados = dr.temas_recomendados(autor)
    with st.container(border=True, key="card_entidades_temas"):
        st.subheader("Temas y entidades en los que le rinde")
        st.caption(
            "Extraído en automático del título real de cada nota (9 meses ene-sep 2026) — 🏷️ entidad "
            "(persona/equipo/torneo/lugar identificable) · 📌 tema (frase recurrente, no una entidad "
            "única). Vigencia (¿sigue generando tráfico HOY o ya se enfrió?) todavía no disponible: "
            "necesita una serie diaria real de Search Console que el exportador automático recién "
            "empezó a acumular el 22-ago-2026 — se activa sola en cuanto haya suficiente historia."
        )
        if entidades.empty:
            st.caption("Sin entidades/temas detectados para este periodista todavía.")
        else:
            top = entidades.sort_values("trafico", ascending=False).head(10)
            icono_tipo = {"entidad": "🏷️", "tema": "📌"}
            icono_conf = {"alta": "🟢", "media": "🟡", "baja": "⚪"}
            filas_html = []
            for r in top.itertuples():
                filas_html.append(
                    f'<div style="display:flex;justify-content:space-between;align-items:center;'
                    f'padding:6px 4px;border-bottom:1px solid #E2E6ED">'
                    f'<div>{icono_tipo.get(r.tipo,"•")} <b>{r.entidad}</b> '
                    f'<span style="color:#94A3B8;font-size:0.85rem">{icono_conf.get(r.confianza,"⚪")}</span></div>'
                    f'<div style="text-align:right;color:#64748B;font-size:0.9rem">'
                    f'{int(r.notas)} notas · {calc.formatear_numero(r.trafico)} tráfico</div></div>'
                )
            st.markdown("".join(filas_html), unsafe_allow_html=True)

        st.write("")
        st.markdown("**🎯 Temas recomendados** — patrón real de volver sobre el tema en ≥3 meses distintos, "
                    "con demanda todavía cerca de su pico histórico (no una coyuntura ya cerrada)")
        if recomendados.empty:
            st.caption("Ningún tema de este periodista cumple todavía el patrón de recurrencia real "
                       "(≥3 meses activos + demanda reciente ≥10% del pico).")
        else:
            for r in recomendados.head(6).itertuples():
                icono = "🏷️" if r.tipo == "entidad" else "📌"
                st.markdown(f"{icono} **{r.entidad}** — {int(r.meses_activos)} meses activos, "
                            f"demanda reciente {r.demanda_reciente_ratio:.0%} de su pico")


def _pipeline_pendiente():
    with st.container(border=True, key="card_pipeline_pendiente"):
        st.subheader("Pendiente — todavía no construido")
        st.caption(
            "El dato base (roster, tráfico, Search Console, entidades/temas) ya tiene 9 meses reales de "
            "censo completo (ene-sep 2026). Lo que sigue pendiente necesita un análisis distinto, no más "
            "historial:"
        )
        st.markdown(
            "- **Qué ecuación de titular le rinde** — necesita comparar tráfico \"con vs. sin\" cada rasgo "
            "estructural del titular, con muestra mínima de 10 notas por rasgo.\n"
            "- **Canibalización interna** — necesita detección de títulos muy similares entre notas propias."
        )


def _notas_destacadas(df_notas, slug):
    with st.container(border=True, key="card_notas_destacadas"):
        st.subheader("Notas más vistas del periodo")
        st.caption("De dónde salió el tráfico: ranking de notas individuales con más clics. "
                   "🟢🟡🔴 = semáforo SEO real (septiembre) · ⚪ = sin evaluar. Posición Google real cuando hay dato.")
        propias = df_notas[df_notas["slug"] == slug].sort_values("clics", ascending=False).reset_index(drop=True)
        if propias.empty:
            st.caption("No hay notas registradas para este periodista en el periodo.")
            return
        top = propias.head(10)
        pct_max = top["pct_del_total"].max()
        filas_html = []
        for i, n in enumerate(top.itertuples(), start=1):
            pos_txt = f"{n.posicion_promedio:.0f}" if pd.notna(n.posicion_promedio) else "s/d"
            meta = f"{dr.LABELS_SECCION.get(n.seccion, n.seccion)} · Posición Google {pos_txt}"
            filas_html.append(nota_row(
                rank=i, titulo=n.titulo, meta=meta,
                clics_txt=calc.formatear_numero(n.clics), pct_txt=f"{n.pct_del_total:.1f}%",
                barra_pct=100 * n.pct_del_total / pct_max if pct_max else 0,
                semaforo=n.semaforo,
            ))
        st.markdown(f'<div class="cp-nota-list">{"".join(filas_html)}</div>', unsafe_allow_html=True)


def render(tabla, df_notas, slug: str, periodo=None):
    periodo = periodo or dr.PERIODO_COMPLETO
    periodistas_meta = dr.cargar_periodistas_meta()
    meta_por_slug = {p["slug"]: p for p in periodistas_meta}
    if slug not in meta_por_slug:
        slug = periodistas_meta[0]["slug"]
    meta = dict(meta_por_slug[slug])

    fila = tabla[tabla["slug"] == slug]
    if fila.empty:
        st.warning(f"{meta['nombre']} no tiene notas en el periodo seleccionado — cambia de periodo o de periodista.")
        return
    fila = fila.iloc[0]
    meta["seccion"] = dr.LABELS_SECCION.get(fila["seccion_raw"], fila["seccion_raw"])
    meta["beat"] = fila["beat"]

    st.markdown(info_banner(
        "Perfil real: roster, tráfico, engagement, Search Console y semáforo SEO (septiembre) son datos reales. "
        "Historial de 9 meses (ene-sep 2026), censo completo. "
        "Temas/entidades, ecuación de titulares y canibalización necesitan un pipeline nuevo (ver tarjeta "
        "\"Pendiente\" más abajo) — nunca fabricados."
    ), unsafe_allow_html=True)

    historial = dr.historial_periodista(fila["autor"])
    ranking = dr.ranking_periodista(fila["autor"], periodo)

    col_header, col_trafico, col_estado, col_dificultad = st.columns([1.5, 0.9, 1.05, 1.1], vertical_alignment="top")
    with col_header:
        _header(meta, ranking)
    with col_trafico:
        _trafico(fila, historial)
    with col_estado:
        _estado_actual(fila)
    with col_dificultad:
        _dificultad_header(fila, periodo)
    st.write("")

    _puntaje_rendimiento(fila)
    st.write("")

    _trafico_historico(historial, fila["periodista"], meta, periodistas_meta)
    st.write("")

    col_izq, col_der = st.columns([1.3, 1])
    with col_izq:
        _eficiencia_historica(historial, fila["periodista"])
    with col_der:
        _metricas_clave(fila)

    st.write("")
    _posicion_google(historial, meta)

    st.write("")
    col_eeat, col_seo = st.columns(2)
    with col_eeat:
        _eeat(fila)
    with col_seo:
        _cumplimiento_seo(fila)

    st.write("")
    _eeat_checklist(fila)

    st.write("")
    _diagnostico_seo(fila)

    st.write("")
    _rendimiento_por_seccion(meta)

    st.write("")
    _entidades_y_temas(meta)

    st.write("")
    _pipeline_pendiente()

    st.write("")
    _notas_destacadas(df_notas, slug)
