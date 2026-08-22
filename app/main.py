"""Desempeño Editorial — Futbolperuano.com
Espejo completo de calculadora-periodistas (colombia.com), datos reales.
Entry point: streamlit run app/main.py
"""

import streamlit as st

import alertas as vista_alertas
import datos_reales as dr
import diagnostico_seo as vista_diagnostico_seo
import general
import impacto_algoritmo as vista_impacto_algoritmo
import individual
import notas as vista_notas
import reemplazos as vista_reemplazos
import secciones as vista_secciones
import temas_del_dia as vista_temas_del_dia
from avatares import logo_futbolperuano_data_uri
from estilos import inyectar_css

st.set_page_config(page_title="Desempeño Editorial — Futbolperuano.com", layout="wide", page_icon="⚽")
inyectar_css()

periodistas_meta = dr.cargar_periodistas_meta()

if "vista" not in st.session_state:
    st.session_state.vista = "general"
if "periodista_slug" not in st.session_state:
    st.session_state.periodista_slug = periodistas_meta[0]["slug"]
if "periodo" not in st.session_state:
    st.session_state.periodo = dr.PERIODOS_DISPONIBLES[-1][0]

tabla_periodistas = dr.cargar_periodistas(st.session_state.periodo)
df_notas = dr.cargar_notas(st.session_state.periodo)

NAV_ITEMS = [
    ("🏠", "Dashboard", "general"),
    ("🗂️", "Secciones", "secciones"),
    ("📝", "Notas más vistas", "notas"),
    ("🔔", "Alertas", "alertas"),
    ("🔍", "Diagnóstico SEO", "diagnostico_seo"),
    ("🗓️", "Temas del día", "temas_del_dia"),
    ("📡", "Impacto algoritmo", "impacto_algoritmo"),
    ("🔁", "Reemplazos", "reemplazos"),
]
VISTAS_PRINCIPALES = {"general", "secciones", "notas", "alertas", "diagnostico_seo", "temas_del_dia",
                       "impacto_algoritmo", "reemplazos"}

with st.sidebar:
    st.markdown(
        f'<div style="background:#FFFFFF;border-radius:12px;padding:10px 14px;'
        f'display:inline-flex;align-items:center;justify-content:center;'
        f'width:fit-content;margin-bottom:4px">'
        f'<img src="{logo_futbolperuano_data_uri()}" style="height:40px;width:auto;display:block">'
        f'</div>', unsafe_allow_html=True,
    )
    st.caption("Desempeño Editorial")
    st.write("")
    vista_activa = st.session_state.vista if st.session_state.vista in VISTAS_PRINCIPALES else "general"
    for icono, etiqueta, vista_key in NAV_ITEMS:
        es_actual = vista_activa == vista_key
        st.button(f"{icono}  {etiqueta}", key=f"nav_{etiqueta}", width="stretch",
                  type="primary" if es_actual else "secondary",
                  on_click=lambda v=vista_key: st.session_state.update(vista=v))
    st.write("")
    st.caption("v0.5 · espejo completo, datos reales (ene-ago 2026, 8 meses de censo completo)")

st.markdown(
    f'<div class="cp-topbar"><div class="cp-brand">'
    f'<img src="{logo_futbolperuano_data_uri()}" class="cp-brand-logo-img" alt="Futbolperuano.com">'
    f'<span class="cp-brand-sep">|</span>'
    f'<span class="cp-brand-label">DESEMPEÑO EDITORIAL</span>'
    f'</div></div>', unsafe_allow_html=True,
)

col_espacio, col_periodo = st.columns([4, 2])
with col_periodo:
    codigos = [c for c, _ in dr.PERIODOS_DISPONIBLES]
    st.selectbox(
        "📅 Periodo", codigos, index=codigos.index(st.session_state.periodo),
        format_func=lambda c: dr.LABEL_PERIODO[c], key="periodo", label_visibility="collapsed",
    )

if st.session_state.vista == "individual":
    col_breadcrumb, col_selector = st.columns([3, 1])
    with col_breadcrumb:
        if st.button("← Volver al dashboard", key="volver_dashboard"):
            st.session_state.vista = "general"
            st.rerun()
        st.markdown('<div class="cp-breadcrumb">Desempeño Editorial &nbsp;›&nbsp; <b>Perfil del Periodista</b></div>',
                    unsafe_allow_html=True)
    nombres = [p["nombre"] for p in periodistas_meta]
    slug_actual = st.session_state.periodista_slug
    nombre_actual = next(p["nombre"] for p in periodistas_meta if p["slug"] == slug_actual)
    with col_selector:
        elegido = st.selectbox("Cambiar periodista", nombres, index=nombres.index(nombre_actual),
                                key="selector_periodista_top")
    slug_elegido = next(p["slug"] for p in periodistas_meta if p["nombre"] == elegido)
    if slug_elegido != slug_actual:
        st.session_state.periodista_slug = slug_elegido
        st.rerun()

    individual.render(tabla_periodistas, df_notas, st.session_state.periodista_slug, st.session_state.periodo)
elif st.session_state.vista == "secciones":
    vista_secciones.render(tabla_periodistas, st.session_state.periodo)
elif st.session_state.vista == "notas":
    vista_notas.render(df_notas, st.session_state.periodo)
elif st.session_state.vista == "alertas":
    vista_alertas.render(tabla_periodistas, st.session_state.periodo)
elif st.session_state.vista == "diagnostico_seo":
    vista_diagnostico_seo.render()
elif st.session_state.vista == "temas_del_dia":
    vista_temas_del_dia.render()
elif st.session_state.vista == "impacto_algoritmo":
    vista_impacto_algoritmo.render()
elif st.session_state.vista == "reemplazos":
    vista_reemplazos.render(tabla_periodistas)
else:
    slug_seleccionado = general.render(tabla_periodistas, st.session_state.periodo)
    if slug_seleccionado:
        st.session_state.periodista_slug = slug_seleccionado
        st.session_state.vista = "individual"
        st.rerun()
