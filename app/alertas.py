"""Vista Alertas — señales de estado actual (SEO, CTR, eficiencia) medibles con
el periodo activo, más alertas de TENDENCIA con los 7 meses cerrados de
historial real que ya hay (ene-jul 2026, ver dr.alertas_tendencia()). Espejo de
calculadora-periodistas/app/alertas.py (colombia.com); canibalización sigue sin
construirse (s/d, nunca fabricada)."""

import streamlit as st

import datos_reales as dr
from estilos import kpi_card

COLOR_SEVERIDAD = {"CRÍTICO": ("#FEE2E2", "#991B1B", "🔴"), "ATENCIÓN": ("#FEF3C7", "#92400E", "🟡")}
ICONO_TIPO = {"SEO": "🧭", "Canibalización": "🔁", "CTR": "🎯", "Eficiencia": "📉", "Tendencia": "📉"}


def _kpis(tabla):
    n_criticos = int(tabla["en_alerta"].sum())
    n_con_alertas = int((tabla["alertas"].apply(len) > 0).sum())
    total_alertas = int(tabla["alertas"].apply(len).sum())
    limpios = int((tabla["alertas"].apply(len) == 0).sum())
    tarjetas = [
        kpi_card("🔴", "Periodistas con alerta crítica", f"{n_criticos}"),
        kpi_card("🟡", "Periodistas con alguna alerta", f"{n_con_alertas}"),
        kpi_card("📋", "Total de alertas activas", f"{total_alertas}"),
        kpi_card("✅", "Periodistas sin alertas", f"{limpios}"),
    ]
    st.markdown(f'<div class="cp-kpi-row">{"".join(tarjetas)}</div>', unsafe_allow_html=True)


def _tarjeta_alertas(slug, periodista, seccion, alertas, prefijo="alerta"):
    alertas = sorted(alertas, key=lambda a: a["severidad"] != "CRÍTICO")
    if not alertas:
        return
    with st.container(border=True, key=f"{prefijo}_{slug}"):
        col_nombre, col_boton = st.columns([3, 1])
        col_nombre.markdown(f"**{periodista}** · {dr.LABELS_SECCION.get(seccion, seccion)}")
        if col_boton.button("Ver perfil →", key=f"btn_{prefijo}_{slug}", width="stretch"):
            st.session_state.periodista_slug = slug
            st.session_state.vista = "individual"
            st.rerun()
        for a in alertas:
            bg, fg, icono_sev = COLOR_SEVERIDAD[a["severidad"]]
            icono_tipo = ICONO_TIPO.get(a["tipo"], "•")
            st.markdown(
                f'<div style="background:{bg};color:{fg};border-radius:8px;padding:8px 12px;'
                f'margin-top:6px;font-size:0.92rem">{icono_sev} {icono_tipo} <b>{a["tipo"]}</b> — {a["mensaje"]}</div>',
                unsafe_allow_html=True,
            )


def _alertas_tendencia():
    st.subheader("Alertas de tendencia (7 meses)")
    st.caption(
        "Ahora sí medibles: con 7 meses de historial real (ene-jul 2026), una racha de varios meses seguidos "
        "con eficiencia por debajo de la mediana del equipo es una señal real de tendencia, no solo un mal mes. "
        "🟡 3-4 meses seguidos · 🔴 5+ meses seguidos."
    )
    st.caption(
        "⏸️ El mes en curso (agosto) no entra en este cálculo a propósito: "
        "un mes parcial mezclado con 7 meses completos distorsionaría la racha real (un mal arranque de mes "
        "no es lo mismo que una tendencia sostenida). Se incorpora solo cuando el mes cierra."
    )
    alertas = dr.alertas_tendencia()
    if not alertas:
        st.success("Ningún periodista tiene una racha de 3+ meses con eficiencia baja.")
        return
    for a in alertas:
        _tarjeta_alertas(a["slug"], a["periodista"], a["seccion"],
                          [{"tipo": "Tendencia", "severidad": a["severidad"], "mensaje": a["mensaje"]}],
                          prefijo="alerta_tendencia")


def render(tabla, periodo=None):
    periodo = periodo or dr.PERIODO_COMPLETO
    st.subheader(f"Alertas — estado actual del equipo ({dr.LABEL_PERIODO.get(periodo, periodo)})")
    st.info(
        "⚠️ Estas alertas son de **estado actual** (eficiencia relativa al equipo, semáforo SEO real, "
        "CTR real vs. esperado) — todas medibles con los datos reales de este periodo. Canibalización "
        "interna no está construida todavía (s/d, nunca fabricada). Las alertas de **tendencia** "
        "(racha de 3+ periodos) están más abajo.",
        icon="ℹ️",
    )
    _kpis(tabla)
    st.write("")

    ordenado = tabla.copy()
    ordenado["n_alertas"] = ordenado["alertas"].apply(len)
    ordenado["n_criticas"] = ordenado["alertas"].apply(lambda al: sum(1 for a in al if a["severidad"] == "CRÍTICO"))
    ordenado = ordenado.sort_values(["n_criticas", "n_alertas"], ascending=False)

    con_alertas = ordenado[ordenado["n_alertas"] > 0]
    sin_alertas = ordenado[ordenado["n_alertas"] == 0]

    if con_alertas.empty:
        st.success("Ningún periodista tiene alertas activas este periodo.")
    else:
        for _, fila in con_alertas.iterrows():
            _tarjeta_alertas(fila["slug"], fila["periodista"], fila["seccion"], fila["alertas"])

    if not sin_alertas.empty:
        st.write("")
        st.caption("Sin alertas activas: " + ", ".join(sin_alertas["periodista"].tolist()))

    st.write("")
    with st.container(border=True, key="card_alertas_tendencia"):
        _alertas_tendencia()
