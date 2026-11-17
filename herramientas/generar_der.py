"""
Herramienta para generar el diagrama entidad-relacion (DER) de la base de datos de MotorGuardian.

Responsabilidad:
    Dibujar, en un PNG de alta resolucion y fondo claro (para el documento impreso), las 15 tablas de
    basedatos/modelos.py con sus columnas, claves y relaciones. Las columnas, tipos, claves primarias,
    foraneas y restricciones UNIQUE se leen de los propios modelos (no se escriben a mano), de modo que el
    diagrama no puede diferir del codigo; solo la posicion de cada caja y los puntos de anclaje de las
    lineas estan definidos aqui.

Salida:
    docs/der_basedatos.png
"""

import sys
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch

RUTA_PROYECTO = Path(__file__).parent.parent
sys.path.insert(0, str(RUTA_PROYECTO))

from basedatos.modelos import Base  # noqa: E402

RUTA_SALIDA = RUTA_PROYECTO / "docs" / "der_basedatos.png"

FONDO = "#ffffff"
TEXTO = "#0f172a"
TEXTO_TENUE = "#64748b"
LINEA = "#475569"
COLOR_PK = "#b45309"
COLOR_FK = "#0369a1"
COLOR_UQ = "#15803d"

ANCHO = 34.0
ALTO_ENCABEZADO = 3.6
ALTO_FILA = 2.3

# Grupo de cada tabla: color del encabezado.
GRUPOS = {
    "catalogos": ("#1d4ed8", "Catálogos"),
    "nucleo": ("#0f766e", "Equipos, sensores y mediciones"),
    "resultados": ("#b45309", "Resultados del análisis"),
    "avisos": ("#7e22ce", "Avisos"),
    "sistema": ("#475569", "Sistema (sin relaciones)"),
}
GRUPO_DE = {
    "planta": "catalogos", "tipo_equipo": "catalogos", "tipo_sensor": "catalogos",
    "equipo": "nucleo", "sensor": "nucleo", "rodamiento": "nucleo", "medicion": "nucleo",
    "linea_base": "resultados", "resultado_analisis": "resultados", "reporte": "resultados",
    "notificacion": "avisos", "destinatario_notificacion": "avisos",
    "usuario": "sistema", "modelo": "sistema", "plantilla_importacion": "sistema",
}

# Esquina inferior izquierda de cada caja.
POSICION = {
    "planta": (4, 120), "tipo_equipo": (4, 102),
    "equipo": (46, 104), "sensor": (88, 104), "tipo_sensor": (130, 112),
    "reporte": (4, 76), "rodamiento": (67, 66),
    "medicion": (130, 62), "linea_base": (130, 34), "resultado_analisis": (172, 70),
    "notificacion": (46, 24),
    "usuario": (4, 0), "modelo": (46, 0), "plantilla_importacion": (88, 0), "destinatario_notificacion": (130, 0),
}

# (hija, lado y fraccion en la hija, madre, lado y fraccion en la madre). Lado: L, R, T (arriba), B (abajo).
RELACIONES = [
    ("equipo", "L", 0.85, "planta", "R", 0.5),
    ("equipo", "L", 0.35, "tipo_equipo", "R", 0.5),
    ("sensor", "L", 0.55, "equipo", "R", 0.55),
    ("sensor", "R", 0.70, "tipo_sensor", "L", 0.5),
    ("rodamiento", "T", 0.15, "equipo", "B", 0.77),
    ("sensor", "B", 0.24, "rodamiento", "T", 0.85),
    ("medicion", "T", 0.12, "sensor", "R", 0.15),
    ("linea_base", "L", 0.60, "sensor", "B", 0.70),
    ("linea_base", "T", 0.50, "medicion", "B", 0.50),
    ("resultado_analisis", "L", 0.50, "medicion", "R", 0.55),
    ("reporte", "R", 0.50, "equipo", "B", 0.08),
    ("notificacion", "T", 0.18, "equipo", "B", 0.20),
    ("notificacion", "R", 0.40, "medicion", "B", 0.10),
]


def tipo_corto(tipo):
    nombre = type(tipo).__name__.upper()
    if nombre == "STRING":
        return f"str({tipo.length})" if tipo.length else "str"
    return {"INTEGER": "int", "FLOAT": "float", "TEXT": "text", "DATETIME": "datetime", "JSON": "json", "BOOLEAN": "bool"}.get(nombre, nombre.lower())


def columnas_de(tabla):
    """[(nombre, tipo, es_pk, es_fk, es_unico, obligatorio)] en el orden en que estan declaradas."""
    fks = {c.name for fk in tabla.foreign_key_constraints for c in fk.columns}
    unicos = {c.name for c in tabla.columns if c.unique}
    for restriccion in tabla.constraints:
        if restriccion.__class__.__name__ == "UniqueConstraint":
            unicos |= {c.name for c in restriccion.columns}
    return [
        (c.name, tipo_corto(c.type), c.primary_key, c.name in fks, c.name in unicos, not c.nullable and not c.primary_key)
        for c in tabla.columns
    ]


def alto_de(tabla):
    return ALTO_ENCABEZADO + ALTO_FILA * len(tabla.columns) + 0.8


def punto(nombre, lado, fraccion, tablas):
    x, y = POSICION[nombre]
    alto = alto_de(tablas[nombre])
    return {
        "L": (x, y + alto * fraccion), "R": (x + ANCHO, y + alto * fraccion),
        "T": (x + ANCHO * fraccion, y + alto), "B": (x + ANCHO * fraccion, y),
    }[lado]


def dibujar_tabla(ax, nombre, tabla):
    x, y = POSICION[nombre]
    alto = alto_de(tabla)
    color = GRUPOS[GRUPO_DE[nombre]][0]
    ax.add_patch(FancyBboxPatch((x, y), ANCHO, alto, boxstyle="round,pad=0,rounding_size=0.7", linewidth=1.4, edgecolor=color, facecolor="#ffffff", zorder=3))
    ax.add_patch(FancyBboxPatch((x, y + alto - ALTO_ENCABEZADO), ANCHO, ALTO_ENCABEZADO, boxstyle="round,pad=0,rounding_size=0.7", linewidth=0, facecolor=color, zorder=4))
    ax.add_patch(plt.Rectangle((x, y + alto - ALTO_ENCABEZADO), ANCHO, 1.2, linewidth=0, facecolor=color, zorder=4))
    ax.text(x + ANCHO / 2, y + alto - ALTO_ENCABEZADO / 2, nombre, ha="center", va="center", fontsize=10.2, fontweight="bold", color="#ffffff", zorder=5)
    for i, (col, tipo, pk, fk, unico, obligatorio) in enumerate(columnas_de(tabla)):
        yy = y + alto - ALTO_ENCABEZADO - ALTO_FILA * (i + 0.5) - 0.2
        marca, color_marca = ("PK", COLOR_PK) if pk else (("FK", COLOR_FK) if fk else (("UQ", COLOR_UQ) if unico else ("", TEXTO)))
        if marca:
            ax.text(x + 0.9, yy, marca, ha="left", va="center", fontsize=7.4, fontweight="bold", color=color_marca, zorder=5)
        ax.text(x + 4.2, yy, col + (" *" if obligatorio else ""), ha="left", va="center", fontsize=8.1, color=TEXTO, family="DejaVu Sans Mono", zorder=5)
        ax.text(x + ANCHO - 0.9, yy, tipo, ha="right", va="center", fontsize=7.6, color=TEXTO_TENUE, zorder=5)
        if unico and not pk and not fk:
            pass


def dibujar_relacion(ax, hija, lado_h, frac_h, madre, lado_m, frac_m, tablas):
    origen = punto(hija, lado_h, frac_h, tablas)
    destino = punto(madre, lado_m, frac_m, tablas)
    opcional = any(
        c.nullable for fk in tablas[hija].foreign_key_constraints if fk.referred_table.name == madre for c in fk.columns
    )
    ax.add_patch(
        FancyArrowPatch(
            origen, destino, arrowstyle="-", linewidth=1.5, color=LINEA, linestyle="--" if opcional else "-", zorder=2,
            shrinkA=0, shrinkB=0,
        )
    )
    for (px, py), texto in ((origen, "N"), (destino, "1")):
        ax.text(px, py, texto, ha="center", va="center", fontsize=8.2, fontweight="bold", color=LINEA, zorder=6, bbox=dict(boxstyle="round,pad=0.12", facecolor="#ffffff", edgecolor="none"))


def dibujar():
    tablas = {t.name: t for t in Base.metadata.sorted_tables}
    faltan = set(tablas) - set(POSICION)
    if faltan:
        raise SystemExit(f"Hay tablas sin posicion en el diagrama: {sorted(faltan)}")

    fig, ax = plt.subplots(figsize=(21, 14))
    fig.patch.set_facecolor(FONDO)
    ax.set_facecolor(FONDO)
    ax.set_xlim(0, 210)
    ax.set_ylim(-2, 140)
    ax.axis("off")

    ax.text(105, 138.2, "MotorGuardian — Diagrama entidad-relación de la base de datos", ha="center", va="center", fontsize=18, fontweight="bold", color=TEXTO)
    ax.text(105, 135.2, f"MySQL · {len(tablas)} tablas · {sum(len(t.foreign_key_constraints) for t in tablas.values())} relaciones", ha="center", va="center", fontsize=11, color=TEXTO_TENUE)

    for hija, lado_h, frac_h, madre, lado_m, frac_m in RELACIONES:
        dibujar_relacion(ax, hija, lado_h, frac_h, madre, lado_m, frac_m, tablas)
    for nombre, tabla in tablas.items():
        dibujar_tabla(ax, nombre, tabla)

    ax.text(4, 22.2, "Sin relaciones con otras tablas", ha="left", va="center", fontsize=9, color=TEXTO_TENUE, style="italic")
    ax.text(130, 22.2, "(destinatarios: lista de a quién avisar)", ha="left", va="center", fontsize=9, color=TEXTO_TENUE, style="italic")

    # Leyenda
    lx, ly = 172, 20
    ax.add_patch(FancyBboxPatch((lx, ly), 34, 44, boxstyle="round,pad=0,rounding_size=0.7", linewidth=1.0, edgecolor="#cbd5e1", facecolor="#f8fafc", zorder=1))
    ax.text(lx + 17, ly + 41.2, "Leyenda", ha="center", va="center", fontsize=10.5, fontweight="bold", color=TEXTO)
    lineas = [
        ("PK", COLOR_PK, "clave primaria"),
        ("FK", COLOR_FK, "clave foránea"),
        ("UQ", COLOR_UQ, "valor único"),
        ("*", TEXTO, "dato obligatorio (no nulo)"),
        ("1 — N", LINEA, "uno a muchos (N: tabla hija)"),
        ("- - -", LINEA, "relación opcional (FK nula)"),
    ]
    for i, (marca, color, texto) in enumerate(lineas):
        yy = ly + 36 - i * 3.6
        ax.text(lx + 2, yy, marca, ha="left", va="center", fontsize=8.6, fontweight="bold", color=color)
        ax.text(lx + 10.5, yy, texto, ha="left", va="center", fontsize=8.4, color=TEXTO)
    for i, (clave, (color, nombre)) in enumerate(GRUPOS.items()):
        yy = ly + 13.5 - i * 3.0
        ax.add_patch(plt.Rectangle((lx + 2, yy - 0.9), 3.4, 1.8, facecolor=color, linewidth=0))
        ax.text(lx + 7, yy, nombre, ha="left", va="center", fontsize=8.2, color=TEXTO)
    return fig


def main():
    fig = dibujar()
    RUTA_SALIDA.parent.mkdir(exist_ok=True)
    fig.savefig(RUTA_SALIDA, dpi=140, facecolor=FONDO, bbox_inches="tight", pad_inches=0.3)
    plt.close(fig)
    print(f"Guardado en {RUTA_SALIDA}")


if __name__ == "__main__":
    main()
