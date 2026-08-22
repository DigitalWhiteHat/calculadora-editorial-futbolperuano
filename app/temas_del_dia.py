"""Vista Temas del día — pendiente. Espejo de
calculadora-periodistas/app/temas_del_dia.py (colombia.com): ahí cruza
"Temas recomendados" (que sale de un pipeline de entidades/temas recurrentes
sobre su historial) con keywords en tendencia vía Semrush. Acá ya hay la misma
profundidad de historial real (ene-ago 2026, 8 meses) que colombia.com, pero el
insumo de entrada (entidades recomendadas por periodista) todavía no existe --
ver la tarjeta "Pendiente" del perfil individual -- así que este cruce con
Semrush no tiene con qué alimentarse todavía. Nunca se fabrica un lote falso."""

import streamlit as st


def render():
    st.subheader("🗓️ Temas del día")
    st.info(
        "⏳ Pendiente — en colombia.com esta pestaña cruza \"Temas recomendados\" (entidades con patrón "
        "sostenido, ya extraídas de títulos reales) con keywords en tendencia vía Semrush. "
        "Acá ya hay la misma profundidad de historial real que colombia.com (ene-ago 2026, 8 meses), pero "
        "todavía no existe el insumo de entrada: la minería de entidades/temas recurrentes necesita un "
        "pipeline de extracción que no se ha construido, no más historial. "
        "Ver la tarjeta \"Pendiente\" en el perfil de cada periodista para el detalle exacto."
    )
    st.caption(
        "Cuando el pipeline de entidades esté listo, esta vista sí puede correr de inmediato — Semrush "
        "(keyword_research/organic_research) ya está disponible en esta sesión, solo falta la lista de "
        "entidades reales con la que cruzar."
    )
