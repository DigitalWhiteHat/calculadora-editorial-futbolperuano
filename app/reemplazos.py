"""Vista Reemplazos — para cada periodista, quién del resto del equipo podría
cubrir su sección principal si falta. Espejo de
calculadora-periodistas/app/reemplazos.py (colombia.com), con ene-sep 2026
(9 meses reales, misma profundidad que el original). No depende del selector
de periodo."""

import streamlit as st

import calculos as calc
import datos_reales as dr
from avatares import avatar_data_uri
from estilos import kpi_card

ICONO_CONFIANZA = {"alta": "🟢", "media": "🟡", "baja": "⚪"}
ORDEN_CONFIANZA = {"alta": 0, "media": 1, "baja": 2}
MAX_CANDIDATOS = 3


def _color_cobertura(ratio):
    if ratio >= 0.9:
        return "green", "Cobertura equivalente o mejor"
    if ratio >= 0.6:
        return "blue", "Cobertura aceptable, con caída esperada"
    return "red", "Cobertura débil — el tráfico caería de forma notoria"


def _candidatos(esp, titular, seccion_raw, eficiencia_titular):
    candidatos = esp[(esp["seccion"] == seccion_raw) & (esp["autor"] != titular)].copy()
    if candidatos.empty:
        return candidatos
    tiene_baseline = eficiencia_titular is not None and eficiencia_titular > 0
    candidatos["ratio_eficiencia"] = candidatos["trafico_por_nota"] / eficiencia_titular if tiene_baseline else float("nan")
    candidatos["orden_confianza"] = candidatos["confianza"].map(ORDEN_CONFIANZA)
    return candidatos.sort_values(["orden_confianza", "ratio_eficiencia", "trafico_por_nota"], ascending=[True, False, False])


def _nivel_respaldo(candidatos):
    if candidatos.empty:
        return "🔴", "Sin candidato con experiencia en esta sección"
    mejores = candidatos[candidatos["confianza"].isin(["alta", "media"])]
    if mejores.empty:
        return "🟡", "Solo candidatos con experiencia mínima (⚪ baja confianza)"
    if (mejores["ratio_eficiencia"] >= 0.9).any() or mejores["ratio_eficiencia"].isna().all():
        return "🟢", "Respaldo con experiencia consolidada en la sección"
    return "🟡", "Respaldo con experiencia, eficiencia por debajo del titular"


def _tarjeta_candidato(row, rank, recomendado):
    if row["ratio_eficiencia"] == row["ratio_eficiencia"]:
        color_key, texto_cobertura = _color_cobertura(row["ratio_eficiencia"])
    else:
        color_key, texto_cobertura = "blue", "Sin base de comparación (titular sin datos en esta sección)"
    bg, fg = {"green": ("#DCFCE7", "#166534"), "blue": ("#DBEAFE", "#1E40AF"), "red": ("#FEE2E2", "#991B1B")}[color_key]
    ratio_txt = f"{row['ratio_eficiencia'] * 100:.0f}% de la eficiencia del titular" if row["ratio_eficiencia"] == row["ratio_eficiencia"] else "—"
    etiqueta_rank = "★ Reemplazo recomendado" if recomendado else f"Opción {rank}"
    st.markdown(
        f'<div style="display:flex;align-items:center;justify-content:space-between;gap:14px;'
        f'background:{bg};border-radius:12px;padding:12px 16px;margin-bottom:8px">'
        f'<div style="min-width:0">'
        f'<div style="font-weight:700;font-size:1.05rem;color:#1A1A1A">{etiqueta_rank} — {row["autor"]}</div>'
        f'<div style="font-size:0.95rem;color:#475569;margin-top:2px">'
        f'{ICONO_CONFIANZA.get(row["confianza"], "⚪")} confianza {row["confianza"]} · '
        f'{int(row["notas"])} notas en ene-sep · {row["trafico_por_nota"]:,.0f} tráfico/nota</div></div>'
        f'<div style="text-align:right;flex-shrink:0">'
        f'<div style="font-weight:700;color:{fg};font-size:0.92rem;letter-spacing:0.02em">{texto_cobertura.upper()}</div>'
        f'<div style="font-size:0.9rem;color:#64748B;margin-top:2px">{ratio_txt}</div>'
        f'</div></div>'.replace(",", "."),
        unsafe_allow_html=True,
    )


def _tarjeta_titular(meta, tabla, esp):
    fila = tabla[tabla["slug"] == meta["slug"]]
    eficiencia_titular = None
    fila_esp_propia = esp[(esp["autor"] == meta["nombre"]) & (esp["seccion"] == meta["seccion_raw"])]
    if not fila_esp_propia.empty:
        eficiencia_titular = float(fila_esp_propia.iloc[0]["trafico_por_nota"])

    candidatos = _candidatos(esp, meta["nombre"], meta["seccion_raw"], eficiencia_titular)
    icono_nivel, texto_nivel = _nivel_respaldo(candidatos)
    label_seccion = dr.LABELS_SECCION.get(meta["seccion_raw"], meta["seccion_raw"].title())

    with st.container(border=True, key=f"card_reemplazo_{meta['slug']}"):
        col_foto, col_info = st.columns([1, 6], vertical_alignment="center")
        with col_foto:
            st.markdown(
                f'<img class="cp-avatar-perfil" style="width:56px !important;height:56px !important;'
                f'min-width:56px !important;max-width:56px !important;max-height:56px !important" '
                f'src="{avatar_data_uri(meta["nombre"], "#1A1A1A", 120)}">',
                unsafe_allow_html=True,
            )
        with col_info:
            notas_periodo = f"{int(fila.iloc[0]['notas'])} notas este periodo" if not fila.empty else "sin notas este periodo"
            st.markdown(f"**{meta['nombre']}** — sección principal: **{label_seccion}** ({notas_periodo})")
            st.caption(f"{icono_nivel} {texto_nivel}")

        if candidatos.empty:
            st.warning(f"Ningún otro periodista tiene notas registradas en {label_seccion} en ene-sep — "
                       "no hay candidato con experiencia directa.")
            return
        for i, (_, row) in enumerate(candidatos.head(MAX_CANDIDATOS).iterrows(), start=1):
            _tarjeta_candidato(row, i, recomendado=(i == 1))


def _color_desempeno_seccion(ratio):
    if ratio != ratio:
        return "blue", "Sin mediana de sección para comparar"
    if ratio >= 0.9:
        return "green", "Rendimiento igual o mejor que la mediana de la sección"
    if ratio >= 0.6:
        return "blue", "Rendimiento por debajo de la mediana, con experiencia real"
    return "red", "Rendimiento bajo en esta sección hasta ahora"


def _tarjeta_candidato_seccion(row, rank):
    color_key, texto = _color_desempeno_seccion(row["ratio_mediana"])
    bg, fg = {"green": ("#DCFCE7", "#166534"), "blue": ("#DBEAFE", "#1E40AF"), "red": ("#FEE2E2", "#991B1B")}[color_key]
    ratio_txt = f"{row['ratio_mediana'] * 100:.0f}% de la mediana de la sección" if row["ratio_mediana"] == row["ratio_mediana"] else "—"
    etiqueta_rank = "★ Mejor opción" if rank == 1 else f"Opción {rank}"
    st.markdown(
        f'<div style="display:flex;align-items:center;justify-content:space-between;gap:14px;'
        f'background:{bg};border-radius:12px;padding:12px 16px;margin-bottom:8px">'
        f'<div style="min-width:0">'
        f'<div style="font-weight:700;font-size:1.05rem;color:#1A1A1A">{etiqueta_rank} — {row["autor"]}</div>'
        f'<div style="font-size:0.95rem;color:#475569;margin-top:2px">'
        f'{ICONO_CONFIANZA.get(row["confianza"], "⚪")} confianza {row["confianza"]} · '
        f'{int(row["notas"])} notas en ene-sep · {row["trafico_por_nota"]:,.0f} tráfico/nota</div></div>'
        f'<div style="text-align:right;flex-shrink:0">'
        f'<div style="font-weight:700;color:{fg};font-size:0.92rem;letter-spacing:0.02em">{texto.upper()}</div>'
        f'<div style="font-size:0.9rem;color:#64748B;margin-top:2px">{ratio_txt}</div>'
        f'</div></div>'.replace(",", "."),
        unsafe_allow_html=True,
    )


def _bloque_por_seccion(periodistas_meta, esp, tabla_periodistas):
    st.subheader("¿Qué periodista podría tomar esta sección?")
    st.caption(
        "Vista inversa: eliges una sección y ves quién del equipo, sin ser ya su titular, tiene mejor "
        "base real para asumirla. Quienes nunca han escrito en la sección se listan aparte, sin "
        "inventarles un número."
    )
    secciones_disponibles = sorted(esp["seccion"].unique())
    with st.container(border=True, key="card_seccion_selector"):
        seccion_elegida = st.selectbox("Sección que necesita más cobertura", secciones_disponibles,
                                        format_func=lambda s: dr.LABELS_SECCION.get(s, s.title()),
                                        key="reemplazo_seccion_elegida")
    label_seccion = dr.LABELS_SECCION.get(seccion_elegida, seccion_elegida.title())
    dominantes = set(tabla_periodistas[tabla_periodistas["seccion_raw"] == seccion_elegida]["periodista"])
    st.write("")
    with st.container(border=True, key="card_seccion_candidatos"):
        if dominantes:
            st.caption(f"Ya escriben {label_seccion} como su sección principal: {', '.join(sorted(dominantes))}.")
        candidatos = esp[(esp["seccion"] == seccion_elegida) & (~esp["autor"].isin(dominantes))].copy()
        if not candidatos.empty:
            mediana = candidatos["mediana_seccion_otros"].iloc[0]
            candidatos["ratio_mediana"] = candidatos["trafico_por_nota"] / mediana if mediana else float("nan")
            candidatos["orden_confianza"] = candidatos["confianza"].map(ORDEN_CONFIANZA)
            candidatos = candidatos.sort_values(["orden_confianza", "trafico_por_nota"], ascending=[True, False])
            for i, (_, row) in enumerate(candidatos.head(MAX_CANDIDATOS).iterrows(), start=1):
                _tarjeta_candidato_seccion(row, i)
        else:
            st.info(f"Nadie más del equipo tiene notas registradas en {label_seccion} en ene-sep.")

        con_datos = set(esp[esp["seccion"] == seccion_elegida]["autor"]) | dominantes
        sin_experiencia = sorted(p["nombre"] for p in periodistas_meta if p["nombre"] not in con_datos)
        if sin_experiencia:
            st.caption(f"Sin experiencia registrada en {label_seccion}: {', '.join(sin_experiencia)}.")


def _kpis(periodistas_meta, tabla, esp):
    niveles = []
    for meta in periodistas_meta:
        fila_esp_propia = esp[(esp["autor"] == meta["nombre"])]
        if fila_esp_propia.empty:
            niveles.append("🔴")
            continue
        seccion_raw = fila_esp_propia.sort_values("notas", ascending=False).iloc[0]["seccion"]
        eficiencia_titular = float(fila_esp_propia[fila_esp_propia["seccion"] == seccion_raw].iloc[0]["trafico_por_nota"])
        candidatos = _candidatos(esp, meta["nombre"], seccion_raw, eficiencia_titular)
        icono, _ = _nivel_respaldo(candidatos)
        niveles.append(icono)
    tarjetas = [
        kpi_card("👥", "Periodistas evaluados", f"{len(niveles)}"),
        kpi_card("🟢", "Con respaldo consolidado", f"{niveles.count('🟢')}"),
        kpi_card("🟡", "Con respaldo parcial", f"{niveles.count('🟡')}"),
        kpi_card("🔴", "Sin ningún respaldo", f"{niveles.count('🔴')}"),
    ]
    st.markdown(f'<div class="cp-kpi-row">{"".join(tarjetas)}</div>', unsafe_allow_html=True)


def render(tabla_periodistas):
    st.subheader("¿Quién puede reemplazar a quién?")
    st.caption(
        "Para cubrir vacaciones, incapacidades o permisos sin afectar el tráfico de la sección: "
        "candidatos con experiencia REAL de ene-sep 2026 (9 meses de censo completo) en la sección "
        "principal de cada periodista. Confianza: 🟢 alta (≥10 notas) · 🟡 media (3-9) · ⚪ baja (<3). "
        "No mide calidad editorial — solo si el candidato ya genera tráfico comparable ahí mismo."
    )
    esp = dr.especializacion_todos()
    if esp.empty:
        st.info("El cruce periodista × sección todavía se está procesando.")
        return

    periodistas_meta = dr.cargar_periodistas_meta()
    _kpis(periodistas_meta, tabla_periodistas, esp)
    st.write("")

    nombres = sorted(p["nombre"] for p in periodistas_meta)
    with st.container(border=True, key="card_reemplazo_selector"):
        elegido = st.selectbox("Si esta persona falta, ¿quién la puede reemplazar?", nombres,
                                key="reemplazo_periodista_elegido")
    meta = next(p for p in periodistas_meta if p["nombre"] == elegido)
    fila_actual = tabla_periodistas[tabla_periodistas["slug"] == meta["slug"]]
    meta["seccion_raw"] = fila_actual.iloc[0]["seccion_raw"] if not fila_actual.empty else (
        esp[esp["autor"] == elegido].sort_values("notas", ascending=False).iloc[0]["seccion"]
        if not esp[esp["autor"] == elegido].empty else None)
    st.write("")
    if meta["seccion_raw"]:
        _tarjeta_titular(meta, tabla_periodistas, esp)
    else:
        st.caption("Sin sección principal identificada para este periodista todavía.")

    st.write("")
    st.divider()
    _bloque_por_seccion(periodistas_meta, esp, tabla_periodistas)
