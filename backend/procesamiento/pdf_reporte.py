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
    ListFlowable,
    ListItem,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

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
    """Devuelve un PNG (bytes) del espectro FFT con 1x/2x/3x marcados."""
    frecuencias = [d["frecuencia"] for d in datos_fft]

    figura, eje_grafico = plt.subplots(figsize=(16, 7))

    for eje in ("x", "y", "z"):
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
    """Señal cruda en el tiempo con su curva de envolvente (Hilbert) superpuesta."""
    tiempo = datos_grafico["tiempo"]
    señal = datos_grafico["señal"]
    envolvente = datos_grafico["envolvente_tiempo"]

    figura, eje_grafico = plt.subplots(figsize=(16, 6))
    eje_grafico.plot(tiempo, señal, color="#cbd5e1", linewidth=0.6, label="Señal cruda")
    eje_grafico.plot(tiempo, envolvente, color="#ef4444", linewidth=1.4, label="Envolvente (Hilbert)")

    eje_grafico.set_xlabel("Tiempo [s]")
    eje_grafico.set_ylabel("Amplitud")
    eje_grafico.set_title(f"Señal cruda y su envolvente — eje {datos_grafico['eje'].upper()}", fontsize=10)
    eje_grafico.legend(loc="upper right")
    eje_grafico.grid(alpha=0.3)

    buffer = io.BytesIO()
    figura.savefig(buffer, format="png", dpi=130, bbox_inches="tight")
    plt.close(figura)
    buffer.seek(0)
    return buffer


def generar_pdf_reporte(reporte, graficos_rodamiento=None):
    """
    reporte: {
        "equipo": {"nombre", "tipo", "planta", "rpm_nominal"},
        "fecha_generacion": str,
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
                    ", ".join(h["evidencias"]),
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

    buffer_pdf = io.BytesIO()
    documento = SimpleDocTemplate(
        buffer_pdf, pagesize=A4,
        topMargin=1.5 * cm, bottomMargin=1.5 * cm,
        leftMargin=1.5 * cm, rightMargin=1.5 * cm,
    )
    documento.build(elementos)
    buffer_pdf.seek(0)
    return buffer_pdf.read()
