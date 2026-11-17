"""
Generacion del PDF de un reporte de diagnostico (D-012: procesamiento
separado de los endpoints; este modulo no sabe nada de FastAPI ni de la
base de datos, solo recibe datos ya calculados y devuelve bytes de PDF).
"""

import io

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import (
    Image,
    KeepInFrame,
    ListFlowable,
    ListItem,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from backend.procesamiento.ejes import ejes_en_datos_fft

COLORES_EJE = {"x": "#14b8a6", "y": "#38bdf8", "z": "#a78bfa"}


def marcar_frecuencias(eje_grafico, frecuencias):
    """
    Dibuja una linea vertical en cada frecuencia y, ARRIBA del area del
    grafico (no encima de la curva), una etiqueta con el nombre y el
    valor exacto en Hz - para no tener que adivinar el valor de un pico
    a ojo. Usa get_xaxis_transform() para que la coordenada Y quede en
    fraccion de los ejes (por encima de 1.0 = fuera del area de trazado)
    mientras la X sigue en unidades de datos (la frecuencia real).
    """
    transformacion = eje_grafico.get_xaxis_transform()
    for nombre, frecuencia in frecuencias.items():
        eje_grafico.axvline(frecuencia, color="#94a3b8", linestyle="--", linewidth=1)
        eje_grafico.text(
            frecuencia, 1.02, f"{nombre}\n{frecuencia:.1f} Hz",
            transform=transformacion, ha="center", va="bottom",
            fontsize=8, color="#475569",
        )


def graficar_espectro(datos_fft, frecuencias_esperadas):
    """Devuelve un PNG (bytes) del espectro FFT con 1x/2x/3x marcados (sin la componente continua, 0 Hz)."""
    # El 0 Hz es el desplazamiento del sensor, no vibracion: puede ser decenas de veces mayor que el 1x
    # y aplastar la escala. Solo se omite al graficar; el diagnostico usa el espectro completo.
    datos_fft = [d for d in datos_fft if d["frecuencia"] > 0]
    frecuencias = [d["frecuencia"] for d in datos_fft]

    figura, eje_grafico = plt.subplots(figsize=(16, 7))

    for eje in ejes_en_datos_fft(datos_fft):
        eje_grafico.plot(
            frecuencias,
            [d[f"amplitud_{eje}"] for d in datos_fft],
            label=f"Eje {eje.upper()}",
            color=COLORES_EJE[eje],
            linewidth=1.2,
        )

    marcar_frecuencias(eje_grafico, frecuencias_esperadas)

    eje_grafico.set_xlabel("Frecuencia [Hz]")
    eje_grafico.set_ylabel("Amplitud")
    eje_grafico.legend(loc="upper right")
    eje_grafico.grid(alpha=0.3)

    buffer = io.BytesIO()
    figura.savefig(buffer, format="png", dpi=130, bbox_inches="tight")
    plt.close(figura)
    buffer.seek(0)
    return buffer


def graficar_envolvente(datos_grafico):
    """Espectro de envolvente con BPFO/BPFI/BSF/FTF marcados."""
    espectro = datos_grafico["frecuencias_espectro"]
    amplitudes = datos_grafico["amplitudes_espectro"]

    figura, eje_grafico = plt.subplots(figsize=(16, 6))
    eje_grafico.plot(espectro, amplitudes, color=COLORES_EJE.get(datos_grafico["eje"], "#14b8a6"), linewidth=1.2)

    marcar_frecuencias(eje_grafico, datos_grafico["frecuencias_falla"])

    eje_grafico.set_xlabel("Frecuencia [Hz]")
    eje_grafico.set_ylabel("Amplitud (envolvente)")
    eje_grafico.set_title(f"Espectro de envolvente — eje {datos_grafico['eje'].upper()}", fontsize=10)
    eje_grafico.grid(alpha=0.3)

    buffer = io.BytesIO()
    figura.savefig(buffer, format="png", dpi=130, bbox_inches="tight")
    plt.close(figura)
    buffer.seek(0)
    return buffer


def graficar_senal_envolvente(datos_grafico):
    """Señal filtrada en la banda de resonancia, con su curva de envolvente (Hilbert) superpuesta."""
    tiempo = datos_grafico["tiempo"]
    señal = datos_grafico["señal"]
    envolvente = datos_grafico["envolvente_tiempo"]
    banda = datos_grafico.get("banda_demodulacion_hz")

    figura, eje_grafico = plt.subplots(figsize=(16, 6))
    eje_grafico.plot(tiempo, señal, color="#94a3b8", linewidth=0.6, label="Señal filtrada en la banda de resonancia")
    eje_grafico.plot(tiempo, envolvente, color="#ef4444", linewidth=1.6, label="Envolvente (Hilbert)")

    eje_grafico.set_xlabel("Tiempo [s]")
    eje_grafico.set_ylabel("Amplitud")
    texto_banda = f", banda {banda[0] / 1000:.1f}–{banda[1] / 1000:.1f} kHz" if banda else ""
    eje_grafico.set_title(
        f"Señal filtrada y su envolvente (primeros {tiempo[-1] * 1000:.0f} ms) — eje {datos_grafico['eje'].upper()}{texto_banda}",
        fontsize=10,
    )
    eje_grafico.legend(loc="upper right")
    eje_grafico.grid(alpha=0.3)

    buffer = io.BytesIO()
    figura.savefig(buffer, format="png", dpi=130, bbox_inches="tight")
    plt.close(figura)
    buffer.seek(0)
    return buffer


def pagina_resumen_ia(resumen_ia, equipo, fecha_generacion, estilos):
    """
    Pagina adicional "Resumen redactado por IA" (redaccion_ia.py). Va al final del reporte, que no cambia. Todo el
    contenido se encoge para caber en UNA sola pagina, sea cual sea el largo del texto.
    """
    estilo_titulo = ParagraphStyle("TituloIA", parent=estilos["Title"], fontSize=18, spaceAfter=4)
    estilo_subtitulo = ParagraphStyle("SubtituloIA", parent=estilos["Normal"], fontSize=10, textColor=colors.grey)
    estilo_h2 = ParagraphStyle("H2IA", parent=estilos["Heading2"], spaceBefore=14, spaceAfter=6)
    estilo_aviso = ParagraphStyle(
        "AvisoIA", parent=estilos["Normal"], fontSize=8.5, leading=11, textColor=colors.HexColor("#475569"),
        borderColor=colors.HexColor("#cbd5e1"), borderWidth=0.6, borderPadding=6, backColor=colors.HexColor("#f1f5f9"),
    )
    estilo_texto = ParagraphStyle("TextoIA", parent=estilos["Normal"], fontSize=10.5, leading=14.5)

    contenido = [
        Paragraph("Resumen redactado por IA", estilo_titulo),
        Paragraph(f"Equipo: {equipo['nombre']} · Reporte generado: {fecha_generacion}", estilo_subtitulo),
        Spacer(1, 0.5 * cm),
        Paragraph(
            f"Texto redactado con inteligencia artificial (modelo {resumen_ia['modelo']}, {resumen_ia['fecha']}). "
            "Se basa solo en los resultados de este reporte: no modifica el diagnóstico, las confianzas ni las cifras, y "
            "debe ser revisado por el analista. La confianza es el puntaje de la evidencia encontrada por las reglas, no "
            "la probabilidad de que el equipo falle.",
            estilo_aviso,
        ),
        Paragraph("Resumen", estilo_h2),
    ]
    for parrafo in [p.strip() for p in resumen_ia["resumen"].split("\n") if p.strip()]:
        contenido.append(Paragraph(parrafo, estilo_texto))
        contenido.append(Spacer(1, 0.2 * cm))

    if resumen_ia["observaciones"]:
        contenido.append(Paragraph("Observaciones de la IA", estilo_h2))
        contenido.append(ListFlowable(
            [ListItem(Paragraph(o, estilo_texto)) for o in resumen_ia["observaciones"]],
            bulletType="bullet",
        ))
    else:
        contenido.append(Paragraph("Observaciones de la IA", estilo_h2))
        contenido.append(Paragraph("La IA no encontró aspectos que advertir.", estilo_texto))

    ancho, alto = A4
    return [KeepInFrame(ancho - 3 * cm, alto - 3.4 * cm, contenido, mode="shrink")]


def generar_pdf_reporte(reporte, graficos_rodamiento=None):
    """
    reporte: {
        "equipo": {"nombre", "tipo", "planta", "rpm_nominal"},
        "fecha_generacion": str,
        "resumen_ia": dict opcional de redaccion_ia.redactar_resumen: agrega al final UNA pagina "Resumen redactado
            por IA" (el resto del reporte no cambia),
        "sensores": [
            {
                "sensor_id", "nombre_tipo", "tiene_medicion": bool,
                "mensaje": str opcional (si no tiene medicion),
                "diagnostico": dict devuelto por diagnosticar_sensor,
                "datos_fft": lista opcional (para graficar),
            },
            ...
        ],
    }
    graficos_rodamiento: {sensor_id: dict devuelto por
        diagnostico_rodamientos.py::calcular_datos_grafico (numpy sin
        serializar)} - opcional, uno por sensor con rodamiento vinculado
        y geometria completa.

    Devuelve los bytes del PDF generado.
    """
    graficos_rodamiento = graficos_rodamiento or {}
    estilos = getSampleStyleSheet()
    estilo_titulo = ParagraphStyle(
        "TituloReporte", parent=estilos["Title"], fontSize=18, spaceAfter=4,
    )
    estilo_subtitulo = ParagraphStyle(
        "Subtitulo", parent=estilos["Normal"], fontSize=10, textColor=colors.grey,
    )
    estilo_h2 = ParagraphStyle(
        "H2Reporte", parent=estilos["Heading2"], spaceBefore=16, spaceAfter=6,
    )
    estilo_normal = estilos["Normal"]
    estilo_celda = ParagraphStyle("CeldaTabla", parent=estilos["Normal"], fontSize=8.5, leading=10.5)

    elementos = []

    equipo = reporte["equipo"]
    elementos.append(Paragraph(f"Reporte de diagnóstico — {equipo['nombre']}", estilo_titulo))
    elementos.append(Paragraph(
        f"Tipo: {equipo.get('tipo') or '—'} · Planta: {equipo.get('planta') or '—'} · "
        f"RPM nominal: {equipo.get('rpm_nominal') or '—'}",
        estilo_subtitulo,
    ))
    elementos.append(Paragraph(f"Generado: {reporte['fecha_generacion']}", estilo_subtitulo))
    elementos.append(Spacer(1, 0.6 * cm))

    for sensor in reporte["sensores"]:
        elementos.append(Paragraph(f"Sensor: {sensor['nombre_tipo']}", estilo_h2))

        if not sensor["tiene_medicion"]:
            elementos.append(Paragraph(sensor["mensaje"], estilo_normal))
            continue

        diagnostico = sensor["diagnostico"]

        severidad_iso = diagnostico.get("severidad_iso")
        if severidad_iso and severidad_iso["aplicable"]:
            elementos.append(Paragraph(
                f"<b>Severidad ISO 20816-3:</b> Zona {severidad_iso['zona']} "
                f"({severidad_iso['severidad']}) — velocidad RMS {severidad_iso['velocidad_rms_mm_s']:.2f} mm/s "
                f"· {severidad_iso['accion_recomendada'].replace('_', ' ')}",
                estilo_normal,
            ))
        elif severidad_iso:
            elementos.append(Paragraph(
                f"<b>Severidad ISO 20816-3:</b> no evaluable — {severidad_iso['motivo_no_aplicable']}",
                estilo_normal,
            ))

        cambio = diagnostico.get("cambio_linea_base")
        if cambio and cambio["aplicable"]:
            niveles = {"sin_cambio": "sin cambio relevante", "elevado": "elevado", "muy_elevado": "muy elevado", "disminuyo": "disminuyó"}
            elementos.append(Paragraph(
                f"<b>Cambio respecto de la línea base:</b> {niveles.get(cambio['nivel'], cambio['nivel'])} — "
                f"velocidad RMS {cambio['velocidad_rms_actual_mm_s']:.2f} mm/s frente a "
                f"{cambio['velocidad_rms_referencia_mm_s']:.2f} mm/s de la referencia ({cambio['razon']:g} veces; "
                f"banda {cambio['banda_hz'][0]:g}–{cambio['banda_hz'][1]:.0f} Hz, peor eje). "
                "Por eje: "
                + " · ".join(f"{eje.upper()} ×{v['razon'] if v['razon'] is not None else '—'}" for eje, v in cambio["por_eje"].items())
                + ". Criterio relativo del proyecto, no una norma.",
                estilo_normal,
            ))
        elif cambio:
            elementos.append(Paragraph(
                f"<b>Cambio respecto de la línea base:</b> no evaluable — {cambio['motivo_no_aplicable']}",
                estilo_normal,
            ))

        velocidad = diagnostico.get("velocidad")
        if velocidad:
            origenes = {"medida": "declarada en la medición", "estimada": "estimada desde el espectro", "nominal": "nominal del equipo"}
            texto_velocidad = (
                f"<b>Velocidad de giro usada:</b> {velocidad['rpm']:.0f} r/min "
                f"({origenes.get(velocidad['origen'], velocidad['origen'])}"
                + (f", {velocidad['desviacion_pct']:+.1f}% respecto de la nominal" if velocidad["origen"] != "nominal" else "")
                + ")"
            )
            verificacion = diagnostico.get("verificacion_velocidad")
            if verificacion:
                def _pico(pico):
                    return f"{pico['frecuencia']:.1f} Hz (amplitud {pico['amplitud']:.3g})" if pico else "ninguno"

                texto_velocidad += (
                    f"<br/>1x esperado: {verificacion['frecuencia_1x_esperada']} Hz (±{verificacion['tolerancia_pct']:g}%) · "
                    f"pico encontrado ahí: {_pico(verificacion['pico_1x'])} · "
                    f"pico dominante del espectro: {_pico(verificacion['pico_dominante'])}"
                )
            elementos.append(Paragraph(texto_velocidad, estilo_normal))

            if verificacion and verificacion["inconsistente"]:
                elementos.append(Paragraph(
                    "<b>Posible inconsistencia de velocidad:</b> hay un pico en "
                    f"{_pico(verificacion['pico_externo'])}, fuera de la ventana donde se busca el 1x"
                    + (
                        f", {verificacion['razon_pico_externo']:g} veces el pico encontrado dentro de ella"
                        if verificacion["razon_pico_externo"]
                        else " (dentro de la ventana no se encontró ningún pico)"
                    )
                    + ". La velocidad usada puede no ser la real: declárala al cargar la medición.",
                    estilo_normal,
                ))

        calidad_medicion = diagnostico.get("calidad_medicion")
        if calidad_medicion and calidad_medicion["estado"] != "valida":
            mensajes = calidad_medicion["criticas"] + calidad_medicion["advertencias"]
            elementos.append(Paragraph(
                f"<b>Calidad de medición (ISO 13373-1):</b> {calidad_medicion['estado'].replace('_', ' ')} — "
                + " ".join(mensajes),
                estilo_normal,
            ))

        elementos.append(Spacer(1, 0.2 * cm))

        if sensor.get("datos_fft"):
            imagen = graficar_espectro(sensor["datos_fft"], diagnostico["frecuencias_esperadas"])
            elementos.append(Image(imagen, width=17 * cm, height=17 * cm * 7 / 16))
            elementos.append(Spacer(1, 0.3 * cm))

        datos_grafico_rodamiento = graficos_rodamiento.get(sensor.get("sensor_id"))
        if datos_grafico_rodamiento is not None:
            imagen_envolvente = graficar_envolvente(datos_grafico_rodamiento)
            elementos.append(Image(imagen_envolvente, width=17 * cm, height=17 * cm * 6 / 16))
            elementos.append(Spacer(1, 0.2 * cm))

            imagen_senal = graficar_senal_envolvente(datos_grafico_rodamiento)
            elementos.append(Image(imagen_senal, width=17 * cm, height=17 * cm * 6 / 16))
            elementos.append(Spacer(1, 0.3 * cm))

        if diagnostico["hipotesis"]:
            filas = [["Hipótesis de falla", "Confianza", "Evidencia"]]
            for h in diagnostico["hipotesis"]:
                filas.append([
                    h["falla"].replace("_", " ").capitalize(),
                    f"{h['confianza'] * 100:.0f}%",
                    # Paragraph y no texto plano: la celda ajusta el texto largo en vez de salirse de la tabla.
                    Paragraph(", ".join(h["evidencias"]), estilo_celda),
                ])

            tabla = Table(filas, colWidths=[5 * cm, 2.5 * cm, 9.5 * cm])
            tabla.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0f1520")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTSIZE", (0, 0), (-1, -1), 8.5),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f1f5f9")]),
            ]))
            elementos.append(tabla)

            for h in diagnostico["hipotesis"]:
                if h["recomendacion"]:
                    elementos.append(Spacer(1, 0.15 * cm))
                    elementos.append(Paragraph(
                        f"<b>{h['falla'].replace('_', ' ').capitalize()}</b> — recomendaciones: "
                        + ", ".join(r.replace("_", " ") for r in h["recomendacion"]),
                        estilo_normal,
                    ))
        else:
            elementos.append(Paragraph(
                "No se encontraron hipótesis de falla con confianza suficiente.",
                estilo_normal,
            ))

        elementos.append(Spacer(1, 0.3 * cm))
        elementos.append(Paragraph("<b>Limitaciones de este diagnóstico:</b>", estilo_normal))
        elementos.append(ListFlowable(
            [ListItem(Paragraph(limitacion, estilo_normal)) for limitacion in diagnostico["limitaciones"]],
            bulletType="bullet",
        ))
        elementos.append(Spacer(1, 0.4 * cm))

    if reporte.get("resumen_ia"):
        elementos.append(PageBreak())
        elementos.extend(pagina_resumen_ia(reporte["resumen_ia"], equipo, reporte["fecha_generacion"], estilos))

    buffer_pdf = io.BytesIO()
    documento = SimpleDocTemplate(
        buffer_pdf, pagesize=A4,
        topMargin=1.5 * cm, bottomMargin=1.5 * cm,
        leftMargin=1.5 * cm, rightMargin=1.5 * cm,
    )
    documento.build(elementos)
    buffer_pdf.seek(0)
    return buffer_pdf.read()
