"""Vista Impacto algoritmo — declive real por sección (mes vs. mes anterior,
ritmo diario) + updates de Google conocidos. Espejo simplificado de
calculadora-periodistas/app/impacto_algoritmo.py (colombia.com): esa versión usa
snapshots DIARIOS de Search Console + desglose Search/Discover/News por sección,
construido a lo largo de varias rondas específicas para colombia.com. Acá el
ranking de declive SÍ es real (GA4 real, agosto vs. julio -- los dos periodos
más recientes de los 8 meses reales disponibles, ene-ago 2026 -- ritmo diario
para que un mes parcial no se vea peor solo por tener menos días) -- lo que
falta es granularidad DIARIA (no mensual) y el desglose por tipo de búsqueda
GSC (Search/Discover/News), que necesitan exports distintos, no hechos todavía."""

import streamlit as st

import calculos as calc
import datos_reales as dr
from google_updates import UPDATES_2026


def _semaforo_pct(pct):
    if pct <= -15:
        return "🔴"
    if pct <= 0:
        return "🟡"
    return "🟢"


def _header_algoritmo():
    updates_ordenados = sorted(UPDATES_2026, key=lambda u: u["inicio"], reverse=True)
    with st.container(border=True, key="card_header_algoritmo"):
        st.subheader("📡 Impacto del algoritmo — por sección")
        if updates_ordenados:
            u = updates_ordenados[0]
            cierre_txt = "sin fecha de cierre reportada" if u["fin"] is None else f"cerró {u['fin'].strftime('%d-%b-%Y')}"
            st.markdown(f"Update más reciente conocido: **{u['nombre']}** ({u['tipo']}) — "
                        f"inició {u['inicio'].strftime('%d-%b-%Y')}, {cierre_txt}.")
        st.warning(
            "⚠️ Search Console tiene un rezago real de reporte de 2-3 días, y acá los 8 meses reales "
            "disponibles (ene-ago 2026) son a nivel MENSUAL, no snapshots diarios — no hay suficiente "
            "granularidad todavía para medir el efecto de un algoritmo específico con confianza. Lo de "
            "abajo es una comparación real agosto vs. julio (ritmo diario, no el total crudo), útil como "
            "alerta temprana de qué secciones vienen cayendo — no una atribución a ningún algoritmo en particular.",
            icon="⚠️",
        )


def _ranking_declive():
    df = dr.declive_secciones_jul_ago()
    with st.container(border=True, key="card_ranking_declive"):
        st.subheader("Qué secciones cayeron más — julio vs. agosto (ritmo diario real)")
        st.caption(
            "Tráfico real de GA4 dividido por días reales de cada periodo (31 en julio, 22 en agosto al "
            "corte) — así un mes parcial no se ve peor solo por tener menos días. 🔴 caída ≥15% · "
            "🟡 caída leve · 🟢 estable o sube."
        )
        if df.empty:
            st.info("Sin datos suficientes para comparar.")
            return
        filas = []
        for r in df.itertuples():
            filas.append(
                f'<div style="display:flex;justify-content:space-between;align-items:center;'
                f'padding:8px 4px;border-bottom:1px solid #E2E6ED">'
                f'<div><span style="font-weight:600">{_semaforo_pct(r.pct_cambio)} '
                f'{dr.LABELS_SECCION.get(r.seccion, r.seccion.title())}</span></div>'
                f'<div style="text-align:right"><span style="font-weight:700">{r.pct_cambio:+.0f}%</span> '
                f'<span style="color:#64748B;font-size:0.85rem">'
                f'({calc.formatear_numero(r.ritmo_dia_anterior)}/día en julio → '
                f'{calc.formatear_numero(r.ritmo_dia_actual)}/día en agosto)</span></div></div>'
            )
        st.markdown("".join(filas), unsafe_allow_html=True)
        peores = df.head(3)
        if not peores.empty and peores.iloc[0]["pct_cambio"] < -15:
            nombres = ", ".join(dr.LABELS_SECCION.get(s, s) for s in peores[peores["pct_cambio"] < -15]["seccion"])
            st.caption(f"🔻 Mayor caída: {nombres}. Antes de asumir que es un algoritmo, revisar si hay una "
                       "coyuntura real detrás (ej. fin de un torneo, ventana de fichajes cerrada) — el "
                       "ritmo diario ya descarta el sesgo de \"menos días = se ve peor\", pero no descarta "
                       "coyuntura editorial.")


def _updates_detalle():
    with st.container(border=True, key="card_updates_detalle"):
        with st.expander("📡 Detalle de updates de Google 2026"):
            for u in UPDATES_2026:
                fin_txt = u["fin"].strftime("%d %b") if u["fin"] else "en curso"
                st.markdown(f"- **{u['nombre']}** ({u['tipo']}) — {u['inicio'].strftime('%d %b')} a {fin_txt}")
            st.caption("Fuentes: Search Engine Land, Search Engine Journal, Search Engine Roundtable "
                       "(verificado agosto 2026, mismo registro que colombia.com — son updates globales "
                       "de Google, no específicos de un sitio).")


def render():
    _header_algoritmo()
    st.write("")
    _ranking_declive()
    st.write("")
    _updates_detalle()
