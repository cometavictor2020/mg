"""
Herramienta para generar el diagrama de bloques de la arquitectura actual de MotorGuardian.

Responsabilidad:
    Dibujar, en un PNG de alta resolucion y fondo oscuro, los bloques del sistema (navegador, frontend, backend,
    motor de diagnostico, importador, avisos, base de datos, archivos, conocimiento y respaldo) y como se
    conectan. Complementa a generar_diagrama_capas.py (vista por capas, fondo claro, para la memoria).

Salida:
    docs/arquitectura_bloques.png
"""

from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch

RUTA_PROYECTO = Path(__file__).parent.parent
RUTA_SALIDA = RUTA_PROYECTO / "docs" / "arquitectura_bloques.png"

FONDO = "#0b1220"
TEXTO = "#f8fafc"
TEXTO_TENUE = "#94a3b8"
BORDE = "#e2e8f0"

NAVEGADOR = "#7c3aed"
FRONTEND = "#0284c7"
BACKEND = "#0d9488"
MOTOR = "#0f766e"
IMPORTADOR = "#0e7490"
AVISOS = "#a21caf"
CONOCIMIENTO = "#b45309"
BASE_DATOS = "#475569"
ARCHIVOS = "#334155"
REPORTES = "#57534e"
RESPALDO = "#92400e"
EXTERNOS = "#1e293b"


def bloque(ax, x, y, ancho, alto, titulo, lineas, color, estilo="-", tam_titulo=12.5, tam_lineas=9.6):
    ax.add_patch(
        FancyBboxPatch(
            (x, y), ancho, alto, boxstyle="round,pad=0,rounding_size=1.0",
            linewidth=1.8, edgecolor=BORDE, facecolor=color, linestyle=estilo, zorder=3,
        )
    )
    ax.text(x + ancho / 2, y + alto - 2.6, titulo, ha="center", va="center", fontsize=tam_titulo, fontweight="bold", color=TEXTO, zorder=4)
    if lineas:
        paso = (alto - 5.4) / len(lineas)
        for i, linea in enumerate(lineas):
            ax.text(x + ancho / 2, y + alto - 5.4 - paso * (i + 0.5), linea, ha="center", va="center", fontsize=tam_lineas, color=TEXTO, zorder=4)


def chip(ax, x, y, ancho, alto, texto, color, tam=8.6):
    ax.add_patch(
        FancyBboxPatch(
            (x, y), ancho, alto, boxstyle="round,pad=0,rounding_size=0.7",
            linewidth=1.2, edgecolor=BORDE, facecolor=color, linestyle="--", zorder=4,
        )
    )
    ax.text(x + ancho / 2, y + alto / 2, texto, ha="center", va="center", fontsize=tam, color=TEXTO, zorder=5, linespacing=1.15)


def flecha(ax, origen, destino, color, texto=None, posicion_texto=None, doble=False, estilo="-", curva=0.0):
    ax.add_patch(
        FancyArrowPatch(
            origen, destino, arrowstyle="<|-|>" if doble else "-|>", mutation_scale=15, linewidth=2.0, color=color,
            linestyle=estilo, connectionstyle=f"arc3,rad={curva}", zorder=5, shrinkA=0, shrinkB=0,
        )
    )
    if texto:
        x, y = posicion_texto or ((origen[0] + destino[0]) / 2, (origen[1] + destino[1]) / 2)
        ax.text(
            x, y, texto, ha="center", va="center", fontsize=8.4, fontweight="bold", color=TEXTO, zorder=7,
            bbox=dict(boxstyle="round,pad=0.25", facecolor=FONDO, edgecolor=color, linewidth=1.2),
        )


def dibujar():
    fig, ax = plt.subplots(figsize=(17, 11.4))
    fig.patch.set_facecolor(FONDO)
    ax.set_facecolor(FONDO)
    ax.set_xlim(0, 150)
    ax.set_ylim(0, 100)
    ax.axis("off")

    ax.text(75, 97.5, "MotorGuardian — Arquitectura actual", ha="center", va="center", fontsize=19, fontweight="bold", color=TEXTO)
    ax.text(
        75, 93.8, "Python + FastAPI + MySQL + React/Vite  ·  reglas de diagnóstico curadas (YAML)  ·  severidad ISO 20816-3 y calidad de medición ISO 13373-1",
        ha="center", va="center", fontsize=10.5, color=TEXTO_TENUE,
    )

    # ---- Columna A: usuario, interfaz, avisos y archivos externos ----------------------------------------------
    bloque(ax, 3, 78, 28, 12, "NAVEGADOR", ["Acceso · Resumen general", "Analizador de vibraciones", "Reportes · Laboratorio · Configuración"], NAVEGADOR, tam_lineas=8.8)
    bloque(ax, 3, 56, 28, 15, "FRONTEND — React + Vite", ["Gráficos de tiempo, FFT y envolvente", "Carga de datos con mapeo", "de columnas"], FRONTEND, tam_titulo=11.0, tam_lineas=9.0)
    bloque(ax, 3, 33, 28, 13, "AVISOS", ["Correo y Telegram", "al cargar una medición"], AVISOS)
    bloque(ax, 3, 4, 28, 20, "ARCHIVOS EXTERNOS", ["CSV y .mat de bancos de ensayo", "(CWRU, MAFAULDA, Ottawa…)", "o señales simuladas"], EXTERNOS, estilo="--", tam_lineas=9.2)

    # ---- Columna B: backend, motor e importador ------------------------------------------------------------------
    bloque(ax, 41, 70, 52, 20, "BACKEND — FastAPI", ["15 routers, todos con JWT (solo el acceso es público)"], BACKEND)
    chip(ax, 44, 71.0, 46, 4.4, "módulo opcional (PSO): pso_envolvente.py\nlo usan Laboratorio y el Analizador", "#115e59")
    bloque(
        ax, 41, 40, 52, 23, "MOTOR DE DIAGNÓSTICO Y CÁLCULO",
        [
            "diagnostico.py · diagnostico_rodamientos.py",
            "frecuencia.py (FFT) · envolvente.py (Hilbert) · estadisticos.py",
            "velocidad_peine.py · linea_base.py · cambio_linea_base.py",
            "severidad_iso.py · calidad_medicion.py · pdf_reporte.py",
        ],
        MOTOR,
    )
    bloque(ax, 41, 12, 52, 19, "IMPORTADOR DE ARCHIVOS", ["importador.py · importador_mat.py · lectura_mat.py", "valida y adapta el formato; una persona", "confirma la correspondencia de columnas"], IMPORTADOR, tam_lineas=9.2)

    # ---- Columna C: conocimiento, base de datos, archivos, reportes y respaldo ----------------------------------
    bloque(ax, 103, 74, 44, 16, "MYSQL — motorguardian", ["15 tablas: Equipo · Sensor · Rodamiento", "Medición · Línea base · Reporte", "Notificación · Usuario · catálogos"], BASE_DATOS, tam_lineas=9.2)
    bloque(ax, 103, 53, 44, 15, "CONOCIMIENTO (YAML)", ["normativa_motorguardian.yaml", "criterios_proyecto.yaml"], CONOCIMIENTO)
    bloque(ax, 103, 35, 44, 12, "reportes/", ["PDF con diagnóstico, evidencia", "y recomendaciones"], REPORTES, tam_lineas=9.2)
    bloque(ax, 103, 15, 44, 14, "datos/  —  señales", ["un CSV por medición", "(MySQL guarda solo la ruta)"], ARCHIVOS)
    bloque(ax, 103, 3, 44, 8, "AWS S3 — respaldo", [], RESPALDO, estilo="--", tam_titulo=11)
    ax.text(125, 5.0, "subida manual", ha="center", va="center", fontsize=8.8, color=TEXTO, zorder=4)

    # ---- Flechas --------------------------------------------------------------------------------------------------
    flecha(ax, (17, 78), (17, 71), NAVEGADOR, "renderiza", (17, 74.6))
    flecha(ax, (31, 67), (41, 80), FRONTEND, "fetch + JWT", (36, 76.5), doble=True, curva=-0.15)
    flecha(ax, (67, 70), (67, 63), BACKEND, "invoca cálculo", (67, 66.5))
    flecha(ax, (41, 73.5), (31, 43), AVISOS, "avisa", (37.5, 56), estilo="--")
    flecha(ax, (93, 82), (103, 82), BASE_DATOS, "SQLAlchemy", (98, 84.8), doble=True)
    flecha(ax, (93, 58), (103, 58), CONOCIMIENTO, "lee reglas", (98, 60.8))
    flecha(ax, (93, 46), (103, 42), REPORTES, "genera PDF", (98, 47.6))
    flecha(ax, (103, 26), (93, 41.5), TEXTO_TENUE, "lee la señal", (100.6, 34.4))
    flecha(ax, (93, 21), (103, 21), ARCHIVOS, "guarda", (98, 23.6))
    flecha(ax, (125, 15), (125, 11), RESPALDO, None, estilo="--")
    flecha(ax, (31, 18), (41, 20), IMPORTADOR, "cargar", (36, 21.6))
    flecha(ax, (31, 20), (41, 45), EXTERNOS, "Laboratorio:\nsin guardar", (35.6, 31.8), estilo="--")

    ax.text(
        75, 0.8,
        "El motor de diagnóstico lo usan los reportes, el Analizador y las alertas (datos guardados). Laboratorio solo usa su parte de rodamientos, con archivos que no se guardan. El PSO es un módulo aparte y opcional.",
        ha="center", va="center", fontsize=9.0, color=TEXTO_TENUE, style="italic",
    )
    return fig


def main():
    fig = dibujar()
    RUTA_SALIDA.parent.mkdir(exist_ok=True)
    fig.savefig(RUTA_SALIDA, dpi=130, facecolor=FONDO, bbox_inches="tight", pad_inches=0.3)
    plt.close(fig)
    print(f"Guardado en {RUTA_SALIDA}")


if __name__ == "__main__":
    main()
