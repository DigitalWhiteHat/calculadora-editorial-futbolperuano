"""Vista general — desempeño editorial de todo el equipo.

Espejo de calculadora-periodistas/app/general.py (colombia.com), con el núcleo que
ya corre sobre datos REALES (roster + GA4 + canal) para julio y agosto 2026, más
tendencia real del portal ene-ago. Quedan pendientes para cuando haya más
historial: advertencias de declive y minería de patrones de titulares (ver
datos_reales.py y memoria futbolperuano-app-fase1-estado.md)."""

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import calculos as calc
import datos_reales as dr
from avatares import avatar_data_uri
from estilos import BG_ESTADO, TXT_ESTADO, info_banner, kpi_card, seccion_dificultad_row
from graficos import agregar_proyeccion, texto_metodologia_proyeccion

COLOR_ESTADO = {"green": "#16A34A", "blue": "#3457D5", "red": "#DC2626"}
ESTADO_STYLE = {
    label: f"background-color:{BG_ESTADO[key]};color:{TXT_ESTADO[key]};font-weight:600;border-radius:6px"
    for label, key in [("SOBRE MEDIANA", "green"), ("EN RANGO", "blue"), ("EN ALERTA", "red")]
}


def _kpis(tabla):
    notas_total = tabla["notas"].sum()
    trafico_total = tabla["clics"].sum()
    # Mediana, no promedio: eficiencia_normalizada no tiene tope, así que un periodista
    # muy por encima del resto arrastraría la MEDIA a un número que no representa al
    # equipo. La mediana es robusta a ese outlier y, por diseño del índice (100 =
    # mediana del equipo), debería rondar 100.
    eficiencia_mediana = tabla["eficiencia_normalizada"].median()
    en_alerta = int(tabla["en_alerta"].sum())
    canal_top = tabla.groupby("canal_dominante")["clics"].sum().idxmax() if len(tabla) else "—"

    tarjetas = [
        kpi_card("👥", "Periodistas activos", f"{len(tabla)}"),
        kpi_card("⚠️", "En alerta", f"{en_alerta}", help_text="Periodistas con eficiencia muy por debajo de la "
                  "mediana del equipo este periodo."),
        kpi_card("📈", "Eficiencia mediana", f"{eficiencia_mediana:.0f}" if len(tabla) else "—",
                  help_text="Índice comparativo, no un porcentaje ni un conteo: 100 = mediana del equipo. "
                  "Tráfico ajustado por dificultad de sección, relativo al resto del equipo."),
        kpi_card("📝", "Notas totales", f"{notas_total:.0f}"),
        kpi_card("🔎", "Tráfico total", calc.formatear_numero(trafico_total)),
        kpi_card("📡", "Canal dominante del portal", canal_top),
    ]
    st.markdown(f'<div class="cp-kpi-row">{"".join(tarjetas)}</div>', unsafe_allow_html=True)


def _explicacion_eficiencia(tabla):
    mediana = tabla["trafico_ajustado"].median()
    ref = tabla.iloc[(tabla["trafico_ajustado"] - mediana).abs().argsort()[:1]].iloc[0]
    top = tabla.sort_values("eficiencia_normalizada", ascending=False).iloc[0]
    with st.expander("ℹ️ ¿Qué significa \"eficiencia normalizada\"? (no es el número de notas)", expanded=False):
        st.markdown(
            "Es un **índice comparativo**, no un porcentaje ni un conteo de notas. Compara el tráfico "
            "de cada periodista (ajustado por qué tan competida es su sección) contra la **mediana del "
            "equipo del periodo**.\n\n"
            "- **100** = tráfico igual a la mediana del equipo\n"
            "- **200** = el doble de la mediana\n"
            "- **50** = la mitad de la mediana\n\n"
            f"**Con los datos de este periodo:** la mediana de tráfico ajustado del equipo fue "
            f"**{calc.formatear_numero(mediana)}**. {ref['periodista']} tuvo prácticamente esa misma cifra, "
            f"por eso su índice es {ref['eficiencia_normalizada']:.0f} (≈100). {top['periodista']} generó "
            f"{calc.formatear_numero(top['trafico_ajustado'])} — por eso su índice es "
            f"{top['eficiencia_normalizada']:.0f}."
        )


def _aporte_trafico(tabla):
    st.subheader("Aporte de tráfico por periodista")
    ordenado = tabla.sort_values("clics", ascending=True)
    colores = [COLOR_ESTADO[calc.estado_label(r.eficiencia_normalizada, r.en_alerta)[1]] for r in ordenado.itertuples()]
    textos = [f"{calc.formatear_numero(v)} · {p:.1f}%" for v, p in zip(ordenado["clics"], ordenado["pct_trafico_total"])]

    fig = go.Figure(go.Bar(
        x=ordenado["clics"], y=ordenado["periodista"], orientation="h",
        marker_color=colores, text=textos, textposition="outside",
        hovertemplate="%{y}<br>Tráfico: %{x:,.0f}<extra></extra>",
    ))
    fig.update_layout(
        height=max(280, 34 * len(ordenado)), margin=dict(l=0, r=60, t=10, b=10),
        xaxis_title=None, yaxis_title=None, showlegend=False,
        plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
        xaxis=dict(showgrid=True, gridcolor="#E2E6ED"),
        yaxis=dict(automargin=True),
    )
    st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})
    st.caption(f"Tráfico total del periodo: **{calc.formatear_numero(tabla['clics'].sum())}**")


def _notas_por_periodista(tabla):
    st.subheader("Notas publicadas por periodista")
    st.caption("Cuántas notas hizo cada quien en el periodo — dato bruto, sin ajustar.")
    ordenado = tabla.sort_values("notas", ascending=True)
    colores = [COLOR_ESTADO[calc.estado_label(r.eficiencia_normalizada, r.en_alerta)[1]] for r in ordenado.itertuples()]

    fig = go.Figure(go.Bar(
        x=ordenado["notas"], y=ordenado["periodista"], orientation="h",
        marker_color=colores, text=ordenado["notas"].astype(int).astype(str), textposition="outside",
        hovertemplate="%{y}<br>Notas: %{x}<extra></extra>",
    ))
    fig.update_layout(
        height=max(280, 34 * len(ordenado)), margin=dict(l=0, r=40, t=10, b=10),
        xaxis_title=None, yaxis_title=None, showlegend=False,
        plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
        xaxis=dict(showgrid=True, gridcolor="#E2E6ED"),
        yaxis=dict(automargin=True),
    )
    st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})
    st.caption(f"Notas totales del periodo: **{int(tabla['notas'].sum())}**")


def _cuadrante(tabla):
    st.subheader("Volumen de notas vs. eficiencia normalizada")
    st.caption("Cada punto representa a un periodista. Haz clic en un punto para ver su perfil.")

    x = tabla["notas"].to_numpy(dtype=float)
    y_real = tabla["eficiencia_normalizada"].to_numpy(dtype=float)
    # Escala logarítmica en Y: eficiencia_normalizada no tiene tope, así que un outlier
    # real deja el resto de puntos pegados al piso en escala lineal.
    y = np.log10(np.clip(y_real, 1, None))
    x_mid = float(np.median(x))
    y_mid = np.log10(100.0)
    x_range = (0, max(x.max() * 1.25, x_mid * 2, 1))
    y_range = (0, max(y.max() * 1.15, np.log10(300)))

    ticks_candidatos = [10, 25, 50, 100, 250, 500, 1000, 2500, 5000, 10000, 25000, 50000, 100000]
    tickvals = [np.log10(t) for t in ticks_candidatos if y_range[0] <= np.log10(t) <= y_range[1]]
    ticktext = [calc.formatear_numero(t) for t in ticks_candidatos if y_range[0] <= np.log10(t) <= y_range[1]]

    fig = go.Figure()
    zonas = [
        (x_range[0], x_mid, y_mid, y_range[1], "#FEF3C7", "ALTA EFICIENCIA · BAJO VOLUMEN"),
        (x_mid, x_range[1], y_mid, y_range[1], "#DCFCE7", "ZONA IDEAL · ALTA EFICIENCIA Y VOLUMEN"),
        (x_range[0], x_mid, y_range[0], y_mid, "#F1F5F9", "BAJA EFICIENCIA · BAJO VOLUMEN"),
        (x_mid, x_range[1], y_range[0], y_mid, "#FEE2E2", "ZONA DE REVISIÓN · ALTO VOLUMEN, BAJA EFICIENCIA"),
    ]
    for x0, x1, y0, y1, color, _ in zonas:
        fig.add_shape(type="rect", x0=x0, x1=x1, y0=y0, y1=y1, fillcolor=color, opacity=0.5, line_width=0, layer="below")
    for x0, x1, y0, y1, _, label in zonas:
        fig.add_annotation(x=(x0 + x1) / 2, y=y1 - (y_range[1] * 0.04), text=label, showarrow=False,
                            font=dict(size=10, color="#64748B"), xanchor="center")

    fig.add_shape(type="line", x0=x_mid, x1=x_mid, y0=y_range[0], y1=y_range[1], line=dict(color="#94A3B8", dash="dash", width=1))
    fig.add_shape(type="line", x0=x_range[0], x1=x_range[1], y0=y_mid, y1=y_mid, line=dict(color="#94A3B8", dash="dash", width=1))

    # Marcador transparente: la zona de fondo ya comunica el cuadrante y el aro de color
    # taparía el avatar -- solo existe para que el clic/hover funcione.
    fig.add_trace(go.Scatter(
        x=x, y=y, mode="markers", marker=dict(size=34, color="rgba(0,0,0,0)"),
        customdata=np.stack([tabla["slug"], y_real], axis=-1), text=tabla["periodista"],
        hovertemplate="%{text}<br>Notas: %{x}<br>Eficiencia: %{customdata[1]:.0f}<extra></extra>",
    ))

    factor_densidad = min(1.0, (7 / max(len(tabla), 1)) ** 0.5)
    sizex = (x_range[1] - x_range[0]) * 0.075 * factor_densidad
    sizey = (y_range[1] - y_range[0]) * 0.15 * factor_densidad
    for r, y_log in zip(tabla.itertuples(), y):
        fig.add_layout_image(dict(
            source=avatar_data_uri(r.periodista, "#1A1A1A", 96), xref="x", yref="y",
            x=r.notas, y=y_log, sizex=sizex, sizey=sizey,
            xanchor="center", yanchor="middle", layer="above",
        ))

    fig.update_layout(
        height=440, margin=dict(l=10, r=10, t=30, b=10),
        xaxis=dict(title="Volumen de notas publicadas (periodo)", range=x_range, showgrid=True,
                    gridcolor="#E2E6ED", automargin=True),
        yaxis=dict(title="Eficiencia normalizada (índice, escala log)", range=y_range,
                    tickvals=tickvals, ticktext=ticktext, showgrid=True, gridcolor="#E2E6ED", automargin=True),
        plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)", showlegend=False,
    )

    event = st.plotly_chart(fig, width="stretch", on_select="rerun", selection_mode="points",
                             key="cuadrante_scatter", config={"displayModeBar": False})
    puntos = event.get("selection", {}).get("points", []) if event else []
    if puntos and "customdata" in puntos[0]:
        return puntos[0]["customdata"][0]
    return None


def _selector_perfil(tabla):
    orden = tabla.sort_values("clics", ascending=False)
    col_txt, col_sel, col_btn = st.columns([2, 2, 1])
    col_txt.subheader("Detalle por periodista")
    nombre = col_sel.selectbox("Ver perfil de periodista", orden["periodista"], label_visibility="collapsed")
    if col_btn.button("Ver perfil →", width="stretch"):
        return orden.loc[orden["periodista"] == nombre, "slug"].iloc[0]
    return None


def _tabla_principal(tabla):
    st.caption("O haz clic en una fila de la tabla / un punto del cuadrante para ver su perfil.")
    st.caption(
        "**Semáforo SEO** = % de cumplimiento del checklist on-page sobre las notas evaluadas de cada "
        "periodista: 🟢 80% o más · 🟡 entre 60% y 79% · 🔴 menos de 60%."
    )
    vista = tabla.copy().sort_values("clics", ascending=False).reset_index(drop=True)
    vista["foto"] = [avatar_data_uri(n, "#1A1A1A", 64) for n in vista["periodista"]]
    vista["seccion_beat"] = vista["seccion"].map(dr.LABELS_SECCION) + " · " + vista["beat"]
    # Pedido de Edwin (25-ago-2026): que se vea explícito en qué sección escribe y su
    # dificultad, conectado a que eso le sube/baja puntos -- ícono + ajuste real,
    # no solo el nombre de la sección.
    ICONO_DIFICULTAD = {"Fácil": "🟢", "Media": "🔵", "Difícil": "🔴"}
    vista["dificultad_txt"] = vista.apply(
        lambda r: f"{ICONO_DIFICULTAD.get(r['dificultad_categoria'], '⚪')} {r['dificultad_categoria']} "
                  f"(×{r['dificultad_ajuste']:.1f})", axis=1)
    vista["eficiencia_delta"] = vista.apply(
        lambda r: calc.formatear_delta_pct(r["eficiencia_normalizada"], r["eficiencia_normalizada_anterior"]) or "—",
        axis=1)
    vista["engagement"] = vista["tiempo_pagina_seg"].apply(calc.formatear_tiempo)
    vista["semaforo"] = vista["pct_cumplimiento_prom"].apply(
        lambda v: "⚪ s/e" if pd.isna(v) else f"{'🟢' if v >= 80 else '🟡' if v >= 60 else '🔴'} {v:.0f}%")
    vista["estado_txt"] = vista.apply(lambda r: calc.estado_label(r["eficiencia_normalizada"], r["en_alerta"])[0], axis=1)
    vista["trafico_txt"] = vista["clics"].apply(calc.formatear_numero)
    vista["pct_trafico_txt"] = vista["pct_trafico_total"].apply(lambda v: f"{v:.1f}%")
    vista["posicion_txt"] = vista["posicion_promedio"].apply(lambda v: "s/d" if pd.isna(v) else f"{v:.1f}")
    vista["ctr_indice_txt"] = vista["ctr_indice"].apply(lambda v: "s/d" if pd.isna(v) else f"{v:.2f}")

    columnas = ["foto", "periodista", "seccion_beat", "dificultad_txt", "notas", "eficiencia_normalizada",
                "eficiencia_delta", "puntaje_rendimiento", "trafico_txt", "pct_trafico_txt", "canal_dominante",
                "posicion_txt", "ctr_indice_txt", "engagement", "semaforo", "flags_ia", "estado_txt"]
    styled = vista[columnas].style.map(lambda v: ESTADO_STYLE.get(v, ""), subset=["estado_txt"])
    event = st.dataframe(
        styled, hide_index=True, width="stretch", on_select="rerun",
        selection_mode="single-row", key="tabla_periodistas",
        column_config={
            "foto": st.column_config.ImageColumn("", width="small"),
            "periodista": st.column_config.TextColumn("Periodista", width="medium"),
            "seccion_beat": st.column_config.TextColumn("Sección / Beat", width="medium"),
            "dificultad_txt": st.column_config.TextColumn(
                "Dificultad de su sección", width="small",
                help="🟢 Fácil (×0.8) · 🔵 Media (×1.0) · 🔴 Difícil (×1.3) -- según el tráfico mensual real "
                "de la sección. El ajuste ya está aplicado en la columna Eficiencia y en el Puntaje: escribir "
                "en una sección difícil suma puntos, no los resta."),
            "notas": st.column_config.NumberColumn("Notas", width="small",
                                                     help="Número de notas publicadas en el periodo (dato bruto)"),
            "eficiencia_normalizada": st.column_config.NumberColumn(
                "Eficiencia", format="%.0f", width="small",
                help="Índice comparativo (100 = mediana del equipo), no un conteo de notas ni un porcentaje"),
            "eficiencia_delta": st.column_config.TextColumn("Δ vs. periodo ant.", width="small"),
            "puntaje_rendimiento": st.column_config.NumberColumn(
                "Puntaje (0-10)", format="%.1f", width="small",
                help="Herramienta interna del equipo, para decidir el incentivo mensual -- NO se muestra en "
                "el perfil de cada periodista comparado contra otros (pedido de Karen, reunión 24-ago-2026). "
                "Combina eficiencia ajustada por dificultad + CTR índice + posición SERP + cumplimiento SEO."),
            "trafico_txt": st.column_config.TextColumn("Tráfico", width="small"),
            "pct_trafico_txt": st.column_config.TextColumn("% del medio", width="small"),
            "canal_dominante": st.column_config.TextColumn("Canal", width="small"),
            "posicion_txt": st.column_config.TextColumn("Posición SERP", width="small",
                                                          help="Posición promedio real en Google Search Console. "
                                                          "s/d = sin notas en el top 1.000 páginas de GSC (tope de la plataforma)"),
            "ctr_indice_txt": st.column_config.TextColumn("CTR índice", width="small",
                                                            help="CTR real vs. el esperado para su posición (Search Console). "
                                                            "1.00 = promedio del equipo; por debajo, su CTR rinde menos de lo que la posición predeciría"),
            "engagement": st.column_config.TextColumn("Engagement", width="small"),
            "semaforo": st.column_config.TextColumn("Semáforo SEO", width="small"),
            "flags_ia": st.column_config.NumberColumn("Flags IA", width="small"),
            "estado_txt": st.column_config.TextColumn("Estado", width="medium"),
        },
    )
    filas = event.get("selection", {}).get("rows", []) if event else []
    if filas:
        return vista.iloc[filas[0]]["slug"]
    return None


def _dificultad_canal_secciones(periodo):
    st.subheader("Dificultad y canal por sección")
    nota_parcial = (
        " Agosto es un mes parcial (22 de 31 días) — proyectado a mes completo con una regla de tres simple."
        if dr.mes_es_parcial(periodo) else " Julio es un mes cerrado — el tráfico no necesita proyección."
    )
    st.caption(
        "Qué tan fácil es generar tráfico en cada sección (🟢 Fácil >500K/mes · 🔵 Media 20K-500K/mes · "
        "🔴 Difícil <20K/mes) y qué canal le aporta más. Tráfico real de GA4." + nota_parcial
    )
    df = dr.secciones_dificultad_canal(periodo)
    filas_html = [
        seccion_dificultad_row(
            dr.LABELS_SECCION.get(r.seccion, r.seccion.title()), r.dificultad_categoria,
            dr.ICONO_CANAL.get(r.canal_dominante, "🔗"), r.canal_dominante,
            r.pct_canal_dominante, calc.formatear_numero(r.trafico_total),
        )
        for r in df.itertuples()
    ]
    st.markdown("".join(filas_html), unsafe_allow_html=True)


def _tendencia_portal():
    por_mes = dr.trafico_real_por_mes()
    n_meses = len(por_mes)
    rango_txt = f"{dr.MES_LARGO.get(por_mes['mes'].iloc[0], '')}-{dr.MES_LARGO.get(por_mes['mes'].iloc[-1], '')} 2026"
    st.subheader(f"Tendencia del portal — {n_meses} meses ({rango_txt})")
    st.caption(
        "Tráfico TOTAL real reportado por GA4 cada mes (todo el portal). Enero-agosto son meses "
        "cerrados; septiembre es el mes en curso (línea punteada = proyección de cierre, no dato real)."
    )
    por_mes["label"] = por_mes["mes"].map(lambda m: dr.MES_CORTO.get(m, m))

    fig = go.Figure(go.Scatter(
        x=por_mes["mes"], y=por_mes["trafico"], mode="lines+markers+text",
        line=dict(color="#E5152A", width=3), marker=dict(size=9, color="#E5152A"),
        text=[calc.formatear_numero(v) for v in por_mes["trafico"]], textposition="top center",
        hovertemplate="%{x}<br>Tráfico: %{y:,.0f}<extra></extra>",
    ))

    tickvals, ticktext = list(por_mes["mes"]), list(por_mes["label"])
    proyeccion = dr.proyeccion_fin_de_mes(por_mes, "trafico")
    if proyeccion:
        ultimo_mes = por_mes["mes"].iloc[-1]
        x_proy = f"{ultimo_mes}-proy"
        agregar_proyeccion(fig, proyeccion, x_actual=ultimo_mes, x_proyectado=x_proy, color="#E5152A")
        tickvals.append(x_proy)
        ticktext.append(f"{dr.MES_CORTO.get(ultimo_mes, ultimo_mes)} (proy.)")

    fig.update_layout(
        height=340, margin=dict(l=0, r=10, t=50, b=10),
        # type="category" es necesario: "2026-08" parece fecha y sin esto Plotly infiere un
        # eje de fechas -- la categoría sintética "2026-08-proy" no es una fecha válida y el
        # punto se descarta en silencio.
        xaxis=dict(type="category", tickmode="array", tickvals=tickvals, ticktext=ticktext),
        yaxis_title=None, showlegend=False,
        plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
        yaxis=dict(showgrid=True, gridcolor="#E2E6ED", rangemode="tozero"),
    )
    st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})
    if proyeccion:
        st.caption(texto_metodologia_proyeccion(proyeccion))


def render(tabla, periodo=None):
    periodo = periodo or dr.PERIODO_COMPLETO
    hay_anterior = tabla["eficiencia_normalizada_anterior"].notna().any() if not tabla.empty else False
    seo_real_txt = (
        "Semáforo SEO real (septiembre, censo completo de 744 notas — checklist de 13 ítems "
        "automatizables). " if periodo == "2026-09" else ""
    )
    banner_txt = (
        "Datos REALES (roster + GA4 + Search Console" + (" + semáforo SEO" if periodo == "2026-09" else "")
        + ") — agosto 2026 es mes cerrado (censo completo); septiembre es el mes en curso (1-28 sep, "
        "proyectado a mes completo donde aplica). "
        + ("Deltas vs. agosto ya son reales para quien escribió en ambos meses. "
           if hay_anterior else "")
        + "Posición/CTR real (Search Console) cubre el top 1.000 páginas por clics — tope de la "
        "plataforma, no elegido por nosotros. " + seo_real_txt
        + "Sigue pendiente (marcado \"s/d\", nunca inventado): flags de IA y notas por dificultad."
    )
    st.markdown(info_banner(banner_txt), unsafe_allow_html=True)

    if tabla.empty:
        st.info("No hay datos para el periodo seleccionado.")
        return None

    _kpis(tabla)
    _explicacion_eficiencia(tabla)
    st.write("")
    with st.container(border=True, key="card_tendencia"):
        _tendencia_portal()
    st.write("")

    col_izq, col_der = st.columns([1, 1.3])
    with col_izq:
        with st.container(border=True, key="card_aporte"):
            _aporte_trafico(tabla)
    with col_der:
        with st.container(border=True, key="card_cuadrante"):
            seleccion_cuadrante = _cuadrante(tabla)

    st.write("")
    with st.container(border=True, key="card_notas"):
        _notas_por_periodista(tabla)

    st.write("")
    with st.container(border=True, key="card_tabla"):
        seleccion_selector = _selector_perfil(tabla)
        seleccion_tabla = _tabla_principal(tabla)

    st.write("")
    with st.container(border=True, key="card_dificultad_canal"):
        _dificultad_canal_secciones(periodo)

    return seleccion_cuadrante or seleccion_tabla or seleccion_selector
