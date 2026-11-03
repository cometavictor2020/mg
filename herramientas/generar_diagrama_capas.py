"""
Herramienta para generar el diagrama de capas de MotorGuardian (sección 4.1 de la memoria).

Responsabilidad:
    Dibujar, en un PNG de alta resolución y fondo claro (para el documento impreso), las capas del sistema
    (interfaz, servicios, procesamiento y datos), con la base de conocimiento y los avisos como servicios
    laterales, y las tres razones por las que se organizó así.

Salida:
    docs/arquitectura_capas.png
"""

from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.patches import Circle, FancyArrowPatch, FancyBboxPatch

RUTA_PROYECTO = Path(__file__).parent.parent
RUTA_SALIDA = RUTA_PROYECTO / "docs" / "arquitectura_capas.png"

FONDO = "#ffffff"
TEXTO = "#0f172a"
TEXTO_TENUE = "#475569"

CAPAS = {
    "interfaz": {"fondo": "#e0f2fe", "borde": "#0284c7"},
    "servicios": {"fondo": "#ccfbf1", "borde": "#0d9488"},
    "procesamiento": {"fondo": "#fef3c7", "borde": "#d97706"},
    "datos": {"fondo": "#e2e8f0", "borde": "#475569"},
    "lateral": {"fondo": "#ede9fe", "borde": "#7c3aed"},
}
COLOR_RAZON = "#be123c"


def caja(ax, x, y, ancho, alto, fondo, borde, radio=0.9, grosor=1.6, estilo="-", zorder=2):
    ax.add_patch(
        FancyBboxPatch(
            (x, y), ancho, alto,
            boxstyle=f"round,pad=0,rounding_size={radio}",
            linewidth=grosor, edgecolor=borde, facecolor=fondo, linestyle=estilo, zorder=zorder,
        )
    )


def chip(ax, x, y, ancho, alto, texto, borde, tam=9.2, estilo="-"):
    caja(ax, x, y, ancho, alto, "#ffffff", borde, radio=0.5, grosor=1.1, estilo=estilo, zorder=3)
    ax.text(x + ancho / 2, y + alto / 2, texto, ha="center", va="center", fontsize=tam, color=TEXTO, zorder=4, linespacing=1.15)


def fila_de_chips(ax, x0, y, ancho_total, alto, textos, borde, separacion=0.8, tam=9.2, discontinuo_el_ultimo=False):
    ancho = (ancho_total - separacion * (len(textos) - 1)) / len(textos)
    for i, texto in enumerate(textos):
        estilo = "--" if discontinuo_el_ultimo and i == len(textos) - 1 else "-"
        chip(ax, x0 + i * (ancho + separacion), y, ancho, alto, texto, borde, tam, estilo)


def titulo_capa(ax, x, y, numero, titulo, subtitulo, color):
    ax.text(x, y, f"{numero}  {titulo}", ha="left", va="center", fontsize=12.5, fontweight="bold", color=color, zorder=4)
    ax.text(x, y - 1.55, subtitulo, ha="left", va="center", fontsize=9.2, color=TEXTO_TENUE, style="italic", zorder=4)


def flecha(ax, x1, y1, x2, y2, doble=True, estilo="-"):
    ax.add_patch(
        FancyArrowPatch(
            (x1, y1), (x2, y2), arrowstyle="<|-|>" if doble else "-|>", mutation_scale=14,
            linewidth=1.6, color=TEXTO_TENUE, linestyle=estilo, zorder=5, shrinkA=0, shrinkB=0,
        )
    )


def etiqueta(ax, x, y, texto, ha="left"):
    ax.text(x, y, texto, ha=ha, va="center", fontsize=8.8, color=TEXTO_TENUE, zorder=5)


def razon(ax, x, y, numero):
    ax.add_patch(Circle((x, y), 1.25, facecolor=COLOR_RAZON, edgecolor="#ffffff", linewidth=1.4, zorder=8))
    ax.text(x, y - 0.05, str(numero), ha="center", va="center", fontsize=10.5, fontweight="bold", color="#ffffff", zorder=9)


def dibujar():
    fig, ax = plt.subplots(figsize=(15.5, 12.4))
    fig.patch.set_facecolor(FONDO)
    ax.set_facecolor(FONDO)
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 80)
    ax.axis("off")

    ax.text(50, 78.3, "MotorGuardian: arquitectura por capas", ha="center", va="center", fontsize=17, fontweight="bold", color=TEXTO)

    X, ANCHO = 3, 70  # columna principal
    XL, ANCHO_L = 77, 20  # columna lateral

    # ---- Capa 1: interfaz --------------------------------------------------------------------------------------
    c = CAPAS["interfaz"]
    caja(ax, X, 62.5, ANCHO, 13, c["fondo"], c["borde"])
    titulo_capa(ax, X + 1.5, 73.6, "1", "Interfaz web", "Lo que ve y usa el responsable de mantenimiento (React + Vite)", c["borde"])
    fila_de_chips(
        ax, X + 1.5, 64.2, ANCHO - 3, 5.2,
        ["Acceso", "Resumen\ngeneral", "Analizador de\nvibraciones", "Reportes", "Laboratorio", "Configuración", "Otro cliente\n(a futuro)"],
        c["borde"], tam=8.4, discontinuo_el_ultimo=True,
    )

    # ---- Capa 2: servicios -------------------------------------------------------------------------------------
    c = CAPAS["servicios"]
    caja(ax, X, 43.5, ANCHO, 13, c["fondo"], c["borde"])
    titulo_capa(ax, X + 1.5, 54.6, "2", "Servicios (API)", "Recibe las solicitudes, comprueba el acceso y responde; no calcula (FastAPI)", c["borde"])
    fila_de_chips(ax, X + 1.5, 45.2, ANCHO - 3, 5.2, ["Acceso y\nusuarios", "Equipos y\nsensores", "Carga de\nmediciones", "Diagnóstico\ny alertas", "Reportes\nen PDF", "Líneas base"], c["borde"])

    # ---- Capa 3: procesamiento y diagnóstico -------------------------------------------------------------------
    c = CAPAS["procesamiento"]
    caja(ax, X, 21.5, ANCHO, 18.5, c["fondo"], c["borde"])
    titulo_capa(ax, X + 1.5, 37.6, "3", "Procesamiento y diagnóstico", "Cálculo sobre la señal (Python); no conoce la interfaz ni el protocolo HTTP", c["borde"])
    ancho_chip = (ANCHO - 3 - 0.8 * 3) / 4
    modulos = [
        ["Lectura de\nseñales", "Espectro\n(FFT)", "Espectro de\nenvolvente", "Velocidad\nde giro"],
        ["Diagnóstico\ndel rotor", "Diagnóstico de\nrodamientos", "Severidad\nISO 20816-3", "Calidad de medición\nISO 13373-1"],
        ["Línea base y\ncambio", "Optimización\nPSO (opcional)", "Informe\nen PDF", "Importación de\narchivos"],
    ]
    for fila, textos in enumerate(modulos):
        for i, texto in enumerate(textos):
            chip(ax, X + 1.5 + i * (ancho_chip + 0.8), 31.2 - fila * 3.9, ancho_chip, 3.2, texto, c["borde"], tam=8.4)

    # ---- Capa 4: datos -----------------------------------------------------------------------------------------
    c = CAPAS["datos"]
    caja(ax, X, 3.5, ANCHO, 14, c["fondo"], c["borde"])
    titulo_capa(ax, X + 1.5, 15.1, "4", "Datos", "Qué se guarda y dónde", c["borde"])
    chip(ax, X + 1.5, 5.0, 30.5, 7.4, "Base de datos MySQL\nEquipos, sensores, rodamientos, mediciones,\nreportes, líneas base, avisos y usuarios", c["borde"], tam=8.6)
    chip(ax, X + 33.0, 5.0, 17.0, 7.4, "Archivos de señales\n(disco local)\nLas muestras no van\na la base de datos", c["borde"], tam=8.4)
    chip(ax, X + 51.0, 5.0, 16.5, 7.4, "Respaldo en la nube\n(AWS S3)\nSubida manual", c["borde"], tam=8.6, estilo="--")

    # ---- Columna lateral: avisos (junto a los servicios) --------------------------------------------------------
    c = CAPAS["lateral"]
    caja(ax, XL, 43.5, ANCHO_L, 13, c["fondo"], c["borde"])
    ax.text(XL + 1.2, 54.6, "Avisos", ha="left", va="center", fontsize=11.3, fontweight="bold", color=c["borde"], zorder=4)
    ax.text(XL + 1.2, 53.0, "Al cargar una medición", ha="left", va="center", fontsize=8.6, color=TEXTO_TENUE, style="italic", zorder=4)
    chip(ax, XL + 1.2, 49.0, ANCHO_L - 2.4, 2.8, "Correo electrónico", c["borde"], tam=8.8)
    chip(ax, XL + 1.2, 45.2, ANCHO_L - 2.4, 2.8, "Telegram", c["borde"], tam=8.8)

    # ---- Columna lateral: base de conocimiento (junto al procesamiento) -----------------------------------------
    caja(ax, XL, 19.5, ANCHO_L, 22.0, c["fondo"], c["borde"])
    ax.text(XL + 1.2, 39.6, "Base de conocimiento", ha="left", va="center", fontsize=11.3, fontweight="bold", color=c["borde"], zorder=4)
    ax.text(XL + 1.2, 37.0, "Archivos de texto (YAML)\ncurados por el desarrollador", ha="left", va="center", fontsize=8.6, color=TEXTO_TENUE, style="italic", zorder=4, linespacing=1.2)
    for i, texto in enumerate(["Normativa y reglas\nde diagnóstico", "Criterios del\nproyecto", "Catálogo de\ntipos de sensor"]):
        chip(ax, XL + 1.2, 31.6 - i * 4.6, ANCHO_L - 2.4, 3.8, texto, c["borde"], tam=8.6)
    ax.text(XL + 1.2, 20.9, "Las reglas no están fijas\nen el código", ha="left", va="center", fontsize=8.4, color=TEXTO_TENUE, zorder=4, linespacing=1.2)

    # ---- Leyenda de trazos (columna lateral, a la altura de la interfaz) ----------------------------------------
    ax.text(XL + 0.5, 72.0, "Trazo continuo:\nparte del sistema.", ha="left", va="center", fontsize=8.6, color=TEXTO_TENUE, zorder=4, linespacing=1.25)
    ax.text(XL + 0.5, 67.0, "Trazo discontinuo:\nfunción manual o\nposible a futuro.", ha="left", va="center", fontsize=8.6, color=TEXTO_TENUE, zorder=4, linespacing=1.25)

    # ---- Flechas entre capas -----------------------------------------------------------------------------------
    flecha(ax, X + 25, 62.5, X + 25, 56.5)
    etiqueta(ax, X + 26.2, 59.5, "solicitudes y respuestas (JSON sobre HTTP): la misma API sirve a cualquier cliente")
    flecha(ax, X + 25, 43.5, X + 25, 40.0)
    etiqueta(ax, X + 26.2, 41.8, "llamadas a funciones de cálculo")
    flecha(ax, X + 58, 21.5, X + 58, 17.5)
    etiqueta(ax, X + 59.2, 19.5, "lectura y escritura")
    flecha(ax, X + ANCHO, 31.0, XL, 31.0, doble=False)
    flecha(ax, X + ANCHO, 50.0, XL, 50.0, doble=False, estilo="--")

    # ---- Nota sobre los catálogos abiertos ---------------------------------------------------------------------
    ax.text(X + 4.2, 19.0, "Los tipos de equipo y de sensor son tablas abiertas: agregar uno nuevo es agregar una fila", ha="left", va="center", fontsize=8.8, color=TEXTO_TENUE, style="italic", zorder=5)

    # ---- Marcas de las tres razones -----------------------------------------------------------------------------
    razon(ax, X + 21.5, 59.5, 1)
    razon(ax, X + ANCHO - 2, 40.0, 2)
    razon(ax, X + 2.0, 19.0, 3)

    # ---- Leyenda de las razones --------------------------------------------------------------------------------
    ax.add_patch(FancyBboxPatch((X, 0.3), 94, 2.5, boxstyle="round,pad=0,rounding_size=0.5", linewidth=0, facecolor="#fff1f2", zorder=1))
    razones = [
        ("1", "Cambiar la interfaz sin tocar el cálculo"),
        ("2", "Probar cada módulo por separado"),
        ("3", "Incorporar otros equipos y sensores sin rediseñar"),
    ]
    xs = [X + 1.5, X + 34, X + 60]
    for (numero, texto), x in zip(razones, xs):
        razon(ax, x, 1.55, numero)
        ax.text(x + 2.0, 1.55, texto, ha="left", va="center", fontsize=9.6, color=TEXTO, zorder=5)

    return fig


def main():
    fig = dibujar()
    RUTA_SALIDA.parent.mkdir(exist_ok=True)
    fig.savefig(RUTA_SALIDA, dpi=200, facecolor=FONDO, bbox_inches="tight", pad_inches=0.3)
    plt.close(fig)
    print(f"Guardado en {RUTA_SALIDA}")


if __name__ == "__main__":
    main()
