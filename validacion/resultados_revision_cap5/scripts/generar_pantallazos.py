"""
Genera imagenes ("pantallazos") con fragmentos de la salida REAL de los scripts de validacion, para respaldar
las cifras del capitulo 5. No recalcula nada: lee los archivos de resultados guardados en esta carpeta
(o los anteriores, cuando se indica) y los dibuja tal cual, con el comando y el archivo de origen en el encabezado.

Uso (desde mg\\, con el venv activo):
    python -X utf8 validacion\\resultados_revision_cap5\\scripts\\generar_pantallazos.py
"""

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

RAIZ = Path(__file__).resolve().parents[3]
BASE = RAIZ / "validacion" / "resultados_revision_cap5"
SALIDA = BASE / "pantallazos"

ANTERIOR_22KW = RAIZ / "herramientas" / "local_sin_git" / "salida_sintetica" / "resumen.txt"


def recortar(lineas, inicio, fin=None, desde_linea=0):
    """Lineas desde la primera que empieza con `inicio` hasta la anterior a la primera que empieza con `fin`."""
    i = next(k for k in range(desde_linea, len(lineas)) if lineas[k].startswith(inicio))
    if fin is None:
        return lineas[i:], i
    j = next(k for k in range(i + 1, len(lineas)) if lineas[k].startswith(fin))
    return lineas[i:j], i


def dibujar(nombre, comando, archivo, cuerpo):
    encabezado = [f"$ {comando}", f"# salida: {archivo}", ""]
    lineas = encabezado + [l.rstrip() for l in cuerpo]
    ancho_car = max(len(l) for l in lineas)
    tamano = 9
    ancho = ancho_car * tamano * 0.6 / 72 + 0.8
    alto = len(lineas) * tamano * 1.3 / 72 + 0.7
    fig = plt.figure(figsize=(ancho, alto), dpi=150, facecolor="#0f1720")
    for k, texto in enumerate(lineas):
        color = "#7ee0a1" if k == 0 else ("#8aa4b8" if k == 1 else "#e6edf3")
        if texto.startswith(("==", "###", "--")):
            color = "#ffd479"
        fig.text(0.4 / ancho, 1 - (0.35 + k * tamano * 1.3 / 72) / alto, texto, family="DejaVu Sans Mono", fontsize=tamano,
                 color=color, va="top")
    SALIDA.mkdir(exist_ok=True)
    fig.savefig(SALIDA / nombre, facecolor=fig.get_facecolor())
    plt.close(fig)
    print("listo", nombre)


def leer(ruta):
    return Path(ruta).read_text(encoding="utf-8").splitlines()


def sinteticos_22kw():
    for etiqueta, ruta, rel in (
        ("actual", BASE / "sinteticos_22kw" / "resumen.txt", "validacion/resultados_revision_cap5/sinteticos_22kw/resumen.txt"),
        ("anterior", ANTERIOR_22KW, "herramientas/local_sin_git/salida_sintetica/resumen.txt (corrida previa al criterio de ruido local)"),
    ):
        lineas = leer(ruta)
        cmd = "python -X utf8 herramientas\\local_sin_git\\generar_sintetico_desalineacion_vacio_y_carga.py"
        if etiqueta == "anterior":
            cmd += "    # misma corrida con relacion_sobre_ruido_local_minima = None (reproduce el resultado previo)"
        parte_a, _ = recortar(lineas, "Desalineacion sintetica", "== vacio | con_orientacion | sensor 1")
        parte_b, _ = recortar(lineas, "== vacio | con_orientacion | sensor 1", "Ejemplo,")
        dibujar(f"22kw_{etiqueta}_1_carga75.png", cmd, rel, parte_a)
        dibujar(f"22kw_{etiqueta}_2_vacio.png", cmd, rel, parte_b)


def ottawa():
    ruta = BASE / "motor" / "resumen.txt"
    lineas = leer(ruta)
    rel = "validacion/resultados_revision_cap5/motor/resumen.txt"
    cmd = "python -X utf8 herramientas\\validar_motor.py --salida validacion\\resultados_revision_cap5\\motor"
    bloque, _ = recortar(lineas, "### Ottawa — reglas de rotor — escenario sin_linea_base", "### Ottawa — reglas de rotor — escenario con_linea_base")
    dibujar("ottawa_1_sin_linea_base.png", cmd, rel, bloque)
    i = next(k for k, l in enumerate(lineas) if l.startswith("### Ottawa — reglas de rotor — escenario con_linea_base"))
    bloque, _ = recortar(lineas, "Ventanas con la hipótesis ≥ 0.70", "Ventanas con la hipótesis ≥ 0.90", i)
    dibujar("ottawa_2_con_linea_base_conf070.png", cmd, rel, ["### Ottawa — con línea base (escenario con_linea_base)", ""] + bloque)
    bloque, _ = recortar(lineas, "### Ottawa — indicador de cambio", "Por velocidad y carga")
    dibujar("ottawa_3_indicador_cambio.png", cmd, rel, bloque)
    bloque, _ = recortar(lineas, "Hipótesis principal de rotor con línea base", "### CWRU")
    dibujar("ottawa_4_hipotesis_principal.png", cmd, rel, bloque)


def mafaulda(carpeta="mafaulda", prefijo="mafaulda", cmd=None, cabecera=None):
    ruta = BASE / carpeta / "resumen.txt"
    if not ruta.exists():
        print("no existe", ruta)
        return
    lineas = leer(ruta)
    rel = f"validacion/resultados_revision_cap5/{carpeta}/resumen.txt"
    cmd = cmd or "python -X utf8 herramientas\\validar_mafaulda.py --salida validacion\\resultados_revision_cap5\\mafaulda"
    for k, (escenario, etiqueta) in enumerate((("antes", "antes"), ("solo_relacion", "solo_relacion"), ("relacion_y_ejes", "relacion_y_ejes")), 1):
        try:
            bloque, _ = recortar(lineas, f"== Escenario: {escenario}", "-- calibracion")
        except StopIteration:
            continue
        # el recorte llega hasta "-- calibracion": incluye el encabezado del escenario y la tabla de reserva
        dibujar(f"{prefijo}_{k}_{etiqueta}.png", cmd, rel, bloque)


def sro():
    ruta = BASE / "sro" / "resumen.txt"
    lineas = leer(ruta)
    bloque, _ = recortar(lineas, "== Escenario: sin_relacion", "== Escenario: con_relacion")
    dibujar(
        "sro_1_sin_relacion.png",
        'python -X utf8 herramientas\\validar_sro.py --datos "<carpeta SRO-Cross-Speed-Dataset>" --velocidades 900',
        "validacion/resultados_revision_cap5/sro/resumen.txt",
        lineas[:3] + [""] + bloque,
    )


if __name__ == "__main__":
    sinteticos_22kw()
    ottawa()
    mafaulda()
    mafaulda(
        "vertical", "mafaulda_vertical",
        "python -X utf8 herramientas\\validar_mafaulda.py --carpetas normal/normal vertical-misalignment/vertical-misalignment --salida ...\\vertical",
    )
    sro()
