"""Vista Notas — buscador/listado de todas las notas reales del periodo. Espejo
de calculadora-periodistas/app/notas.py (colombia.com)."""

import streamlit as st

import calculos as calc
import datos_reales as dr


def render(df_notas, periodo=None):
    periodo = periodo or dr.PERIODO_COMPLETO
    st.subheader("Todas las notas del periodo")
    st.caption(f"{len(df_notas)} notas reales de {dr.LABEL_PERIODO.get(periodo, periodo)} con autor identificado. "
               "Filtra por periodista, sección o canal, o busca por palabra clave del título.")

    col_buscar, col_periodista, col_seccion = st.columns([2, 1, 1])
    with col_buscar:
        buscar = st.text_input("Buscar en el título", placeholder="ej. Alianza Lima, Liga 1, Cienciano...")
    with col_periodista:
        periodistas = ["Todos"] + sorted(df_notas["periodista"].unique().tolist())
        f_periodista = st.selectbox("Periodista", periodistas)
    with col_seccion:
        secciones = ["Todas"] + sorted(df_notas["seccion"].unique().tolist())
        f_seccion = st.selectbox("Sección", secciones, format_func=lambda s: dr.LABELS_SECCION.get(s, s) if s != "Todas" else s)

    vista = df_notas.copy()
    if buscar:
        vista = vista[vista["titulo"].str.contains(buscar, case=False, na=False)]
    if f_periodista != "Todos":
        vista = vista[vista["periodista"] == f_periodista]
    if f_seccion != "Todas":
        vista = vista[vista["seccion"] == f_seccion]

    vista = vista.sort_values("clics", ascending=False)
    st.caption(f"{len(vista)} notas encontradas · {calc.formatear_numero(vista['clics'].sum())} de tráfico combinado")

    tabla = vista.copy()
    tabla["seccion_label"] = tabla["seccion"].map(lambda s: dr.LABELS_SECCION.get(s, s))
    tabla["trafico_txt"] = tabla["clics"].apply(calc.formatear_numero)
    tabla["posicion_txt"] = tabla["posicion_promedio"].apply(lambda p: f"{p:.0f}" if p == p else "s/d")

    columnas = ["titulo", "periodista", "seccion_label", "trafico_txt", "posicion_txt", "semaforo"]
    st.dataframe(
        tabla[columnas], hide_index=True, width="stretch", height=560,
        column_config={
            "titulo": st.column_config.TextColumn("Título", width="large"),
            "periodista": st.column_config.TextColumn("Periodista", width="medium"),
            "seccion_label": st.column_config.TextColumn("Sección", width="small"),
            "trafico_txt": st.column_config.TextColumn("Tráfico", width="small"),
            "posicion_txt": st.column_config.TextColumn("Posición Google", width="small"),
            "semaforo": st.column_config.TextColumn("SEO", width="small"),
        },
    )
