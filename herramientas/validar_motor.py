"""
Validacion formal del motor de diagnostico contra datasets publicos con
etiquetas (D-064, ver PROYECTO.md).

Reproduce el protocolo completo y deja todos los resultados por ventana en
CSV, para que cualquier tabla del informe pueda rehacerse. No usa la base de
datos ni la API: llama a las mismas funciones que usa la aplicacion
(calcular_fft, diagnosticar_sensor, ...), sobre ventanas de 2 s como ella.

Experimentos (cada uno se puede elegir con --experimentos):
    mfpt_rodamientos   Dataset MFPT (Society for Machinery Failure Prevention
                       Technology): sano / pista exterior / pista interior de un
                       rodamiento de geometria conocida, 1 eje. Mide si el motor
                       de rodamientos detecta la falla correcta y cuantas
                       alarmas falsas da en el sano.
    mfpt_velocidad     Los mismos archivos: el MFPT declara la velocidad real, asi
                       que sirve para validar la estimacion de velocidad (D-057)
                       y el aviso de inconsistencia (D-058) cuando la velocidad
                       nominal del equipo esta mal.
    ottawa_rotor       Dataset de la Universidad de Ottawa (motor trifasico, 3
                       acelerometros, 8 estados de salud, 4 velocidades, con y sin
                       carga): reglas de desbalanceo / desalineacion con y sin linea
                       base, e indicador de cambio respecto de la linea base.
    cwru_caso          Un archivo de CWRU (caso unico, no estadistica).

Ground truth: sale solo del nombre de los archivos y de la documentacion del
dataset; nunca de lo que el motor responde. Los archivos que el dataset no
documenta con claridad (ejemplos "Real World" del MFPT; velocidades variables
del Ottawa) se excluyen y se informa.

Uso (PowerShell, desde mg\\, con el venv activo):
    python herramientas\\validar_motor.py --salida validacion\\resultados
    python herramientas\\validar_motor.py --experimentos mfpt_rodamientos ottawa_rotor
"""

import argparse
import hashlib
import json
import math
import platform
import sys
import time
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

RUTA_PROYECTO = Path(__file__).parent.parent
sys.path.append(str(RUTA_PROYECTO))

import numpy as np
import pandas as pd

from backend.procesamiento.cambio_linea_base import calcular_valores_velocidad_linea_base
from backend.procesamiento.diagnostico import (
    TOLERANCIA_FRECUENCIA_PCT,
    analizar_espectro_fft,
    cargar_normativa,
    diagnosticar_sensor,
    resolver_velocidad,
    verificar_consistencia_velocidad,
)
from backend.procesamiento.frecuencia import calcular_fft
from backend.procesamiento.importador_mat import leer_canales_y_escalares
from backend.procesamiento.linea_base import calcular_valores_linea_base

# Rutas por defecto (equipo del desarrollador); se pueden pasar por argumento.
MFPT_POR_DEFECTO = r"C:\Todo\Usach\Proyecto-titulo\Titulo\Datasets-csv\03.-MFPT\MFPT Fault Data Sets"
OTTAWA_POR_DEFECTO = r"C:\Todo\Usach\Proyecto-titulo\Titulo\Datasets-csv\05.-Mendeley\2_CSV_Data_Files"
CWRU_POR_DEFECTO = (
    r"C:\Todo\Usach\Proyecto-titulo\Datasets\Vibraciones-Kaggle\Dataset02-MFPT-Mechanical Failure Prevention "
    r"Technology\Paper-Envolvente-Transformada-Hilbert\135.mat"
)

DURACION_VENTANA_S = 2.0  # igual que la aplicacion (DURACION_VENTANA_SEGUNDOS)
UMBRALES = (0.30, 0.50, 0.70, 0.90)  # 0.30 es el minimo con que la app muestra una hipotesis

# MFPT: geometria de NiceBearing.m del propio dataset (8 elementos, d = 0.235, D = 1.245, contacto 0).
# Las unidades no se declaran, pero solo importa la proporcion d/D.
RODAMIENTO_MFPT = SimpleNamespace(
    codigo="MFPT-NiceBearing", numero_elementos_rodantes=8, diametro_elemento_mm=0.235,
    diametro_paso_mm=1.245, angulo_contacto_grados=0.0,
)
RODAMIENTO_SKF_6205 = SimpleNamespace(
    codigo="SKF-6205", numero_elementos_rodantes=9, diametro_elemento_mm=7.94,
    diametro_paso_mm=39.04, angulo_contacto_grados=0.0,
)
FALLAS_RODAMIENTO = {
    "BPFO": "rodamiento_pista_exterior",
    "BPFI": "rodamiento_pista_interior",
    "BSF": "rodamiento_elemento_rodante",
    "FTF": "rodamiento_jaula",
}
FALLAS_ROTOR = {
    "desbalanceo": "desbalanceo",
    "desal_paralela": "desalineacion_paralela",
    "desal_angular": "desalineacion_angular",
}

VELOCIDADES_OTTAWA_HZ = {1: 15, 2: 30, 3: 45, 4: 60}  # codigos 1-4 del nombre = velocidad constante
CLASES_OTTAWA = ["H_H", "R_U", "R_M", "B_R", "K_A", "S_W", "V_U", "F_B"]
NOMBRES_CLASE_OTTAWA = {
    "H_H": "sano", "R_U": "desbalanceo de rotor", "R_M": "desalineacion de rotor", "B_R": "rotor doblado",
    "K_A": "barras rotas", "S_W": "bobinado del estator", "V_U": "desbalance de voltaje", "F_B": "rodamiento (sin geometria)",
}

NORMATIVA = cargar_normativa()


# ---------------------------------------------------------------------------
# Utilidades
# ---------------------------------------------------------------------------

def intervalo_wilson(exitos, total, z=1.96):
    """Intervalo de confianza de Wilson al 95 % para una proporcion. Devuelve (proporcion, bajo, alto)."""
    if total == 0:
        return (math.nan, math.nan, math.nan)
    p = exitos / total
    denominador = 1 + z ** 2 / total
    centro = (p + z ** 2 / (2 * total)) / denominador
    margen = z * math.sqrt(p * (1 - p) / total + z ** 2 / (4 * total ** 2)) / denominador
    return (p, max(0.0, centro - margen), min(1.0, centro + margen))


def formato_proporcion(exitos, total):
    if total == 0:
        return "—"
    p, bajo, alto = intervalo_wilson(exitos, total)
    return f"{exitos}/{total} = {p * 100:.0f} % [{bajo * 100:.0f}–{alto * 100:.0f}]"


def ventanas(señal, frecuencia_muestreo, duracion=DURACION_VENTANA_S):
    """Ventanas contiguas sin solapamiento de `duracion` s (se descarta el resto incompleto)."""
    largo = int(round(frecuencia_muestreo * duracion))
    cantidad = len(señal) // largo
    return [señal[i * largo:(i + 1) * largo] for i in range(cantidad)]


def confianza_de(hipotesis, nombre_falla):
    return max((h["confianza"] for h in hipotesis if h["falla"] == nombre_falla), default=0.0)


def columnas_de_hipotesis(hipotesis):
    fila = {}
    for abreviatura, falla in FALLAS_RODAMIENTO.items():
        fila[f"conf_{abreviatura}"] = confianza_de(hipotesis, falla)
    for abreviatura, falla in FALLAS_ROTOR.items():
        fila[f"conf_{abreviatura}"] = confianza_de(hipotesis, falla)
    fila["hipotesis"] = "; ".join(f"{h['falla']}:{h['confianza']:.2f}" for h in hipotesis)
    return fila


def linea_base_de(df, fs, rpm_nominal, unidad):
    """Linea base como la arma la API: valores en 1x/2x/3x y velocidad RMS de banda por eje."""
    fft = calcular_fft(df, fs, 300)
    velocidad = resolver_velocidad(fft, rpm_nominal, None, NORMATIVA)
    valores = calcular_valores_linea_base(fft, velocidad["rpm"], TOLERANCIA_FRECUENCIA_PCT)
    valores["velocidad_origen"] = velocidad["origen"]
    valores["velocidad_rms"] = calcular_valores_velocidad_linea_base(df, fs, unidad, velocidad["rpm"], NORMATIVA)
    return {"valores": valores, "fecha": "referencia"}


# ---------------------------------------------------------------------------
# MFPT
# ---------------------------------------------------------------------------

def clase_mfpt(nombre_archivo):
    nombre = nombre_archivo.lower()
    if nombre.startswith("baseline"):
        return "sano"
    if nombre.startswith("outerrace"):
        return "pista_exterior"
    if nombre.startswith("innerrace"):
        return "pista_interior"
    return None


def cargar_mfpt(directorio):
    """Archivos etiquetados del MFPT. Un archivo repetido (mismo contenido, ej. la copia de
    InnerRaceFault_vload_7.mat dentro de '5 - Analyses') se usa una sola vez: contarlo dos
    veces inflaria su clase. Devuelve (archivos, excluidos, duplicados)."""
    archivos, excluidos, duplicados, vistos = [], [], [], set()
    for ruta in sorted(Path(directorio).rglob("*.mat")):
        clase = clase_mfpt(ruta.name)
        if clase is None:
            excluidos.append(ruta.name)
            continue
        contenido = ruta.read_bytes()
        huella = hashlib.sha1(contenido).hexdigest()
        if huella in vistos:
            duplicados.append(f"{ruta.parent.name}/{ruta.name}")
            continue
        vistos.add(huella)
        canales, escalares = leer_canales_y_escalares(contenido)
        archivos.append(
            {
                "archivo": ruta.name,
                "grupo": ruta.parent.name,
                "clase": clase,
                "señal": canales["bearing.gs"],
                "fs": int(round(escalares["bearing.sr"])),
                "rpm_declarada": escalares["bearing.rate"] * 60,  # el MFPT declara la velocidad en Hz
            }
        )
    return archivos, excluidos, duplicados


ERRORES_NOMINAL_PCT = (0, -10, -5, -3, 3, 5, 10)


def experimento_mfpt_rodamientos(archivos):
    """
    Escenarios: 'velocidad_declarada' (el operador declara la real, como en la carga de una medicion)
    y 'nominal_<p>' = sin declarar velocidad y con la nominal del equipo equivocada en p % (0 = bien):
    en ese caso el motor estima la velocidad desde el espectro (D-057) o, si no puede, usa la nominal.
    """
    escenarios = ["velocidad_declarada"] + [f"nominal_{p:+d}" for p in ERRORES_NOMINAL_PCT]
    filas = []
    for escenario in escenarios:
        for archivo in archivos:
            p = 0 if escenario == "velocidad_declarada" else int(escenario.split("_")[1])
            rpm_nominal = 1500.0 * (1 + p / 100)  # la velocidad real de los ensayos del MFPT es 25 Hz = 1500 r/min
            for indice, ventana in enumerate(ventanas(archivo["señal"], archivo["fs"])):
                df = pd.DataFrame({"vibracion_x": ventana})
                fft = calcular_fft(df, archivo["fs"], 300)
                d = diagnosticar_sensor(
                    fft, rpm_nominal, datos_crudos=df, frecuencia_muestreo=archivo["fs"], rodamiento=RODAMIENTO_MFPT,
                    unidad_señal="g", rpm_real=archivo["rpm_declarada"] if escenario == "velocidad_declarada" else None,
                )
                fila = {
                    "experimento": "mfpt_rodamientos", "escenario": escenario, "archivo": archivo["archivo"], "grupo": archivo["grupo"],
                    "clase_real": archivo["clase"], "ventana": indice, "fs": archivo["fs"],
                    "rpm_usada": round(d["velocidad"]["rpm"], 2), "origen_velocidad": d["velocidad"]["origen"],
                    "calidad_medicion": (d.get("calidad_medicion") or {}).get("estado"),
                }
                fila.update(columnas_de_hipotesis(d["hipotesis"]))
                filas.append(fila)
    return pd.DataFrame(filas)


def experimento_mfpt_velocidad(archivos, perturbaciones=(-10, -5, -3, 0, 3, 5, 10)):
    """Velocidad nominal equivocada en p %: ¿la estimacion recupera la declarada? ¿el aviso D-058 salta?"""
    filas = []
    for archivo in archivos:
        for indice, ventana in enumerate(ventanas(archivo["señal"], archivo["fs"])):
            fft = calcular_fft(pd.DataFrame({"vibracion_x": ventana}), archivo["fs"], 300)
            for p in perturbaciones:
                nominal = 1500.0 * (1 + p / 100)
                velocidad = resolver_velocidad(fft, nominal, None, NORMATIVA)
                hallazgos, picos = analizar_espectro_fft(fft, velocidad["rpm"])
                verificacion = verificar_consistencia_velocidad(hallazgos["1x"], picos, velocidad["rpm"], NORMATIVA)
                error = (velocidad["rpm"] - archivo["rpm_declarada"]) / archivo["rpm_declarada"] * 100
                filas.append(
                    {
                        "experimento": "mfpt_velocidad", "archivo": archivo["archivo"], "clase_real": archivo["clase"], "ventana": indice,
                        "error_nominal_pct": p, "rpm_nominal": round(nominal, 1), "rpm_declarada": archivo["rpm_declarada"],
                        "rpm_resuelta": round(velocidad["rpm"], 2), "origen": velocidad["origen"],
                        "error_resuelta_pct": round(error, 3), "aviso_inconsistencia": bool(verificacion["inconsistente"]),
                    }
                )
    return pd.DataFrame(filas)


# ---------------------------------------------------------------------------
# Ottawa
# ---------------------------------------------------------------------------

def cargar_ottawa(directorio, clases=CLASES_OTTAWA):
    """{(clase, codigo_velocidad, carga): DataFrame vibracion_x/y/z} (3 acelerometros como X, Y, Z)."""
    base = Path(directorio)
    datos = {}
    for carga, carpeta in ((0, "1_Unloaded_Condition"), (1, "2_Loaded_Condition")):
        for clase in clases:
            for codigo in VELOCIDADES_OTTAWA_HZ:
                tabla = pd.read_csv(base / carpeta / f"{clase}_{codigo}_{carga}.csv", usecols=[0, 2, 3])
                tabla.columns = ["vibracion_x", "vibracion_y", "vibracion_z"]
                datos[(clase, codigo, carga)] = tabla
    return datos


def experimento_ottawa(datos, fs=42000):
    filas = []
    nominal_por_codigo = {c: hz * 60 for c, hz in VELOCIDADES_OTTAWA_HZ.items()}
    for carga in (0, 1):
        for codigo, rpm_nominal in nominal_por_codigo.items():
            sano = ventanas_df(datos[("H_H", codigo, carga)], fs)
            referencia = linea_base_de(sano[0], fs, rpm_nominal, "m/s2")  # ventana 0 del sano = linea base
            for clase in CLASES_OTTAWA:
                for indice, df in enumerate(ventanas_df(datos[(clase, codigo, carga)], fs)):
                    es_referencia = clase == "H_H" and indice == 0
                    fft = calcular_fft(df, fs, 300)
                    for escenario, linea in (("sin_linea_base", None), ("con_linea_base", referencia)):
                        if escenario == "con_linea_base" and es_referencia:
                            continue  # compararla consigo misma no mide nada
                        d = diagnosticar_sensor(
                            fft, rpm_nominal, datos_crudos=df, frecuencia_muestreo=fs, potencia_kw=2.2, tipo_soporte="rigido",
                            unidad_señal="m/s2", linea_base=linea,
                        )
                        cambio = d.get("cambio_linea_base") or {}
                        fila = {
                            "experimento": "ottawa_rotor", "escenario": escenario, "clase_real": clase, "velocidad_hz": VELOCIDADES_OTTAWA_HZ[codigo],
                            "carga": carga, "ventana": indice, "rpm_usada": round(d["velocidad"]["rpm"], 2), "origen_velocidad": d["velocidad"]["origen"],
                            "cambio_nivel": cambio.get("nivel"), "cambio_razon": cambio.get("razon"),
                            "aviso_inconsistencia": bool((d.get("verificacion_velocidad") or {}).get("inconsistente")),
                        }
                        fila.update(columnas_de_hipotesis(d["hipotesis"]))
                        filas.append(fila)
    return pd.DataFrame(filas)


def ventanas_df(df, fs):
    largo = int(round(fs * DURACION_VENTANA_S))
    return [df.iloc[i * largo:(i + 1) * largo].reset_index(drop=True) for i in range(len(df) // largo)]


# ---------------------------------------------------------------------------
# CWRU (caso unico)
# ---------------------------------------------------------------------------

def experimento_cwru(ruta, fs=48000):  # 135.mat es de la serie de 48 kHz (5 s, 243 538 muestras)
    canales, escalares = leer_canales_y_escalares(Path(ruta).read_bytes())
    nombre = next(n for n in canales if "de_time" in n.lower())
    rpm = next(v for n, v in escalares.items() if "rpm" in n.lower())
    señal = canales[nombre]
    filas = []
    for indice, ventana in enumerate(ventanas(señal, fs)):
        df = pd.DataFrame({"vibracion_x": ventana})
        d = diagnosticar_sensor(
            calcular_fft(df, fs, 300), rpm, datos_crudos=df, frecuencia_muestreo=fs, rodamiento=RODAMIENTO_SKF_6205, unidad_señal="g", rpm_real=rpm,
        )
        fila = {"experimento": "cwru_caso", "archivo": Path(ruta).name, "variable": nombre, "ventana": indice, "fs_indicada": fs, "rpm_declarada": rpm}
        fila.update(columnas_de_hipotesis(d["hipotesis"]))
        filas.append(fila)
    return pd.DataFrame(filas)


# ---------------------------------------------------------------------------
# Resumenes
# ---------------------------------------------------------------------------

def tabla_markdown(encabezados, filas):
    lineas = ["| " + " | ".join(encabezados) + " |", "|" + "|".join("---" for _ in encabezados) + "|"]
    lineas += ["| " + " | ".join(str(c) for c in fila) + " |" for fila in filas]
    return "\n".join(lineas)


def resumen_mfpt_nominal_erroneo(df):
    """Una fila por escenario: ¿se conserva la deteccion cuando la velocidad nominal esta mal?"""
    columnas_rod = [f"conf_{k}" for k in FALLAS_RODAMIENTO]
    salida = ["\n### MFPT — rodamientos — efecto de una velocidad nominal equivocada (sin declarar la velocidad real)"]
    for tau in (0.50, 0.70):
        filas = []
        for escenario in df.escenario.unique():
            sub = df[df.escenario == escenario]
            ext, inte, san = sub[sub.clase_real == "pista_exterior"], sub[sub.clase_real == "pista_interior"], sub[sub.clase_real == "sano"]
            filas.append([
                escenario, formato_proporcion(int((ext.conf_BPFO >= tau).sum()), len(ext)), formato_proporcion(int((inte.conf_BPFI >= tau).sum()), len(inte)),
                formato_proporcion(int((san[columnas_rod] >= tau).any(axis=1).sum()), len(san)),
                int((sub.origen_velocidad == "estimada").sum()), int((sub.origen_velocidad == "nominal").sum()),
            ])
        salida.append(f"\nUmbral τ = {tau:.2f}:")
        salida.append(tabla_markdown(["escenario", "exterior: BPFO ≥ τ", "interior: BPFI ≥ τ", "sano: falsa alarma", "ventanas con velocidad estimada", "con velocidad nominal"], filas))
    return "\n".join(salida)


def resumen_mfpt_rodamientos(df):
    salida = []
    for escenario in ("velocidad_declarada",):
        sub = df[df.escenario == escenario]
        salida.append(f"\n### MFPT — rodamientos — escenario {escenario} ({sub.archivo.nunique()} archivos, {len(sub)} ventanas de 2 s)")
        filas = []
        for tau in UMBRALES:
            fila = [f"{tau:.2f}"]
            ext, inte, san = sub[sub.clase_real == "pista_exterior"], sub[sub.clase_real == "pista_interior"], sub[sub.clase_real == "sano"]
            fila.append(formato_proporcion(int((ext.conf_BPFO >= tau).sum()), len(ext)))
            fila.append(formato_proporcion(int((inte.conf_BPFI >= tau).sum()), len(inte)))
            alarma_sano = (san[[f"conf_{k}" for k in FALLAS_RODAMIENTO]] >= tau).any(axis=1)
            fila.append(formato_proporcion(int(alarma_sano.sum()), len(san)))
            solo_ext = ((ext[[f"conf_{k}" for k in FALLAS_RODAMIENTO]] >= tau).sum(axis=1) == 1) & (ext.conf_BPFO >= tau)
            solo_int = ((inte[[f"conf_{k}" for k in FALLAS_RODAMIENTO]] >= tau).sum(axis=1) == 1) & (inte.conf_BPFI >= tau)
            fila.append(formato_proporcion(int(solo_ext.sum()), len(ext)))
            fila.append(formato_proporcion(int(solo_int.sum()), len(inte)))
            filas.append(fila)
        salida.append(tabla_markdown(
            ["umbral τ", "pista exterior: BPFO ≥ τ (sensibilidad)", "pista interior: BPFI ≥ τ (sensibilidad)",
             "sano: alguna hipótesis de rodamiento ≥ τ (falsa alarma)", "exterior: BPFO como única hipótesis ≥ τ", "interior: BPFI como única hipótesis ≥ τ"], filas))

        for tau in (0.50, 0.70):
            salida.append(f"\nMatriz de confusión (ventanas con la hipótesis ≥ {tau:.2f}), fila = estado real:")
            filas = []
            for clase in ("sano", "pista_exterior", "pista_interior"):
                s = sub[sub.clase_real == clase]
                columnas = [formato_proporcion(int((s[f"conf_{k}"] >= tau).sum()), len(s)) for k in FALLAS_RODAMIENTO]
                ninguna = (s[[f"conf_{k}" for k in FALLAS_RODAMIENTO]] < tau).all(axis=1)
                filas.append([clase, len(s)] + columnas + [formato_proporcion(int(ninguna.sum()), len(s))])
            salida.append(tabla_markdown(["real", "ventanas", "BPFO", "BPFI", "BSF", "FTF", "ninguna"], filas))

        salida.append("\nSensibilidad por archivo (BPFO ≥ 0.70 para exterior, BPFI ≥ 0.70 para interior; falsa alarma en sano a ≥ 0.70):")
        filas = []
        for (archivo, clase), g in sub.groupby(["archivo", "clase_real"]):
            if clase == "sano":
                detalle = f"alarma en {int((g[[f'conf_{k}' for k in FALLAS_RODAMIENTO]] >= 0.7).any(axis=1).sum())}/{len(g)} ventanas"
            else:
                col = "conf_BPFO" if clase == "pista_exterior" else "conf_BPFI"
                detalle = f"{col[5:]} ≥ 0.70 en {int((g[col] >= 0.7).sum())}/{len(g)} ventanas (máx {g[col].max():.2f})"
            filas.append([archivo, clase, detalle])
        salida.append(tabla_markdown(["archivo", "real", "resultado"], filas))
    return "\n".join(salida)


def resumen_mfpt_velocidad(df):
    salida = ["\n### MFPT — estimación de velocidad con la nominal equivocada (D-057/D-058)"]
    filas = []
    for p, g in df.groupby("error_nominal_pct"):
        recuperada = (g.error_resuelta_pct.abs() <= 0.5)
        filas.append([f"{p:+d} %", len(g), formato_proporcion(int(recuperada.sum()), len(g)),
                      f"{g.error_resuelta_pct.abs().median():.2f} %", f"{g.error_resuelta_pct.abs().max():.1f} %",
                      formato_proporcion(int(g.aviso_inconsistencia.sum()), len(g)), int((g.origen == "estimada").sum())])
    salida.append(tabla_markdown(
        ["nominal equivocada", "ventanas", "velocidad recuperada (error ≤ 0.5 %)", "error mediano", "error máximo", "aviso de inconsistencia", "ventanas con velocidad 'estimada'"], filas))
    return "\n".join(salida)


def resumen_ottawa(df):
    salida = []
    for escenario in ("sin_linea_base", "con_linea_base"):
        sub = df[df.escenario == escenario]
        salida.append(f"\n### Ottawa — reglas de rotor — escenario {escenario} ({len(sub)} ventanas de 2 s; 4 velocidades × 2 cargas)")
        for tau in (0.50, 0.70, 0.90):
            if escenario == "sin_linea_base" and tau > 0.5:
                continue  # sin referencia la confianza de estas reglas esta acotada a 0.50
            salida.append(f"\nVentanas con la hipótesis ≥ {tau:.2f}, fila = estado real:")
            filas = []
            for clase in CLASES_OTTAWA:
                s = sub[sub.clase_real == clase]
                desal = (s[["conf_desal_paralela", "conf_desal_angular"]] >= tau).any(axis=1)
                alguna = (s[["conf_desbalanceo", "conf_desal_paralela", "conf_desal_angular"]] >= tau).any(axis=1)
                filas.append([f"{clase} ({NOMBRES_CLASE_OTTAWA[clase]})", len(s), formato_proporcion(int((s.conf_desbalanceo >= tau).sum()), len(s)),
                              formato_proporcion(int(desal.sum()), len(s)), formato_proporcion(int(alguna.sum()), len(s))])
            salida.append(tabla_markdown(["real", "ventanas", "desbalanceo", "desalineación (paralela o angular)", "alguna de las tres"], filas))

    sub = df[df.escenario == "con_linea_base"]
    salida.append("\n### Ottawa — indicador de cambio respecto de la línea base (sano, misma velocidad y carga)")
    filas = []
    for clase in CLASES_OTTAWA:
        s = sub[sub.clase_real == clase]
        r = s.cambio_razon.astype(float)
        filas.append([f"{clase} ({NOMBRES_CLASE_OTTAWA[clase]})", len(s),
                      formato_proporcion(int(s.cambio_nivel.isin(["elevado", "muy_elevado"]).sum()), len(s)),
                      formato_proporcion(int((s.cambio_nivel == "muy_elevado").sum()), len(s)),
                      f"{r.median():.2f} ({r.min():.2f}–{r.max():.2f})"])
    salida.append(tabla_markdown(["real", "ventanas", "nivel ≥ elevado (≥ 1.25×)", "muy elevado (≥ 2×)", "razón: mediana (mín–máx)"], filas))
    salida.append("\nPor velocidad y carga (fallas = las 7 clases con falla; razón mediana y ventanas 'muy elevado'):")
    filas = []
    fallas = sub[sub.clase_real != "H_H"]
    for (hz, carga), g in fallas.groupby(["velocidad_hz", "carga"]):
        filas.append([f"{hz} Hz", "con carga" if carga else "sin carga", len(g), f"{g.cambio_razon.astype(float).median():.2f}",
                      formato_proporcion(int((g.cambio_nivel == "muy_elevado").sum()), len(g))])
    salida.append(tabla_markdown(["velocidad", "carga", "ventanas con falla", "razón mediana", "muy elevado"], filas))
    return "\n".join(salida)


def mayoria(serie_booleana):
    """True si mas de la mitad de las ventanas de la unidad cumplen la condicion."""
    return bool(serie_booleana.sum() * 2 > len(serie_booleana))


def resumen_por_unidad_mfpt(df):
    """La unidad independiente es el ARCHIVO (sus ventanas son casi replicas): n = 20."""
    sub = df[df.escenario == "velocidad_declarada"]
    cols = [f"conf_{k}" for k in FALLAS_RODAMIENTO]
    salida = ["\n### MFPT — por ARCHIVO (unidad independiente; un archivo es positivo si más de la mitad de sus ventanas lo son)"]
    filas = []
    for tau in UMBRALES[1:]:
        fila = [f"{tau:.2f}"]
        for clase, col in (("pista_exterior", "conf_BPFO"), ("pista_interior", "conf_BPFI")):
            g = sub[sub.clase_real == clase].groupby("archivo")
            positivos = sum(mayoria(x[col] >= tau) for _, x in g)
            fila.append(formato_proporcion(positivos, g.ngroups))
        g = sub[sub.clase_real == "sano"].groupby("archivo")
        fila.append(formato_proporcion(sum(mayoria((x[cols] >= tau).any(axis=1)) for _, x in g), g.ngroups))
        for clase, col in (("pista_exterior", "conf_BPFI"), ("pista_interior", "conf_BPFO")):
            g = sub[sub.clase_real == clase].groupby("archivo")
            fila.append(formato_proporcion(sum(mayoria(x[col] >= tau) for _, x in g), g.ngroups))
        filas.append(fila)
    salida.append(tabla_markdown(
        ["umbral τ", "exterior: BPFO", "interior: BPFI", "sano: falsa alarma", "exterior con BPFI también (confusión)", "interior con BPFO también (confusión)"], filas))

    salida.append("\nHipótesis principal de rodamiento por ventana (la de mayor confianza; empate = dos o más con la misma confianza máxima):")
    filas = []
    for clase, col in (("pista_exterior", "conf_BPFO"), ("pista_interior", "conf_BPFI")):
        s = sub[sub.clase_real == clase]
        maximo = s[cols].max(axis=1)
        unica = (s[cols].eq(maximo, axis=0).sum(axis=1) == 1)
        correcta = s[col] == maximo
        filas.append([clase, len(s), formato_proporcion(int((correcta & unica).sum()), len(s)),
                      formato_proporcion(int((correcta & ~unica).sum()), len(s)), formato_proporcion(int((~correcta).sum()), len(s))])
    salida.append(tabla_markdown(["real", "ventanas", "principal = correcta (sin empate)", "correcta empatada con otra", "principal incorrecta"], filas))
    return "\n".join(salida)


def resumen_por_condicion_ottawa(df):
    """La unidad independiente es la CONDICION (velocidad × carga): n = 8 por clase."""
    salida = []
    for escenario, taus in (("sin_linea_base", (0.50,)), ("con_linea_base", (0.50, 0.90))):
        sub = df[df.escenario == escenario]
        for tau in taus:
            salida.append(f"\n### Ottawa — por CONDICIÓN (velocidad × carga; positiva si más de la mitad de sus ventanas) — {escenario}, hipótesis ≥ {tau:.2f}")
            filas = []
            for clase in CLASES_OTTAWA:
                g = sub[sub.clase_real == clase].groupby(["velocidad_hz", "carga"])
                desb = sum(mayoria(x.conf_desbalanceo >= tau) for _, x in g)
                desal = sum(mayoria((x[["conf_desal_paralela", "conf_desal_angular"]] >= tau).any(axis=1)) for _, x in g)
                filas.append([f"{clase} ({NOMBRES_CLASE_OTTAWA[clase]})", g.ngroups, formato_proporcion(desb, g.ngroups), formato_proporcion(desal, g.ngroups)])
            salida.append(tabla_markdown(["real", "condiciones", "desbalanceo", "desalineación"], filas))

    sub = df[df.escenario == "con_linea_base"]
    salida.append("\n### Ottawa — confianza mediana por condición, con línea base (R_U = desbalanceo real; R_M = desalineación real; H_H = sano)")
    filas = []
    for clase in ("R_U", "R_M", "H_H"):
        for (hz, carga), g in sub[sub.clase_real == clase].groupby(["velocidad_hz", "carga"]):
            filas.append([clase, f"{hz} Hz", "con carga" if carga else "sin carga", f"{g.conf_desbalanceo.median():.2f}",
                          f"{g.conf_desal_paralela.median():.2f}", f"{g.conf_desal_angular.median():.2f}", g.origen_velocidad.mode().iat[0]])
    salida.append(tabla_markdown(["real", "velocidad", "carga", "desbalanceo", "desal. paralela", "desal. angular", "velocidad usada"], filas))

    salida.append("\nHipótesis principal de rotor con línea base, por ventana (entre desbalanceo / desal. paralela / desal. angular; empate = misma confianza máxima):")
    filas = []
    cols = ["conf_desbalanceo", "conf_desal_paralela", "conf_desal_angular"]
    for clase, esperado in (("R_U", ["conf_desbalanceo"]), ("R_M", ["conf_desal_paralela", "conf_desal_angular"])):
        s = sub[sub.clase_real == clase]
        maximo = s[cols].max(axis=1)
        ganadoras = s[cols].eq(maximo, axis=0)
        unica = ganadoras.sum(axis=1) == 1
        correcta = ganadoras[esperado].any(axis=1) & (maximo > 0)
        filas.append([f"{clase} ({NOMBRES_CLASE_OTTAWA[clase]})", len(s), formato_proporcion(int((correcta & unica).sum()), len(s)),
                      formato_proporcion(int((correcta & ~unica).sum()), len(s)), formato_proporcion(int((~correcta).sum()), len(s))])
    salida.append(tabla_markdown(["real", "ventanas", "principal correcta (sin empate)", "correcta empatada con otra", "principal incorrecta o ninguna"], filas))
    return "\n".join(salida)


def resumen_cwru(df):
    filas = [[int(f.ventana), f.hipotesis or "(ninguna)"] for f in df.itertuples()]
    return "\n### CWRU — caso único (135.mat, columna DE, 48 kHz indicada a mano, 1796 r/min declarados)\n" + tabla_markdown(["ventana de 2 s", "hipótesis"], filas)


# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--salida", default=str(RUTA_PROYECTO / "validacion" / "resultados"), help="carpeta donde se guardan los CSV y el resumen")
    parser.add_argument("--experimentos", nargs="+", default=["mfpt_rodamientos", "mfpt_velocidad", "ottawa_rotor", "cwru_caso"],
                        choices=["mfpt_rodamientos", "mfpt_velocidad", "ottawa_rotor", "cwru_caso"])
    parser.add_argument("--mfpt", default=MFPT_POR_DEFECTO)
    parser.add_argument("--ottawa", default=OTTAWA_POR_DEFECTO)
    parser.add_argument("--cwru", default=CWRU_POR_DEFECTO)
    parser.add_argument("--desde-csv", action="store_true",
                        help="no recalcula: rehace el resumen a partir de los CSV que ya hay en --salida")
    argumentos = parser.parse_args()

    salida = Path(argumentos.salida)
    salida.mkdir(parents=True, exist_ok=True)

    if argumentos.desde_csv:
        textos = []
        if (salida / "mfpt_rodamientos.csv").exists():
            df = pd.read_csv(salida / "mfpt_rodamientos.csv")
            textos += [resumen_mfpt_rodamientos(df), resumen_por_unidad_mfpt(df), resumen_mfpt_nominal_erroneo(df)]
        if (salida / "mfpt_velocidad.csv").exists():
            textos.append(resumen_mfpt_velocidad(pd.read_csv(salida / "mfpt_velocidad.csv")))
        if (salida / "ottawa_rotor.csv").exists():
            df = pd.read_csv(salida / "ottawa_rotor.csv")
            textos += [resumen_ottawa(df), resumen_por_condicion_ottawa(df)]
        if (salida / "cwru_caso.csv").exists():
            textos.append(resumen_cwru(pd.read_csv(salida / "cwru_caso.csv").fillna("")))
        texto = "\n".join(textos)
        (salida / "resumen.txt").write_text(texto, encoding="utf-8")
        print(texto)
        return
    resumenes, metadatos = [], {
        "fecha": datetime.now().isoformat(timespec="seconds"), "python": platform.python_version(), "numpy": np.__version__, "pandas": pd.__version__,
        "ventana_s": DURACION_VENTANA_S, "umbrales": list(UMBRALES), "experimentos": argumentos.experimentos,
    }

    if {"mfpt_rodamientos", "mfpt_velocidad"} & set(argumentos.experimentos):
        archivos, excluidos, duplicados = cargar_mfpt(argumentos.mfpt)
        metadatos["mfpt"] = {"archivos": [a["archivo"] for a in archivos], "excluidos": excluidos, "duplicados_omitidos": duplicados}
        resumenes.append(
            f"MFPT: {len(archivos)} archivos usados; excluidos por no tener estado documentado: {', '.join(excluidos) or 'ninguno'}; "
            f"omitidos por ser copia exacta de otro: {', '.join(duplicados) or 'ninguno'}"
        )
        if "mfpt_rodamientos" in argumentos.experimentos:
            inicio = time.time()
            df = experimento_mfpt_rodamientos(archivos)
            df.to_csv(salida / "mfpt_rodamientos.csv", index=False)
            resumenes.append(resumen_mfpt_rodamientos(df))
            resumenes.append(resumen_por_unidad_mfpt(df))
            resumenes.append(resumen_mfpt_nominal_erroneo(df))
            print(f"mfpt_rodamientos: {len(df)} filas en {time.time() - inicio:.0f} s", flush=True)
        if "mfpt_velocidad" in argumentos.experimentos:
            inicio = time.time()
            df = experimento_mfpt_velocidad(archivos)
            df.to_csv(salida / "mfpt_velocidad.csv", index=False)
            resumenes.append(resumen_mfpt_velocidad(df))
            print(f"mfpt_velocidad: {len(df)} filas en {time.time() - inicio:.0f} s", flush=True)

    if "ottawa_rotor" in argumentos.experimentos:
        inicio = time.time()
        df = experimento_ottawa(cargar_ottawa(argumentos.ottawa))
        df.to_csv(salida / "ottawa_rotor.csv", index=False)
        resumenes.append(resumen_ottawa(df))
        resumenes.append(resumen_por_condicion_ottawa(df))
        print(f"ottawa_rotor: {len(df)} filas en {time.time() - inicio:.0f} s", flush=True)

    if "cwru_caso" in argumentos.experimentos:
        df = experimento_cwru(argumentos.cwru)
        df.to_csv(salida / "cwru_caso.csv", index=False)
        resumenes.append(resumen_cwru(df))

    (salida / "metadatos.json").write_text(json.dumps(metadatos, indent=2, ensure_ascii=False), encoding="utf-8")
    texto = "\n".join(resumenes)
    (salida / "resumen.txt").write_text(texto, encoding="utf-8")
    print(texto)


if __name__ == "__main__":
    main()
