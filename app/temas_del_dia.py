"""Vista Temas del día -- espejo de colombia.com/app/temas_del_dia.py: entidades
recomendadas de TODO el portal (patrón real de recurrencia, 9 meses ene-sep
2026, ver data/seleccionar_entidades_prioritarias.py), pensadas como insumo
para cruzar con keywords en tendencia vía Semrush.

El cruce con Semrush queda pendiente por un bloqueo real de cuenta, no de este
proyecto: desde el 26-ago-2026 la cuenta de Semrush está sin unidades de API
(afecta a todos los clientes, ver semrush-sin-unidades-api.md) -- se muestra la
lista real de entidades prioritarias sin el volumen/tendencia de Semrush hasta
que se repongan unidades, en vez de fabricar esas cifras."""

import streamlit as st

import datos_reales as dr


def render():
    st.subheader("🗓️ Temas del día")
    st.info(
        "Entidades/temas prioritarios de TODO el portal, dedupeados -- patrón real de recurrencia "
        "sobre 9 meses reales de censo completo (ene-sep 2026): al menos 3 meses distintos activo, "
        "con demanda todavía cerca de su pico histórico. El cruce con keywords en tendencia vía "
        "Semrush está pendiente por un bloqueo real de cuenta (sin unidades de API desde el "
        "26-ago-2026, afecta a todos los clientes) -- se repone solo, sin tocar código.",
        icon="ℹ️",
    )

    df = dr.entidades_prioritarias_portal()
    if df.empty:
        st.caption("Sin entidades prioritarias reales todavía.")
        return

    icono_tipo = {"entidad": "🏷️", "tema": "📌"}
    icono_conf = {0: "🟢", 1: "🟡", 2: "⚪"}
    for r in df.itertuples():
        with st.container(border=True, key=f"tema_dia_{r.Index}"):
            col_izq, col_der = st.columns([3, 1])
            with col_izq:
                st.markdown(f"{icono_tipo.get(r.tipo, '•')} **{r.entidad}**")
                st.caption(f"{icono_conf.get(r.confianza_top, '⚪')} confianza · "
                           f"{int(r.n_autores)} periodista(s) escribiéndolo con patrón recurrente")
            with col_der:
                st.caption("Volumen/tendencia Semrush: s/d — cuenta sin unidades de API")
