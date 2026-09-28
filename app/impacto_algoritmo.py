"""Vista Impacto algoritmo — tráfico histórico real por sección (9 meses,
ene-sep 2026, GA4) + declive real mes vs. mes anterior + updates de Google
conocidos. Lo que falta frente a la versión de referencia con snapshots
DIARIOS de Search Console (que sí distingue Search/Discover/News por sección)
es granularidad diaria: acá los 9 meses reales disponibles son a nivel
MENSUAL. Ese desglose diario por tipo de búsqueda necesita un export distinto
al que corre hoy -- el exportador automático de GSC (activo desde el
22-ago-2026) recién empieza a acumular esa historia hacia adelante, no se
puede reconstruir hacia atrás con datos reales."""

import plotly.graph_objects as go
import streamlit as st

import calculos as calc
import datos_reales as dr
from google_updates import UPDATES_2026
from graficos import marcar_mes_parcial

PALETA_SECCIONES = [
    "#3457D5", "#DC2626", "#16A34A", "#D97706", "#7C3AED",
    "#0891B2", "#DB2777", "#65A30D", "#EA580C", "#4F46E5",
]
COLOR_UNICO = "#E5152A"
OPCION_PORTAL = "🌐 Todo el portal (top 8 secciones)"


def _semaforo_pct(pct):
    if pct <= -15:
        return "🔴"
    if pct <= 0:
        return "🟡"
    return "🟢"


def _agregar_marcadores_updates(fig, meses):
    updates_por_mes = {}
    for u in UPDATES_2026:
        mes_str = u["inicio"].strftime("%Y-%m")
        if mes_str in meses:
            updates_por_mes.setdefault(mes_str, []).append(u)
    for mes_str, updates in updates_por_mes.items():
        tipos = " + ".join(sorted({u["tipo"] for u in updates}))
        fig.add_vline(x=mes_str, line=dict(color="#DC2626", width=1.5, dash="dash"))
        fig.add_annotation(
            x=mes_str, y=1.0, yref="paper", text=f"📡 {tipos}", showarrow=False,
            font=dict(size=10, color="#DC2626"), bgcolor="rgba(255,255,255,0.9)",
            bordercolor="#DC2626", borderwidth=1, borderpad=2, yanchor="bottom",
        )


def _trafico_historico_secciones():
    df = dr.secciones_trafico_historico()
    with st.container(border=True, key="card_trafico_historico_secciones"):
        st.subheader("Tráfico real por sección — enero a septiembre 2026")
        st.caption(
            "Tráfico real de GA4 (portal completo), mes a mes. Septiembre es un mes parcial "
            "(1-28 sep) — no está proyectado a mes completo en este gráfico, para no mezclar dato real "
            "con proyección en la misma línea. Las líneas verticales marcan updates de Google conocidos "
            "en ese mes."
        )
        secciones_ordenadas = (
            df.groupby("seccion")["trafico"].sum().sort_values(ascending=False).index.tolist()
        )
        opciones = [OPCION_PORTAL] + [dr.LABELS_SECCION.get(s, s.title()) for s in secciones_ordenadas]
        label_a_id = {dr.LABELS_SECCION.get(s, s.title()): s for s in secciones_ordenadas}
        elegido = st.selectbox("Sección", opciones, key="impacto_algo_seccion_sel")
        es_portal = elegido == OPCION_PORTAL
        secciones_grafico = secciones_ordenadas[:8] if es_portal else [label_a_id[elegido]]

        meses = [p for p, _ in dr.PERIODOS_DISPONIBLES]
        fig = go.Figure()
        for i, seccion in enumerate(secciones_grafico):
            color = COLOR_UNICO if len(secciones_grafico) == 1 else PALETA_SECCIONES[i % len(PALETA_SECCIONES)]
            ancho = 3 if len(secciones_grafico) == 1 else 2.5
            sub = df[df["seccion"] == seccion].set_index("mes").reindex(meses)
            fig.add_trace(go.Scatter(
                x=meses, y=sub["trafico"], mode="lines+markers", connectgaps=False,
                name=dr.LABELS_SECCION.get(seccion, seccion.title()),
                line=dict(color=color, width=ancho),
                marker=dict(size=8 if len(secciones_grafico) == 1 else 6),
                hovertemplate="%{fullData.name}<br>%{x}: %{y:,.0f}<extra></extra>",
            ))
        ultimo_mes = meses[-1]
        if dr.mes_es_parcial(ultimo_mes) and secciones_grafico:
            sub_ultimo = df[(df["seccion"] == secciones_grafico[0]) & (df["mes"] == ultimo_mes)]
            if not sub_ultimo.empty:
                marcar_mes_parcial(fig, dr.MES_CORTO.get(ultimo_mes, ultimo_mes), sub_ultimo.iloc[0]["trafico"])
        _agregar_marcadores_updates(fig, meses)
        fig.update_layout(
            height=380, margin=dict(l=0, r=10, t=40, b=10),
            xaxis=dict(type="category", tickmode="array", tickvals=meses,
                       ticktext=[dr.MES_CORTO.get(m, m) for m in meses]),
            yaxis=dict(showgrid=True, gridcolor="#E2E6ED", rangemode="tozero", title=None),
            plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
            legend=dict(orientation="h", yanchor="bottom", y=1.08, xanchor="left", x=0),
        )
        st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})
        st.caption(
            "Falta el desglose por Search/Discover/News de Search Console (necesita snapshots diarios "
            "que el exportador automático recién empezó a acumular el 22-ago-2026, no reconstruible hacia "
            "atrás con datos reales)."
        )


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
            "⚠️ Search Console tiene un rezago real de reporte de 2-3 días, y acá los 9 meses reales "
            "disponibles (ene-sep 2026) son a nivel MENSUAL, no snapshots diarios — no hay suficiente "
            "granularidad todavía para medir el efecto de un algoritmo específico con confianza. Lo de "
            "abajo es una comparación real septiembre vs. agosto (ritmo diario, no el total crudo), útil como "
            "alerta temprana de qué secciones vienen cayendo — no una atribución a ningún algoritmo en particular.",
            icon="⚠️",
        )


def _ranking_declive():
    df = dr.declive_secciones_jul_ago()
    with st.container(border=True, key="card_ranking_declive"):
        st.subheader("Qué secciones cayeron más — agosto vs. septiembre (ritmo diario real)")
        st.caption(
            "Tráfico real de GA4 dividido por días reales de cada periodo (31 en agosto, 28 en septiembre al "
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
                f'({calc.formatear_numero(r.ritmo_dia_anterior)}/día en agosto → '
                f'{calc.formatear_numero(r.ritmo_dia_actual)}/día en septiembre)</span></div></div>'
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
                       "(verificado agosto 2026 — son updates globales de Google, no específicos de un sitio).")


def _analisis_algoritmo():
    """Qué dice la prensa especializada sobre el August 2026 Spam Update, cruzado
    con los patrones reales de contenido de futbolperuano.com (secciones reales,
    ver ranking de declive arriba). NO es una afirmación de que el algoritmo ya
    afectó al sitio -- es la mejor lectura posible con lo que Google y la prensa
    especializada han confirmado, para saber qué vigilar."""
    with st.container(border=True, key="card_analisis_algoritmo"):
        st.subheader("🔬 Qué sabemos del algoritmo y cómo nos podría afectar")
        st.markdown(
            "**Qué es, según fuentes confirmadas:** el tercer *spam update* de Google en 2026 (después de "
            "marzo y junio). No introduce categorías nuevas de spam — es un refresco de SpamBrain (el "
            "sistema automático) para volver a aplicar las políticas de spam ya existentes con más "
            "precisión. Google confirmó explícitamente que **NO** apunta a *link spam* ni a *site "
            "reputation abuse* — descarta esas dos causas para lo que veamos caer."
        )
        st.markdown(
            "**Qué sí apunta (14 de las 16 políticas de spam de Google), en 3 grupos:**\n"
            "- **Contenido a escala:** *scaled content abuse* (muchas páginas generadas en masa sin "
            "aportar valor real, sea con IA o raspando otras fuentes), *thin content*, dominios expirados "
            "reutilizados, páginas puerta (*doorway*).\n"
            "- **Engaño:** *cloaking*, redirecciones encubiertas, texto oculto, *keyword stuffing*.\n"
            "- **Higiene del sitio:** contenido hackeado, spam generado por usuarios, tráfico malicioso."
        )
        st.warning(
            "⚠️ **Dónde futbolperuano.com tiene un patrón de contenido que podría parecerse a 'contenido "
            "a escala' (sin serlo en la práctica):** las páginas de resultados/tablas de las ligas menores "
            "(Liga 2, Liga 3, Liga Femenina, Copa Perú, Vóley, Futsal) se generan con la misma plantilla "
            "partido tras partido, fecha tras fecha — es justo el tipo de patrón masivo/templado que "
            "describe *scaled content abuse*, aunque acá SÍ hay utilidad real y actualizada para el "
            "usuario (no es spam disfrazado). Con los datos de hoy el grupo viene mixto (ver ranking "
            "arriba): Futsal, Copa Perú y Liga 2 crecen, pero Liga Vóley (-35%, la mayor caída del portal "
            "este periodo), Fútbol Femenino (-18%) y Liga 3 (-6%) caen — no hay una señal clara de "
            "penalización pareja en el grupo, pero Liga Vóley en particular vale la pena vigilar de cerca. "
            "Vale la pena revisar que cada página de resultado tenga contenido genuinamente distinto "
            "(crónica del partido, estadísticas, declaraciones) y no un cascarón idéntico con solo el "
            "marcador cambiado.",
            icon="⚠️",
        )
        st.markdown(
            "**Lo que YA está cayendo (ver ranking arriba):** Liga Vóley (-35%), Copa Sudamericana (-19%), "
            "Fútbol Femenino (-18%), Liga 1 (-17%) y Copa de la Liga (-15%) son las mayores caídas de "
            "ritmo diario real de agosto a septiembre. No tenemos todavía un cruce confirmado con el "
            "calendario deportivo real de cada torneo (fin de fase, receso, fecha FIFA) para saber cuánto "
            "de esto es coyuntura editorial y cuánto no — antes de tratar esto como señal del algoritmo, "
            "toca verificar caso por caso si el torneo respectivo sigue activo. Ninguno de los 3 grupos "
            "que apunta este update (escala/engaño/higiene) describe bien estas secciones por sí solo, lo "
            "que hace más probable coyuntura que efecto del algoritmo, pero es una lectura razonada, no "
            "un dato confirmado."
        )
        st.markdown(
            "**Qué vigilar cuando haya más datos post-algoritmo:** Liga Vóley ya cayó -35% este periodo — "
            "si el resto de ligas menores (Liga 2, Liga 3, Copa Perú, Futsal) empieza a seguirla en vez de "
            "seguir creciendo, es la señal más clara de que el algoritmo sí está afectando contenido "
            "templado real. Si en cambio Liga Vóley queda como caso aislado (verificable contra su "
            "calendario real) y las demás siguen creciendo, refuerza que es coyuntura y no el algoritmo."
        )
        st.caption(
            "Fuentes: "
            "[Search Engine Journal](https://www.searchenginejournal.com/google-begins-rolling-out-the-august-2026-spam-update/586301/) · "
            "[ppc.land](https://ppc.land/googles-third-spam-update-of-2026-hits-every-language-and-region/) · "
            "[On-Page.ai](https://blog.on-page.ai/august-2026-spam-update/) · "
            "[Coalition Technologies](https://coalitiontechnologies.com/blog/google-august-2026-spam-update) · "
            "[Google Search Central — políticas de spam](https://developers.google.com/search/docs/essentials/spam-policies)"
        )


def render():
    _header_algoritmo()
    st.write("")
    _trafico_historico_secciones()
    st.write("")
    _ranking_declive()
    st.write("")
    _analisis_algoritmo()
    st.write("")
    _updates_detalle()
