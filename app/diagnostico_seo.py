"""Vista Diagnóstico SEO — auditoría técnica real de futbolperuano.com (robots.txt,
sitemap, canonical, HTTPS/seguridad, indexabilidad). Espejo de
calculadora-periodistas/app/diagnostico_seo.py (colombia.com): auditoría puntual,
no un pipeline recurrente. Corrida el 22-ago-2026 vía fetch real (requests +
BeautifulSoup), no un modelo de lenguaje adivinando. Core Web Vitals de campo
(PageSpeed Insights) quedan pendientes -- necesitan PAGESPEED_API_KEY, no
configurada en este proyecto todavía."""

import html

import streamlit as st

from estilos import kpi_card

FECHA_AUDITORIA = "22 de agosto de 2026"

ESTADO_GENERAL = {
    "nivel": "amarillo",
    "resumen": "Base técnica sana (HTTPS, sitemap, canonical, indexabilidad) — el hallazgo real más "
               "grande no es técnico sino de contenido: 0% de las notas de agosto tiene un title tag en "
               "el rango correcto (ver Dashboard → Semáforo SEO).",
}

KPIS = [
    {"icono": "🔒", "label": "HTTPS + HSTS", "valor": "Sí", "help": "Redirección 301 http→https confirmada, header Strict-Transport-Security presente"},
    {"icono": "🗺️", "label": "Sitemap", "valor": "Válido", "help": "sitemap.xml → sitemap index → 10.000 URLs, lastmod fresco (mismo día)"},
    {"icono": "🔗", "label": "Canonical", "valor": "Presente", "help": "Auto-referenciado en la nota verificada — sin señal de duplicado"},
    {"icono": "📱", "label": "Viewport móvil", "valor": "Configurado", "help": "width=device-width, initial-scale=1 — responsive declarado"},
]

HALLAZGO_PRINCIPAL = (
    "La base técnica está sana: HTTPS forzado con HSTS, robots.txt referencia el sitemap correctamente, "
    "el sitemap es válido y está fresco (actualizado el mismo día), las notas indexables llevan "
    "`index,follow`, canonical auto-referenciado y viewport móvil configurado. **El problema real no es "
    "técnico, es de contenido**: el semáforo SEO real de agosto (526 notas, censo completo) encontró que "
    "el 0% de las notas tiene un title tag en el rango correcto (50-65 caracteres — la muestra real midió "
    "75-111) y solo el 1.3% tiene meta descripción en rango (150-170 caracteres). Esto se ve consistente "
    "en los 7 periodistas, lo que sugiere una plantilla/CMS que no está limitando la longitud del title en "
    "el editor, no un hábito individual — vale la pena confirmarlo con quien administra la plantilla antes "
    "de tratarlo como una corrección editorial nota por nota."
)

MATRIZ_ACCIONES = [
    {"accion": "Acortar el title SEO a 50-65 caracteres (revisar si el editor de contenido permite fijar "
               "un title distinto del H1, o si el CMS lo trunca automático)", "area": "Plantilla/CMS",
     "esfuerzo": "Media", "severidad": "Alta"},
    {"accion": "Ajustar meta descripción a 150-170 caracteres (hoy sistemáticamente corta, 117-134 en la "
               "muestra)", "area": "Plantilla/CMS", "esfuerzo": "Media", "severidad": "Alta"},
    {"accion": "Agregar Content-Security-Policy (ausente en los headers de respuesta)", "area": "Seguridad",
     "esfuerzo": "Media", "severidad": "Media"},
    {"accion": "Confirmar por qué el checklist mide extensión <400 palabras en 65% de las notas — puede "
               "ser correcto editorial para notas de resultado rápido, pero vale confirmarlo",
     "area": "Editorial", "esfuerzo": "Baja", "severidad": "Media"},
    {"accion": "Medir Core Web Vitals de campo real (requiere configurar PAGESPEED_API_KEY)",
     "area": "Performance", "esfuerzo": "Baja", "severidad": "Media"},
]

URGENTES = []  # nada confirmado como urgente en esta auditoría puntual

COBERTURA_VERIFICADA = [
    "robots.txt (fetch real, referencia correcta al sitemap)",
    "sitemap.xml → sitemap index → 10.000 URLs (fetch real, lastmod fresco)",
    "HTTPS forzado (redirección 301 real desde http://)",
    "Headers de seguridad (HSTS, X-Content-Type-Options, X-Frame-Options, CSP)",
    "Canonical y meta robots en una nota real (liga-1)",
    "Viewport móvil declarado",
    "JSON-LD: NewsMediaOrganization + NewsArticle + BreadcrumbList presentes y bien formados",
    "Semáforo SEO on-page real (526 notas de agosto, ver Dashboard)",
]
COBERTURA_PENDIENTE = [
    "Core Web Vitals de campo (LCP/CLS/INP) — necesita PAGESPEED_API_KEY",
    "Auditoría de rendimiento en más de 1 plantilla de nota (solo se verificó liga-1/noticias/)",
    "Auditoría de las páginas utilitarias (tablas de posiciones, partidos por TV) — foco de esta ronda "
    "fue el contenido editorial",
    "Enlaces rotos / crawl completo del sitio (auditoría puntual, no un crawler corrido todavía)",
]

ESTADO_COLOR = {"verde": ("#DCFCE7", "#166534", "🟢"), "amarillo": ("#FEF3C7", "#92400E", "🟡"),
                "rojo": ("#FEE2E2", "#991B1B", "🔴")}
SEVERIDAD_COLOR = {"Alta": ("#FEE2E2", "#991B1B"), "Media": ("#FEF3C7", "#92400E"), "Baja": ("#F1F5F9", "#475569")}


def _encabezado():
    bg, fg, icono = ESTADO_COLOR[ESTADO_GENERAL["nivel"]]
    st.subheader("🔍 Diagnóstico SEO — futbolperuano.com")
    st.caption(f"Auditoría técnica real, corrida el {FECHA_AUDITORIA} (fetch real con requests+BeautifulSoup, "
               "no una suposición). Puntual, no un pipeline recurrente — si pasó mucho tiempo, vale la pena "
               "volver a correrla.")
    st.markdown(
        f'<div style="background:{bg};color:{fg};border-radius:10px;padding:10px 16px;'
        f'font-weight:600;margin-bottom:14px">{icono} {html.escape(ESTADO_GENERAL["resumen"])}</div>',
        unsafe_allow_html=True,
    )


def _kpis():
    tarjetas = [kpi_card(k["icono"], k["label"], k["valor"], help_text=k.get("help", "")) for k in KPIS]
    st.markdown(f'<div class="cp-kpi-row" style="grid-template-columns:repeat(4,1fr)">{"".join(tarjetas)}</div>',
                unsafe_allow_html=True)


def _hallazgo_principal():
    st.write("")
    with st.container(border=True, key="card_hallazgo_seo"):
        st.markdown("#### 🎯 Hallazgo principal")
        st.markdown(HALLAZGO_PRINCIPAL)


def _matriz_acciones():
    st.write("")
    st.markdown("#### 📋 Matriz de acciones priorizadas")
    for a in MATRIZ_ACCIONES:
        bg, fg = SEVERIDAD_COLOR.get(a["severidad"], SEVERIDAD_COLOR["Media"])
        st.markdown(
            f'<div style="display:flex;align-items:center;justify-content:space-between;gap:14px;'
            f'background:#FFFFFF;border:1px solid #E7EAF0;border-radius:10px;padding:10px 16px;margin-bottom:8px">'
            f'<div style="min-width:0">'
            f'<div style="font-weight:600;color:#1A1A1A;font-size:1rem">{html.escape(a["accion"])}</div>'
            f'<div style="font-size:0.92rem;color:#64748B;margin-top:2px">{html.escape(a["area"])} · '
            f'esfuerzo {html.escape(a["esfuerzo"]).lower()}</div></div>'
            f'<div style="flex-shrink:0;background:{bg};color:{fg};border-radius:999px;padding:4px 12px;'
            f'font-size:0.88rem;font-weight:700;white-space:nowrap">{html.escape(a["severidad"])}</div>'
            f'</div>',
            unsafe_allow_html=True,
        )


def _urgentes():
    st.write("")
    with st.container(border=True, key="card_urgentes_seo"):
        st.markdown("#### 🚨 Correcciones urgentes")
        if not URGENTES:
            st.success("Nada urgente confirmado en esta auditoría.")
            return
        for u in URGENTES:
            st.markdown(f'<div style="background:#FEE2E2;color:#991B1B;border-radius:8px;padding:8px 12px;'
                        f'margin-top:6px;font-size:0.92rem">🔴 {u}</div>', unsafe_allow_html=True)


def _cwv():
    st.write("")
    st.markdown("#### ⚡ Core Web Vitals (datos de campo reales, mobile)")
    st.caption("Vía PageSpeed Insights API — percentil 75 de usuarios reales (CrUX), no estimación de laboratorio.")
    st.info("Sin datos de CWV todavía — necesita `PAGESPEED_API_KEY` configurada, no lo está en este "
            "proyecto por ahora. No se estima ni se inventa un valor.")


def _cobertura():
    st.write("")
    with st.expander("🔬 Cobertura de esta auditoría (transparencia)"):
        col_ok, col_pend = st.columns(2)
        with col_ok:
            st.markdown("**Verificado con fetch real:**")
            for item in COBERTURA_VERIFICADA:
                st.markdown(f"✅ {item}")
        with col_pend:
            st.markdown("**Pendiente (no confirmado ni descartado):**")
            for item in COBERTURA_PENDIENTE:
                st.markdown(f"⏳ {item}")


def render():
    _encabezado()
    _kpis()
    _hallazgo_principal()
    _matriz_acciones()
    _urgentes()
    _cwv()
    _cobertura()
