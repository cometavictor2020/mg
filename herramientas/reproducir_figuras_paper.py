"""
Reproduce, con el motor de MotorGuardian, los resultados del paper de Tyagi y Panigrahi (2017, "An improved
envelope detection method using particle swarm optimisation for rolling element bearing fault diagnosis",
Journal of Computational Design and Engineering 4, 305-317) para las figuras 2, 6, 7, 9 y 13, y emite el
diagnostico de rodamientos de cada archivo. Es el material del corte de iteraciones para el informe.

Archivos (CWRU Bearing Data Center, rodamiento SKF 6205-2RS del lado de accionamiento, 48 kHz, 0 hp):
    135.mat  falla de pista exterior 7 mils   (caso 1 del paper; figuras 2, 6, 7, 9 y 13)
    109.mat  falla de pista interior 7 mils   (caso 13; figura 13)
    122.mat  falla de elemento rodante 7 mils (caso 25; figuras 9 y 13)
    238.mat / 213.mat / 226.mat  las mismas fallas con 21 mils (casos 9, 21 y 33; figura 13)
    97.mat   rodamiento sano (Normal_0; tabla 4)
El paper tambien usa 14 mils (figura 13), que no esta en la carpeta de datos.

Que se calcula:
    1. Lectura: variable, muestras, frecuencia de muestreo, duracion y velocidad de cada archivo.
    2. Diagnostico del motor: con la señal completa (como la analiza la pantalla Laboratorio) y por
       ventanas de 2 s (como la aplicacion analiza una medicion).
    3. Figuras 2 y 9: amplitud en la frecuencia de falla en el espectro SIN envolvente y en la envolvente
       sin filtrar, y su cociente (el paper reporta 0,0012 g, 1,1081 g y 923 veces en el caso 1).
    4. Figuras 6 y 7 (solo 135.mat): envolvente con las dos bandas de resonancia (leidas de los rectangulos
       de la figura 6, por lo que son aproximadas) y, con --pso, con la ventana optimizada por PSO.
    5. Figura 13: amplitud del pico de falla segun el tamaño de la falla (7 y 21 mils).
    6. Tabla 4 (con --pso): amplificacion y PMR del rodamiento sano a las tres frecuencias de falla.

Frecuencias de falla: multiplos de la frecuencia de giro de la tabla 1 del paper (ORF 3,5848; IRF 5,4152;
REF 4,7135; este ultimo es 2 x BSF). La velocidad es la que declara cada archivo (1796 o 1797 r/min).

Uso:
    cd C:\\Users\\comet\\Documents\\mg
    .\\venv\\Scripts\\python.exe herramientas\\reproducir_figuras_paper.py
    .\\venv\\Scripts\\python.exe herramientas\\reproducir_figuras_paper.py --pso     (varios minutos)
"""

import argparse
import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd

RUTA_PROYECTO = Path(__file__).parent.parent
sys.path.insert(0, str(RUTA_PROYECTO))

from backend.procesamiento.diagnostico import cargar_normativa  # noqa: E402
from backend.procesamiento.diagnostico_rodamientos import evaluar_rodamiento_detallado  # noqa: E402
from backend.procesamiento.envolvente import calcular_espectro_envolvente  # noqa: E402
from backend.procesamiento.importador_mat import leer_canales_y_escalares  # noqa: E402
from backend.procesamiento.pso_envolvente import _filtrar_pasabanda, amplitud_en_frecuencia, optimizar_ventana  # noqa: E402

# Ruta por defecto (equipo del desarrollador); se puede pasar por argumento.
DATOS_POR_DEFECTO = (
    r"C:\Todo\Usach\Proyecto-titulo\Datasets\Vibraciones-Kaggle\Dataset02-MFPT-Mechanical Failure Prevention "
    r"Technology\Paper-Envolvente-Transformada-Hilbert"
)

FRECUENCIA_MUESTREO = 48000.0  # Hz; los archivos de la serie 48K-Drive y 97.mat (5 s, ~243 500 muestras)
DURACION_VENTANA_S = 2.0
RODAMIENTO_SKF_6205 = SimpleNamespace(
    codigo="SKF-6205", numero_elementos_rodantes=9, diametro_elemento_mm=7.94, diametro_paso_mm=39.04, angulo_contacto_grados=0.0,
)
MULTIPLO_PAPER = {"BPFO": 3.5848, "BPFI": 5.4152, "BPFR": 4.7135}  # tabla 1 del paper (x frecuencia de giro)
FALLA_DE_FRECUENCIA = {"BPFO": "pista_exterior", "BPFI": "pista_interior", "BPFR": "elemento_rodante"}
FRECUENCIA_MAXIMA_PMR_HZ = 450.0  # la figura 11 del paper calcula el PMR sobre 0-450 Hz

# (carpeta, archivo, caso del paper, etiqueta, frecuencia que corresponde a la falla, tamaño en mils)
ARCHIVOS = [
    ("48K-Drive/Set01-07plg1707RPM", "135.mat", 1, "pista exterior 7 mils", "BPFO", 7),
    ("48K-Drive/Set01-07plg1707RPM", "109.mat", 13, "pista interior 7 mils", "BPFI", 7),
    ("48K-Drive/Set01-07plg1707RPM", "122.mat", 25, "elemento rodante 7 mils", "BPFR", 7),
    ("48K-Drive/Set02-021plg1707RPM", "238.mat", 9, "pista exterior 21 mils", "BPFO", 21),
    ("48K-Drive/Set02-021plg1707RPM", "213.mat", 21, "pista interior 21 mils", "BPFI", 21),
    ("48K-Drive/Set02-021plg1707RPM", "226.mat", 33, "elemento rodante 21 mils", "BPFR", 21),
    ("Normal-Dataset", "97.mat", None, "sano (0 hp)", None, None),
]

# Valores que el paper reporta, para compararlos en el resumen.
PAPER_CASO_1 = {"crudo_g": 0.0012, "envolvente_pso_g": 1.1081, "amplificacion": 923, "pmr": 89.7}
PAPER_FIG_7 = {"resonancia_1_g": 0.84, "resonancia_2_g": 0.41, "pso_g": 1.108}  # leidos del grafico (aproximados)
PAPER_AMPLIFICACION_FIG_10 = {1: "923", 9: "~600", 13: "~110", 21: "~150", 25: "~14", 33: "108"}  # 1 y 33 del texto; el resto leido del grafico
PAPER_TABLA_4_0HP = {"BPFO": (7.9, 1.79), "BPFI": (1.74, 2.07), "BPFR": (26.0, 1.97)}  # (amplificacion, PMR)
# Bandas de la figura 6, leidas del grafico: (frecuencia central Hz, ancho Hz).
BANDAS_FIGURA_6 = {"resonancia 1 (3300-3600 Hz)": (3450, 300), "resonancia 2 (2650-3000 Hz)": (2825, 350), "PSO del paper (centro 2584, ancho 832)": (2584, 832)}


def leer_archivo(ruta):
    canales, escalares = leer_canales_y_escalares(ruta.read_bytes())
    nombre = next(n for n in canales if "de_time" in n.lower())
    rpm = next((v for n, v in escalares.items() if "rpm" in n.lower()), None)
    return nombre, canales[nombre], rpm


def hipotesis_texto(hipotesis):
    return "; ".join(f"{h['falla'].replace('rodamiento_', '')} {h['confianza']:.2f}" for h in hipotesis) or "(ninguna)"


def diagnosticar(señal, rpm, normativa):
    datos = pd.DataFrame({"vibracion_x": señal})
    return evaluar_rodamiento_detallado(datos, FRECUENCIA_MUESTREO, rpm, RODAMIENTO_SKF_6205, normativa)[0]


def ventanas(señal, duracion=DURACION_VENTANA_S):
    largo = int(round(FRECUENCIA_MUESTREO * duracion))
    return [señal[i * largo:(i + 1) * largo] for i in range(len(señal) // largo)]


def amplitud_cruda(señal, objetivo):
    n = len(señal)
    frecuencias = np.fft.rfftfreq(n, 1 / FRECUENCIA_MUESTREO)
    amplitudes = 2 / n * np.abs(np.fft.rfft(señal - señal.mean()))
    return amplitud_en_frecuencia(frecuencias, amplitudes, objetivo)


def pico_y_pmr(señal, objetivo):
    frecuencias, amplitudes = calcular_espectro_envolvente(señal, FRECUENCIA_MUESTREO, FRECUENCIA_MAXIMA_PMR_HZ)
    pico = amplitud_en_frecuencia(frecuencias, amplitudes, objetivo)
    return pico, pico / float(np.mean(amplitudes[frecuencias > 0]))


def con_pso(señal, objetivo):
    r = optimizar_ventana(señal, FRECUENCIA_MUESTREO, objetivo, enjambre=30, iteraciones=30)
    frecuencias, amplitudes = np.asarray(r["espectro_frecuencias"]), np.asarray(r["espectro_amplitudes"])
    mascara = (frecuencias > 0) & (frecuencias <= FRECUENCIA_MAXIMA_PMR_HZ)
    return r["amplitud"], r["amplitud"] / float(np.mean(amplitudes[mascara])), r["frecuencia_central"], r["ancho_banda"]


def ejecutar(carpeta, usar_pso):
    normativa = cargar_normativa()
    raiz = Path(carpeta)
    lineas, filas = [], []

    def escribir(texto=""):
        print(texto)
        lineas.append(texto)

    escribir("REPRODUCCION DE LAS FIGURAS 2, 6, 7, 9 Y 13 DEL PAPER DE TYAGI Y PANIGRAHI (2017)")
    escribir(f"Motor: criterios_proyecto.yaml v{normativa['metadata_criterios_proyecto']['version']}; frecuencia de muestreo {FRECUENCIA_MUESTREO:g} Hz")
    datos = {}

    escribir("\n=== 1. LECTURA Y DIAGNOSTICO DEL MOTOR ===")
    escribir("(\"completa\" = señal entera, como la analiza la pantalla Laboratorio; \"2 s\" = ventanas de 2 s, como una medicion en la aplicacion)")
    for subcarpeta, nombre_archivo, caso, etiqueta, clave, tamaño in ARCHIVOS:
        variable, señal, rpm = leer_archivo(raiz / subcarpeta / nombre_archivo)
        datos[nombre_archivo] = (señal, rpm)
        escribir(f"\n{nombre_archivo} — {etiqueta}" + (f" (caso {caso} del paper)" if caso else ""))
        escribir(f"  lectura: variable {variable}, {len(señal)} muestras = {len(señal) / FRECUENCIA_MUESTREO:.2f} s a {FRECUENCIA_MUESTREO:g} Hz, velocidad declarada {rpm:g} r/min")
        completa = diagnosticar(señal, rpm, normativa)
        escribir(f"  diagnostico completa: {hipotesis_texto(completa)}")
        por_ventana = [diagnosticar(v, rpm, normativa) for v in ventanas(señal)]
        for i, h in enumerate(por_ventana):
            escribir(f"  diagnostico 2 s, ventana {i}: {hipotesis_texto(h)}")
        esperada = FALLA_DE_FRECUENCIA.get(clave)
        acierto_completa = (esperada is not None and any(h["falla"] == f"rodamiento_{esperada}" and h["confianza"] >= 0.5 for h in completa)) or (esperada is None and not completa)
        espurias = [h["falla"] for h in completa if esperada is None or h["falla"] != f"rodamiento_{esperada}"]
        escribir(f"  esperado: {esperada or 'sano (sin hipotesis)'} -> " + ("coincide" if acierto_completa and not espurias else "NO coincide" if not acierto_completa else "coincide, con hipotesis adicionales: " + ", ".join(espurias)))
        filas.append({"archivo": nombre_archivo, "caso_paper": caso, "etiqueta": etiqueta, "esperada": esperada or "sano", "diagnostico_completa": hipotesis_texto(completa),
                      **{f"ventana_{i}": hipotesis_texto(h) for i, h in enumerate(por_ventana)}})

    escribir("\n=== 2. FIGURAS 2 Y 9: ESPECTRO SIN ENVOLVENTE FRENTE A ENVOLVENTE (señal completa) ===")
    escribir("amplitud en la frecuencia de falla, en g; el paper reporta para el caso 1: crudo 0,0012, envolvente 1,1081 (923 veces)")
    escribir(f"{'archivo':8} {'falla':6} {'f [Hz]':>7} {'crudo':>9} {'envolvente':>11} {'veces':>6} {'PMR':>6}   paper (fig. 10, aprox.)")
    for subcarpeta, nombre_archivo, caso, etiqueta, clave, tamaño in ARCHIVOS:
        if clave is None:
            continue
        señal, rpm = datos[nombre_archivo]
        objetivo = MULTIPLO_PAPER[clave] * rpm / 60
        crudo = amplitud_cruda(señal, objetivo)
        envolvente, pmr = pico_y_pmr(señal, objetivo)
        escribir(f"{nombre_archivo:8} {clave:6} {objetivo:7.1f} {crudo:9.5f} {envolvente:11.4f} {envolvente / crudo:6.0f} {pmr:6.1f}   caso {caso}: {PAPER_AMPLIFICACION_FIG_10.get(caso, '-')}")

    señal_1, rpm_1 = datos["135.mat"]
    objetivo_1 = MULTIPLO_PAPER["BPFO"] * rpm_1 / 60
    escribir("\n=== 3. FIGURAS 6 Y 7: ENVOLVENTE SEGUN LA BANDA DE FILTRO (135.mat, BPFO) ===")
    escribir(f"paper (fig. 7, valores leidos del grafico): resonancia 1 ~{PAPER_FIG_7['resonancia_1_g']} g, resonancia 2 ~{PAPER_FIG_7['resonancia_2_g']} g, PSO {PAPER_FIG_7['pso_g']} g")
    escribir("las bandas se leyeron de los rectangulos de la figura 6, asi que son aproximadas")
    sin_filtro, pmr = pico_y_pmr(señal_1, objetivo_1)
    escribir(f"  sin filtrar:                                        {sin_filtro:.4f} g   PMR {pmr:.1f}")
    for nombre, (central, ancho) in BANDAS_FIGURA_6.items():
        pico, pmr = pico_y_pmr(_filtrar_pasabanda(señal_1, FRECUENCIA_MUESTREO, central, ancho), objetivo_1)
        escribir(f"  {nombre:50} {pico:.4f} g   PMR {pmr:.1f}")
    if usar_pso:
        pico, pmr, central, ancho = con_pso(señal_1, objetivo_1)
        escribir(f"  PSO del sistema (centro {central:.0f} Hz, ancho {ancho:.0f} Hz):{'':14} {pico:.4f} g   PMR {pmr:.1f}")
        escribir("  nota: la banda dibujada en la figura 6 (centro 2584 Hz, ancho 832 Hz) no reproduce el 1,108 g del paper con estos datos; el valor se alcanza con una banda muy ancha, practicamente la envolvente sin filtrar")
    else:
        escribir("  (PSO omitido; usa --pso para optimizar la ventana, tarda varios minutos)")

    escribir("\n=== 4. FIGURA 13: AMPLITUD DEL PICO DE FALLA SEGUN EL TAMAÑO (envolvente sin filtrar, 0 hp) ===")
    escribir("paper: en pista exterior el pico baja al aumentar la falla; en pista interior y elemento rodante sube")
    escribir(f"{'falla':18} {'7 mils':>9} {'21 mils':>9}   tendencia")
    for clave, archivo7, archivo21 in (("BPFO", "135.mat", "238.mat"), ("BPFI", "109.mat", "213.mat"), ("BPFR", "122.mat", "226.mat")):
        valores = []
        for archivo in (archivo7, archivo21):
            señal, rpm = datos[archivo]
            valores.append(pico_y_pmr(señal, MULTIPLO_PAPER[clave] * rpm / 60)[0])
        esperado_baja = clave == "BPFO"
        sigue = (valores[1] < valores[0]) == esperado_baja
        escribir(f"{FALLA_DE_FRECUENCIA[clave]:18} {valores[0]:9.4f} {valores[1]:9.4f}   {'baja' if valores[1] < valores[0] else 'sube'} ({'coincide con el paper' if sigue else 'NO coincide con el paper'})")
    escribir("(la carpeta de datos no incluye los archivos de 14 mils que tambien muestra la figura 13)")

    if usar_pso:
        escribir("\n=== 5. TABLA 4: RODAMIENTO SANO (97.mat, 0 hp), PSO sobre cada frecuencia de falla ===")
        escribir("criterio del paper: hay falla solo si amplificacion >= 10 y PMR >= 3; amplificacion = pico de la envolvente / pico del espectro sin envolvente")
        señal_sana, rpm_sana = datos["97.mat"]
        escribir(f"{'falla':6} {'ampl.':>7} {'PMR':>6}   paper (amplificacion, PMR)")
        for clave, objetivo_multiplo in MULTIPLO_PAPER.items():
            objetivo = objetivo_multiplo * rpm_sana / 60
            pico, pmr, _, _ = con_pso(señal_sana, objetivo)
            escribir(f"{clave:6} {pico / amplitud_cruda(señal_sana, objetivo):7.1f} {pmr:6.2f}   {PAPER_TABLA_4_0HP[clave]}")

    return "\n".join(lineas), pd.DataFrame(filas)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--datos", default=DATOS_POR_DEFECTO, help="carpeta Paper-Envolvente-Transformada-Hilbert")
    parser.add_argument("--salida", default=str(RUTA_PROYECTO / "validacion" / "resultados_corte"), help="carpeta donde se guardan el resumen y el CSV")
    parser.add_argument("--pso", action="store_true", help="optimiza la ventana con PSO (figura 7 y tabla 4); tarda varios minutos")
    argumentos = parser.parse_args()

    texto, tabla = ejecutar(argumentos.datos, argumentos.pso)
    salida = Path(argumentos.salida)
    salida.mkdir(parents=True, exist_ok=True)
    (salida / "resumen.txt").write_text(texto, encoding="utf-8")
    tabla.to_csv(salida / "diagnostico_por_archivo.csv", index=False)
    print(f"\nGuardado en {salida}")


if __name__ == "__main__":
    main()
