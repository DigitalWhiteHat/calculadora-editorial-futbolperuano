"""Vista Secciones — panorama 360 de todo el portal: dónde está el tráfico, no
solo las secciones con periodista identificado. Espejo de
calculadora-periodistas/app/secciones.py (colombia.com), con ene-ago 2026
(8 meses reales, misma profundidad que el original) -- las herramientas de
decisión (simulador, especialización, redistribución) usan TODO el censo
completo disponible, igual principio que el original (no una foto de un solo mes)."""

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import calculos as calc
import datos_reales as dr
from estilos import kpi_card, metrica_card

COLOR_CON_PERIODISTA = "#16A34A"
COLOR_SIN_PERIODISTA = "#94A3B8"

LABELS_SECCION = dr.LABELS_SECCION
PLAYBOOK_HINT = {}  # sin playbook editorial confirmado todavía para futbolperuano.com


def _kpis(df):
    total = df["trafico"].sum()
    con_p = df[df["con_periodista"]]["trafico"].sum()
    top = df.sort_values("trafico", ascending=False).iloc[0]
    tarjetas = [
        kpi_card("🌐", "Tráfico total del portal (secciones curadas)", calc.formatear_numero(total)),
        kpi_card("👤", "Con periodista identificado", f"{100*con_p/total:.0f}%" if total else "—",
                  help_text="% del tráfico que cae en secciones donde ya identificamos autor por nota"),
        kpi_card("🥇", top["label"], f"{top['pct_del_portal']:.0f}%",
                  help_text="Sección con más tráfico real del portal en este periodo"),
        kpi_card("📊", "Secciones con volumen real", f"{len(df)}"),
    ]
    st.markdown(f'<div class="cp-kpi-row">{"".join(tarjetas)}</div>', unsafe_allow_html=True)


def _grafico(df):
    st.subheader("Tráfico por sección — todo el portal")
    st.caption("🟢 Verde = sección con periodista(s) identificado(s) · Gris = solo seguimiento agregado "
               "(tablas de posiciones, partidos por TV, portada — utilitario, sin autor)")
    ordenado = df.sort_values("trafico", ascending=True)
    colores = [COLOR_CON_PERIODISTA if c else COLOR_SIN_PERIODISTA for c in ordenado["con_periodista"]]
    textos = [f"{calc.formatear_numero(v)} · {p:.1f}%" for v, p in zip(ordenado["trafico"], ordenado["pct_del_portal"])]
    fig = go.Figure(go.Bar(
        x=ordenado["trafico"], y=ordenado["label"], orientation="h",
        marker_color=colores, text=textos, textposition="outside",
        hovertemplate="%{y}<br>Tráfico: %{x:,.0f}<extra></extra>",
    ))
    fig.update_layout(
        height=max(400, 26 * len(ordenado)), margin=dict(l=0, r=80, t=10, b=10),
        xaxis_title=None, yaxis_title=None, showlegend=False,
        plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
        xaxis=dict(showgrid=True, gridcolor="#E2E6ED"),
        yaxis=dict(automargin=True),
    )
    st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})


def _tabla(df):
    st.subheader("Detalle por sección")
    vista = df.copy().sort_values("trafico", ascending=False)
    vista["trafico_txt"] = vista["trafico"].apply(calc.formatear_numero)
    vista["cobertura"] = vista["con_periodista"].apply(lambda c: "👤 Con periodista" if c else "📦 Solo agregado")
    vista["notas_txt"] = vista.apply(
        lambda r: f"{r['notas_identificadas']} ({r['periodistas_activos']} periodistas)" if r["con_periodista"] else "—",
        axis=1)
    columnas = ["label", "trafico_txt", "pct_del_portal", "cobertura", "notas_txt"]
    st.dataframe(
        vista[columnas], hide_index=True, width="stretch",
        column_config={
            "label": st.column_config.TextColumn("Sección", width="medium"),
            "trafico_txt": st.column_config.TextColumn("Tráfico", width="small"),
            "pct_del_portal": st.column_config.NumberColumn("% del portal", format="%.1f%%", width="small"),
            "cobertura": st.column_config.TextColumn("Cobertura editorial", width="small"),
            "notas_txt": st.column_config.TextColumn("Notas identificadas (ene-ago)", width="small"),
        },
    )


def _eficiencia_por_seccion(df_notas):
    st.subheader("Cuántas notas produce cada sección — y qué tan bien le rinden")
    st.caption(
        "Esto NO depende de quién firmó la nota — cuenta todo artículo real con autor identificado, "
        "acumulado en ene-ago 2026 (8 meses reales, misma profundidad que colombia.com)."
    )
    vista = df_notas.copy().sort_values("trafico_por_nota", ascending=False)
    vista["trafico_txt"] = vista["trafico"].apply(calc.formatear_numero)
    fig = go.Figure(go.Bar(
        x=vista["trafico_por_nota"], y=vista["label"], orientation="h",
        marker_color="#3457D5", text=[f"{v:,.0f}".replace(",", ".") for v in vista["trafico_por_nota"]],
        textposition="outside", hovertemplate="%{y}<br>Tráfico por nota: %{x:,.0f}<extra></extra>",
    ))
    fig.update_layout(
        height=max(360, 26 * len(vista)), margin=dict(l=0, r=60, t=10, b=10),
        xaxis_title="Tráfico promedio por nota (eficiencia)", yaxis_title=None, showlegend=False,
        plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
        xaxis=dict(showgrid=True, gridcolor="#E2E6ED"), yaxis=dict(automargin=True),
    )
    st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})
    st.dataframe(
        vista[["label", "notas", "trafico_txt"]], hide_index=True, width="stretch",
        column_config={
            "label": st.column_config.TextColumn("Sección", width="medium"),
            "notas": st.column_config.NumberColumn("Notas publicadas (ene-ago)", width="small"),
            "trafico_txt": st.column_config.TextColumn("Tráfico total", width="small"),
        },
    )


def _simulador(df_notas):
    st.subheader("Simulador: ¿cuántas notas necesita cada sección?")
    st.caption(
        "Elige una sección y escribe la meta mensual de tráfico. Con la eficiencia real de ene-ago 2026 "
        "calcula cuántas notas al mes — y al día — hacen falta para llegar."
    )
    n_meses = len(dr.PERIODOS_DISPONIBLES)
    base = df_notas[df_notas["notas"] >= 3].copy()
    if base.empty:
        st.caption("Ninguna sección con muestra mínima (≥3 notas) todavía.")
        return
    base["notas_mes"] = (base["notas"] / n_meses).round(1)
    base["trafico_mes"] = (base["trafico"] / n_meses).round(0)
    if "meta_mensual" not in st.session_state:
        st.session_state["meta_mensual"] = {row["seccion"]: int(row["trafico_mes"]) for _, row in base.iterrows()}

    capacidad_notas_dia_portal = base["notas_mes"].sum() / 30
    c_seccion, c_meta = st.columns(2)
    with c_seccion:
        with st.container(border=True, key="card_sim_notas_seccion"):
            seccion_sel = st.selectbox("🗂️ Sección", base["seccion"].tolist(),
                                        format_func=lambda s: LABELS_SECCION.get(s, s.title()), key="sim_meta_seccion")
    fila = base[base["seccion"] == seccion_sel].iloc[0]
    with c_meta:
        with st.container(border=True, key="card_sim_notas_meta"):
            meta = st.number_input(
                f"🎯 Meta mensual de tráfico — {fila['label']}", min_value=0, step=5000,
                value=int(st.session_state["meta_mensual"].get(seccion_sel, fila["trafico_mes"])),
                key=f"meta_input_{seccion_sel}",
            )
            st.caption(f"= {calc.formatear_numero(meta)} / mes")
    st.session_state["meta_mensual"][seccion_sel] = meta

    notas_necesarias = meta / fila["trafico_por_nota"] if fila["trafico_por_nota"] else 0
    notas_dia = notas_necesarias / 30
    delta = notas_necesarias - fila["notas_mes"]
    pct_capacidad = 100 * notas_dia / capacidad_notas_dia_portal if capacidad_notas_dia_portal else 0

    def _tarjeta(icono, titulo, valor, bg, fg):
        return (f'<div style="background:{bg};border-radius:12px;padding:14px 16px;height:100%">'
                f'<div style="font-size:0.95rem;color:{fg};font-weight:600;margin-bottom:6px">{icono} {titulo}</div>'
                f'<div style="font-size:1.6rem;font-weight:700;color:{fg}">{valor}</div></div>')

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.markdown(_tarjeta("⚡", "Eficiencia (tráfico/nota)", f"{fila['trafico_por_nota']:,.0f}".replace(",", "."),
                              "#EFF6FF", "#1E40AF"), unsafe_allow_html=True)
    with c2:
        st.markdown(_tarjeta("📝", "Notas necesarias/mes", f"{notas_necesarias:,.0f}".replace(",", "."),
                              "#EFF6FF", "#1E40AF"), unsafe_allow_html=True)
    with c3:
        st.markdown(_tarjeta("📅", "Notas/día", f"{notas_dia:.1f}", "#EFF6FF", "#1E40AF"), unsafe_allow_html=True)
    with c4:
        signo = "+" if delta >= 0 else ""
        bg, fg = ("#FEE2E2", "#991B1B") if delta > 0 else ("#DCFCE7", "#166534")
        st.markdown(_tarjeta("⚖️", "Delta vs. promedio actual", f"{signo}{delta:,.1f}".replace(",", "."), bg, fg),
                    unsafe_allow_html=True)
    st.write("")
    st.info(f"📊 Esas {notas_dia:.1f} notas/día representan **{pct_capacidad:.0f}%** de las "
            f"~{capacidad_notas_dia_portal:.0f} notas/día que produce HOY todo el portal en las "
            "secciones con muestra confiable.")


def _especializacion_periodistas(esp):
    st.subheader("Especialización real: dónde le rinde a cada periodista escribir")
    st.caption(
        "Cruce periodista × sección con ene-ago 2026 (8 meses reales, misma profundidad que colombia.com). Confianza: "
        "🟢 alta (≥10 notas) · 🟡 media (3-9) · ⚪ baja (<3, indicativo)."
    )
    icono_conf = {"alta": "🟢", "media": "🟡", "baja": "⚪"}
    for autor in sorted(esp["autor"].unique()):
        sub = esp[esp["autor"] == autor].sort_values("trafico_por_nota", ascending=False)
        mejor, peor = sub.iloc[0], sub.iloc[-1]
        with st.expander(f"{autor} — {len(sub)} sección(es) trabajada(s) en ene-ago"):
            vista = sub.copy()
            vista["label"] = vista["seccion"].map(lambda s: LABELS_SECCION.get(s, s.title()))
            vista["icono"] = vista["confianza"].map(icono_conf)
            st.dataframe(
                vista[["label", "notas", "trafico_por_nota", "icono"]], hide_index=True, width="stretch",
                column_config={
                    "label": st.column_config.TextColumn("Sección", width="small"),
                    "notas": st.column_config.NumberColumn("Notas (ene-ago)", width="small"),
                    "trafico_por_nota": st.column_config.NumberColumn("Tráfico/nota", format="%.0f", width="small"),
                    "icono": st.column_config.TextColumn("Confianza", width="small"),
                },
            )
            if len(sub) > 1:
                st.markdown(f"🟢 **Mejor rendimiento: {LABELS_SECCION.get(mejor['seccion'], mejor['seccion'])}** "
                            f"— {mejor['trafico_por_nota']:,.0f} tráfico/nota".replace(",", "."))
                st.markdown(f"🔴 **Más débil: {LABELS_SECCION.get(peor['seccion'], peor['seccion'])}** "
                            f"— {peor['trafico_por_nota']:,.0f} tráfico/nota".replace(",", "."))


def _simulador_escenarios(esp, df_notas_seccion, tabla_periodistas):
    st.subheader("Simulador: ¿qué pasa si muevo a un periodista de sección?")
    st.caption(
        "Elige un periodista y una sección destino. Si ya escribió ahí, usa su propio rendimiento real "
        "(ene-ago); si no, la mediana real de quienes sí escriben esa sección; si nadie lo ha intentado, "
        "un estimado conservador. La pérdida se ve de inmediato; la ganancia tarda en madurar."
    )
    periodistas = sorted(esp["autor"].unique())
    c_per, c_deja, c_destino, c_notas = st.columns(4)
    with c_per:
        with st.container(border=True, key="card_sim_periodista"):
            periodista_sel = st.selectbox("👤 Periodista", periodistas, key="sim_periodista")
    secciones_periodista = esp[esp["autor"] == periodista_sel].sort_values("notas", ascending=False)
    with c_deja:
        with st.container(border=True, key="card_sim_origen"):
            seccion_origen = st.selectbox("📉 Sección que reduce/deja", secciones_periodista["seccion"].tolist(),
                                           format_func=lambda s: LABELS_SECCION.get(s, s.title()), key="sim_origen")
    todas_secciones = sorted(df_notas_seccion["seccion"].unique())
    opciones_destino = [s for s in todas_secciones if s != seccion_origen]
    with c_destino:
        with st.container(border=True, key="card_sim_destino"):
            seccion_destino = st.selectbox("📈 Sección destino", opciones_destino,
                                            format_func=lambda s: LABELS_SECCION.get(s, s.title()), key="sim_destino")
    fila_origen = secciones_periodista[secciones_periodista["seccion"] == seccion_origen].iloc[0]
    n_meses = len(dr.PERIODOS_DISPONIBLES)
    notas_mes_promedio = max(1, round(fila_origen["notas"] / n_meses))
    with c_notas:
        with st.container(border=True, key="card_sim_notas"):
            notas_a_mover = st.number_input(
                "🔢 Notas/mes a mover", min_value=1, max_value=max(200, notas_mes_promedio * 3),
                value=notas_mes_promedio, key="sim_notas",
                help=f"Promedio real de {periodista_sel} en esta sección: {int(fila_origen['notas'])} notas en "
                     f"ene-ago (~{notas_mes_promedio}/mes).",
            )
    eficiencia_origen = float(fila_origen["trafico_por_nota"])
    trafico_perdido = notas_a_mover * eficiencia_origen
    fila_destino_propia = esp[(esp["autor"] == periodista_sel) & (esp["seccion"] == seccion_destino)]
    mediana_destino_row = df_notas_seccion[df_notas_seccion["seccion"] == seccion_destino]
    mediana_portal = df_notas_seccion["trafico_por_nota"].median()

    if not fila_destino_propia.empty:
        eficiencia_destino = float(fila_destino_propia.iloc[0]["trafico_por_nota"])
        confianza_destino, fuente_destino = "alta", f"rendimiento propio de {periodista_sel} en esta sección"
    elif not mediana_destino_row.empty:
        eficiencia_destino = float(mediana_destino_row.iloc[0]["trafico_por_nota"])
        confianza_destino, fuente_destino = "media", "eficiencia real de la sección (todo el contenido identificado)"
    else:
        eficiencia_destino = mediana_portal * 0.7
        confianza_destino, fuente_destino = "baja", "sin datos de esa sección — estimado conservador (70% de la mediana)"

    trafico_ganado = notas_a_mover * eficiencia_destino
    neto = trafico_ganado - trafico_perdido
    icono = {"alta": "🟢", "media": "🟡", "baja": "⚪"}.get(confianza_destino)

    def _resultado_card(icono_r, titulo, valor, bg, fg):
        return (f'<div style="background:{bg};border-radius:12px;padding:16px 18px;height:100%">'
                f'<div style="font-size:1.05rem;color:{fg};font-weight:600;margin-bottom:8px">{icono_r} {titulo}</div>'
                f'<div style="font-size:1.9rem;font-weight:700;color:{fg}">{valor}</div></div>')

    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown(_resultado_card("🔻", f"Pierde en {LABELS_SECCION.get(seccion_origen, seccion_origen)} (inmediato)",
                                     f"-{calc.formatear_numero(trafico_perdido)}/mes", "#FEE2E2", "#991B1B"), unsafe_allow_html=True)
    with c2:
        st.markdown(_resultado_card(icono, f"Gana en {LABELS_SECCION.get(seccion_destino, seccion_destino)} (una vez madure)",
                                     f"+{calc.formatear_numero(trafico_ganado)}/mes", "#DCFCE7", "#166534"), unsafe_allow_html=True)
    with c3:
        signo = "+" if neto >= 0 else ""
        bg_neto, fg_neto = ("#DCFCE7", "#166534") if neto >= 0 else ("#FEE2E2", "#991B1B")
        st.markdown(_resultado_card("📊", "Neto proyectado", f"{signo}{calc.formatear_numero(neto)}/mes", bg_neto, fg_neto),
                    unsafe_allow_html=True)
    st.write("")
    st.caption(f"Ganancia estimada con: {fuente_destino}.")
    if neto < 0:
        st.error("Con estos supuestos el movimiento pierde tráfico neto. Prueba otra sección destino.")


def _propuesta_redistribucion(df_notas_seccion, tabla_periodistas):
    st.subheader("Propuesta de redistribución editorial")
    st.caption(
        "Cruce de eficiencia por sección + cuántos periodistas están asignados hoy a cada una (por su "
        "sección dominante). Punto de partida con datos — la decisión final es editorial."
    )
    activos = tabla_periodistas.groupby("seccion_raw").agg(
        periodistas=("periodista", lambda s: ", ".join(s)), n_periodistas=("periodista", "count"),
    ).reset_index().rename(columns={"seccion_raw": "seccion"})
    df = df_notas_seccion.merge(activos, on="seccion", how="left")
    df["n_periodistas"] = df["n_periodistas"].fillna(0).astype(int)
    df["periodistas"] = df["periodistas"].fillna("— ninguno asignado como principal")

    mediana_eficiencia = df["trafico_por_nota"].median()
    subrecursos = df[(df["trafico_por_nota"] > mediana_eficiencia) & (df["n_periodistas"] <= 1)].sort_values(
        "trafico_por_nota", ascending=False)
    sobrerecursos = df[(df["trafico_por_nota"] < mediana_eficiencia) & (df["n_periodistas"] >= 2)].sort_values(
        "trafico_por_nota")

    col_sub, col_sobre = st.columns(2)
    with col_sub:
        st.markdown("**🟢 Candidatas a reforzar** (alta eficiencia, poco recurso asignado)")
        if subrecursos.empty:
            st.caption("Ninguna sección cumple ambas condiciones.")
        for _, r in subrecursos.head(4).iterrows():
            st.markdown(f"- **{r['label']}** — {r['trafico_por_nota']:,.0f} tráfico/nota, "
                        f"{r['n_periodistas']} periodista(s) principal(es)".replace(",", "."))
    with col_sobre:
        st.markdown("**🔴 Candidatas a reducir** (baja eficiencia, varios recursos asignados)")
        if sobrerecursos.empty:
            st.caption("Ninguna sección cumple ambas condiciones.")
        for _, r in sobrerecursos.head(4).iterrows():
            st.markdown(f"- **{r['label']}** — {r['trafico_por_nota']:,.0f} tráfico/nota, "
                        f"{r['n_periodistas']} periodista(s) principal(es)".replace(",", "."))

    st.write("")
    vista = df[["label", "trafico_por_nota", "n_periodistas", "periodistas"]].sort_values(
        "trafico_por_nota", ascending=False)
    st.dataframe(
        vista, hide_index=True, width="stretch",
        column_config={
            "label": st.column_config.TextColumn("Sección", width="small"),
            "trafico_por_nota": st.column_config.NumberColumn("Eficiencia (tráfico/nota)", format="%.0f", width="small"),
            "n_periodistas": st.column_config.NumberColumn("Periodistas asignados hoy", width="small"),
            "periodistas": st.column_config.TextColumn("Quiénes (sección dominante)", width="large"),
        },
    )


def _herramientas_2meses(tabla_periodistas):
    df_notas_seccion = dr.notas_por_seccion_independiente()
    esp = dr.especializacion_todos()
    if df_notas_seccion.empty:
        st.info("Sin notas identificadas todavía para calcular estas herramientas.")
        return

    st.write("")
    with st.container(border=True, key="card_eficiencia_seccion"):
        _eficiencia_por_seccion(df_notas_seccion)
    st.write("")
    with st.container(border=True, key="card_simulador"):
        _simulador(df_notas_seccion)
    if not esp.empty:
        st.write("")
        with st.container(border=True, key="card_especializacion"):
            _especializacion_periodistas(esp)
        st.write("")
        with st.container(border=True, key="card_simulador_escenarios"):
            _simulador_escenarios(esp, df_notas_seccion, tabla_periodistas)
    st.write("")
    with st.container(border=True, key="card_propuesta"):
        _propuesta_redistribucion(df_notas_seccion, tabla_periodistas)

    st.write("")
    with st.container(border=True, key="card_titulares_pendiente"):
        st.subheader("🧮 Qué ecuación de titular le sirve a cada sección")
        st.caption(
            "Pendiente — necesita minería de patrones de titulares (mínimo 10 notas con y sin cada rasgo "
            "por sección), no construida todavía. Ver la misma nota en el perfil de cada periodista."
        )


def render(tabla_periodistas, periodo=None):
    periodo = periodo or dr.PERIODO_COMPLETO
    df = dr.secciones_360(periodo)
    st.subheader(f"Panorama del portal — {dr.LABEL_PERIODO.get(periodo, periodo)}")
    st.caption("No solo lo que tiene periodista asignado: así se reparte TODO el tráfico real del periodo.")
    _kpis(df)
    st.write("")
    with st.container(border=True, key="card_secciones_grafico"):
        _grafico(df)
    st.write("")
    with st.container(border=True, key="card_secciones_tabla"):
        _tabla(df)

    _herramientas_2meses(tabla_periodistas)
