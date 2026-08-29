"""
Herramienta para generar el diagrama de arquitectura de MotorGuardian.

Responsabilidad:
    Dibujar, en un PNG de alta resolución, cómo interactúan el servidor
    backend (FastAPI) y el servidor frontend (React + Vite), y cómo se
    conectan hacia el equipo monitoreado (motor + sensores) y hacia AWS.

Salida:
    docs/arquitectura_servidores.png
"""

from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch


RUTA_PROYECTO = Path(__file__).parent.parent
RUTA_SALIDA = RUTA_PROYECTO / "docs" / "arquitectura_servidores.png"

COLOR_FONDO = "#0b1220"
COLOR_TEXTO_CLARO = "#f8fafc"
COLOR_TEXTO_TENUE = "#94a3b8"

COLOR_EQUIPO = "#334155"
COLOR_DATOS = "#475569"
COLOR_BACKEND = "#0d9488"
COLOR_FRONTEND = "#0284c7"
COLOR_HERRAMIENTA = "#57534e"
COLOR_AWS = "#d97706"
COLOR_NAVEGADOR = "#7c3aed"


def dibujar_bloque(ax, cx, cy, ancho, alto, lineas, color_fondo,
                    color_texto=COLOR_TEXTO_CLARO, tam_fuente_titulo=13.5,
                    tam_fuente_resto=10.5):

    caja = FancyBboxPatch(
        (cx - ancho / 2, cy - alto / 2),
        ancho,
        alto,
        boxstyle="round,pad=0.08,rounding_size=0.14",
        linewidth=1.6,
        edgecolor="#e2e8f0",
        facecolor=color_fondo,
        zorder=3,
    )
    ax.add_patch(caja)

    cantidad_lineas = len(lineas)
    espacio = alto / (cantidad_lineas + 1)

    for indice, linea in enumerate(lineas):
        y = cy + alto / 2 - espacio * (indice + 1)
        es_titulo = indice == 0
        ax.text(
            cx,
            y,
            linea,
            ha="center",
            va="center",
            color=color_texto,
            fontsize=tam_fuente_titulo if es_titulo else tam_fuente_resto,
            fontweight="bold" if es_titulo else "normal",
            zorder=4,
        )


def dibujar_flecha(ax, inicio, fin, etiqueta, color, estilo="->",
                    curvatura=0.0, desplazamiento_etiqueta=(0, 0.0),
                    tam_fuente=9.5, color_etiqueta=COLOR_TEXTO_CLARO):

    ax.annotate(
        "",
        xy=fin,
        xytext=inicio,
        arrowprops=dict(
            arrowstyle=estilo,
            color=color,
            linewidth=2.2,
            connectionstyle=f"arc3,rad={curvatura}",
            shrinkA=8,
            shrinkB=8,
        ),
        zorder=2,
    )

    if etiqueta:
        xm = (inicio[0] + fin[0]) / 2 + desplazamiento_etiqueta[0]
        ym = (inicio[1] + fin[1]) / 2 + desplazamiento_etiqueta[1]

        ax.text(
            xm,
            ym,
            etiqueta,
            ha="center",
            va="center",
            color=color_etiqueta,
            fontsize=tam_fuente,
            fontweight="bold",
            zorder=5,
            bbox=dict(
                boxstyle="round,pad=0.25",
                facecolor="#0b1220",
                edgecolor=color,
                linewidth=1.0,
                alpha=0.92,
            ),
        )


def generar_diagrama():

    fig, ax = plt.subplots(figsize=(18, 10.3), dpi=300)
    fig.patch.set_facecolor(COLOR_FONDO)
    ax.set_facecolor(COLOR_FONDO)

    ax.set_xlim(0, 18.4)
    ax.set_ylim(0, 10.3)
    ax.axis("off")

    ax.text(
        9.2, 10.0,
        "MotorGuardian — Arquitectura de servidores y flujo de datos",
        ha="center", va="center",
        color=COLOR_TEXTO_CLARO, fontsize=19, fontweight="bold",
    )
    ax.text(
        9.2, 9.6,
        "Proyecto fusionado en mg/  ·  Python + FastAPI + React/Vite + AWS S3",
        ha="center", va="center",
        color=COLOR_TEXTO_TENUE, fontsize=11.5,
    )

    # --- Posiciones de los bloques ---
    p_motor = (2.0, 7.9)
    p_sensores = (2.0, 5.8)
    p_csv = (2.0, 3.5)

    p_backend = (8.0, 3.5)
    p_frontend = (15.0, 3.5)

    p_herramienta = (8.0, 6.2)
    p_aws = (8.0, 8.4)

    p_navegador = (15.0, 6.2)

    # --- Bloques: equipo monitoreado ---
    dibujar_bloque(
        ax, *p_motor, 3.3, 1.25,
        ["MOTOR ELÉCTRICO", "MONOFÁSICO", "(equipo monitoreado)"],
        COLOR_EQUIPO, tam_fuente_resto=9.5,
    )

    dibujar_bloque(
        ax, *p_sensores, 3.3, 1.55,
        ["SENSORES", "Acelerómetro triaxial (X, Y, Z)", "Sensor de temperatura"],
        COLOR_EQUIPO, tam_fuente_resto=9.8,
    )

    dibujar_bloque(
        ax, *p_csv, 3.3, 1.35,
        ["ARCHIVO DE DATOS", "datos_vibracion_motor.csv", "carpeta datos/"],
        COLOR_DATOS, tam_fuente_resto=9.8,
    )

    # --- Bloques: servidores (los dos extremos de la API) ---
    dibujar_bloque(
        ax, *p_backend, 4.2, 1.95,
        ["SERVIDOR BACKEND", "FastAPI (Python)", "PORT: 8000", "127.0.0.1:8000"],
        COLOR_BACKEND, tam_fuente_titulo=14.5, tam_fuente_resto=10.5,
    )

    dibujar_bloque(
        ax, *p_frontend, 4.0, 1.95,
        ["SERVIDOR FRONTEND", "React + Vite", "PORT: 5173", "localhost:5173"],
        COLOR_FRONTEND, tam_fuente_titulo=14.5, tam_fuente_resto=10.5,
    )

    # --- Bloques: AWS y herramienta manual ---
    dibujar_bloque(
        ax, *p_herramienta, 4.4, 1.45,
        ["HERRAMIENTA MANUAL", "herramientas/subir_archivo_s3.py",
         "acceso AWS comentado"],
        COLOR_HERRAMIENTA, tam_fuente_resto=9.6,
    )

    dibujar_bloque(
        ax, *p_aws, 4.4, 1.55,
        ["AWS S3", "bucket: motorguardian-lab-vramirez",
         "región: us-east-1"],
        COLOR_AWS, tam_fuente_resto=10,
    )

    # --- Bloque: navegador / dashboard ---
    dibujar_bloque(
        ax, *p_navegador, 4.4, 1.45,
        ["NAVEGADOR", "Dashboard MotorGuardian", "localhost:5173"],
        COLOR_NAVEGADOR, tam_fuente_resto=9.8,
    )

    # --- Flechas: equipo -> datos ---
    dibujar_flecha(
        ax, (p_motor[0], p_motor[1] - 0.63), (p_sensores[0], p_sensores[1] + 0.78),
        "monitorea", "#94a3b8", desplazamiento_etiqueta=(0.85, 0),
    )

    dibujar_flecha(
        ax, (p_sensores[0], p_sensores[1] - 0.78), (p_csv[0], p_csv[1] + 0.68),
        "genera muestras\n(CSV sintético)", "#94a3b8", desplazamiento_etiqueta=(1.05, 0),
    )

    # --- Flecha: CSV -> backend ---
    dibujar_flecha(
        ax, (p_csv[0] + 1.65, p_csv[1]), (p_backend[0] - 2.1, p_backend[1]),
        "pandas.read_csv()", "#38bdf8",
    )

    # --- Flecha principal entre los dos servidores (los dos extremos de la API) ---
    borde_backend = p_backend[0] + 2.1
    borde_frontend = p_frontend[0] - 2.0

    dibujar_flecha(
        ax, (borde_backend, p_backend[1] + 0.22), (borde_frontend, p_frontend[1] + 0.22),
        "", COLOR_TEXTO_CLARO,
    )
    dibujar_flecha(
        ax, (borde_frontend, p_frontend[1] - 0.22), (borde_backend, p_backend[1] - 0.22),
        "", COLOR_TEXTO_CLARO,
    )
    ax.text(
        (borde_backend + borde_frontend) / 2, p_backend[1] + 0.65,
        "FastAPI · API REST\n(JSON)",
        ha="center", va="center", color=COLOR_TEXTO_CLARO,
        fontsize=12, fontweight="bold", zorder=5,
        bbox=dict(boxstyle="round,pad=0.3", facecolor="#0b1220",
                  edgecolor=COLOR_TEXTO_CLARO, linewidth=1.1, alpha=0.94),
    )
    ax.text(
        (borde_backend + borde_frontend) / 2, p_backend[1] - 0.75,
        "GET /api/datos\n/api/fft\n/api/estadisticos",
        ha="center", va="center", color=COLOR_TEXTO_TENUE,
        fontsize=8.8, zorder=5,
    )
    ax.text(
        (borde_backend + borde_frontend) / 2, p_backend[1] - 1.35,
        "CORS: 127.0.0.1:8000 ⇄ localhost:5173",
        ha="center", va="center", color=COLOR_TEXTO_TENUE,
        fontsize=8.2, zorder=5,
    )

    # --- Flecha: CSV -> herramienta manual -> AWS ---
    dibujar_flecha(
        ax, (p_csv[0] + 0.3, p_csv[1] + 0.68), (p_herramienta[0] - 1.9, p_herramienta[1] - 0.55),
        "lectura manual", "#a8a29e", curvatura=0.15, desplazamiento_etiqueta=(-0.55, 0.35),
    )

    dibujar_flecha(
        ax, (p_herramienta[0], p_herramienta[1] + 0.73), (p_aws[0], p_aws[1] - 0.78),
        "boto3 · upload_file()\n(manual, comentado)", COLOR_AWS,
    )

    # --- Flecha: frontend -> navegador ---
    dibujar_flecha(
        ax, (p_frontend[0], p_frontend[1] + 0.98), (p_navegador[0], p_navegador[1] - 0.73),
        "renderiza\n(Recharts)", COLOR_FRONTEND,
    )

    nota = (
        "El motor y los sensores representan la fuente de datos (hoy simulada mediante un CSV sintético). "
        "La subida a AWS S3 es un proceso manual e independiente del servidor FastAPI."
    )
    ax.text(
        8, 0.35, nota,
        ha="center", va="center", color=COLOR_TEXTO_TENUE, fontsize=9.5, style="italic",
    )

    RUTA_SALIDA.parent.mkdir(parents=True, exist_ok=True)

    fig.savefig(
        RUTA_SALIDA,
        dpi=300,
        facecolor=COLOR_FONDO,
        bbox_inches="tight",
    )

    print(f"Diagrama generado en: {RUTA_SALIDA}")


if __name__ == "__main__":
    generar_diagrama()
