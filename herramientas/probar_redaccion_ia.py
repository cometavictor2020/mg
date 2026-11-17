"""
Prueba de la redaccion de reportes con IA (backend/procesamiento/redaccion_ia.py) SIN llamar a OpenAI: la respuesta
del modelo se reemplaza por textos fijos. No usa la clave, no gasta creditos y no escribe nada en la base de datos.

Comprueba:
    - el estado (que falta para poder usar la IA);
    - que los datos enviados no traen los nombres del equipo ni de la planta ni señales;
    - la comprobacion de cifras (acepta las del diagnostico, rechaza las inventadas);
    - que un fallo de la IA se informa con un mensaje claro y no se propaga;
    - que el PDF con IA tiene UNA pagina mas que el PDF sin IA, aunque el texto sea larguisimo.

Uso:
    cd C:\\Users\\comet\\Documents\\mg
    .\\venv\\Scripts\\python.exe herramientas\\probar_redaccion_ia.py
"""

import json
import os
import re
import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd

RUTA_PROYECTO = Path(__file__).parent.parent
sys.path.insert(0, str(RUTA_PROYECTO))
sys.path.insert(0, str(Path(__file__).parent))

import probar_rodamientos_sinteticos as ps  # noqa: E402
from backend.procesamiento import redaccion_ia  # noqa: E402
from backend.procesamiento.diagnostico import diagnosticar_sensor  # noqa: E402
from backend.procesamiento.frecuencia import calcular_fft  # noqa: E402
from backend.procesamiento.pdf_reporte import generar_pdf_reporte  # noqa: E402

fallos = []


def verificar(nombre, condicion, detalle=""):
    print(("  ok     " if condicion else "  FALLA  ") + nombre + (f" — {detalle}" if detalle and not condicion else ""))
    if not condicion:
        fallos.append(nombre)


def paginas(pdf_bytes):
    return len(re.findall(rb"/Type\s*/Page(?!s)", pdf_bytes))


# --- Reporte de ejemplo con el motor real (falla de pista exterior simulada) ---------------------------------------
rodamiento = list(ps.RODAMIENTOS.values())[1]
rng = np.random.default_rng(3)
señal = ps.senal(rng, rodamiento, 25.0, ["BPFO"], 4.0)
datos_crudos = pd.DataFrame({"vibracion_x": señal})
fft = calcular_fft(datos_crudos, ps.FRECUENCIA_MUESTREO, 300)
diagnostico = diagnosticar_sensor(fft, 1500, datos_crudos=datos_crudos, frecuencia_muestreo=ps.FRECUENCIA_MUESTREO, rodamiento=rodamiento)
diagnostico.pop("datos_grafico_rodamiento", None)
reporte = {
    "equipo": {"nombre": "Motor Secreto 7", "tipo": "Motor eléctrico", "planta": "Planta Reservada", "rpm_nominal": 1500},
    "fecha_generacion": "2026-11-03 12:00",
    "sensores": [{"sensor_id": 1, "nombre_tipo": "Acelerómetro", "tiene_medicion": True, "diagnostico": diagnostico}],
}
hipotesis = diagnostico["hipotesis"]
print(f"Reporte de ejemplo: {[(h['falla'], round(h['confianza'] * 100)) for h in hipotesis]}")

CONFIG = {"habilitado": True, "modelo": "modelo-de-prueba", "enviar_nombres": False, "maximo_observaciones": 5,
          "cifras_permitidas": [20816, 13373, 1, 2, 3]}
confianza = round(hipotesis[0]["confianza"] * 100)
falla = hipotesis[0]["falla"].replace("rodamiento_", "").replace("_", " ")

print("\n1. Estado")
clave_original = os.environ.pop("OPENAI_API_KEY", None)
estado = redaccion_ia.estado_ia()
verificar("sin clave: no está listo y dice por qué", (not estado["listo"]) and bool(estado["motivo"]), str(estado))
os.environ["OPENAI_API_KEY"] = "clave-falsa-solo-para-la-prueba"
estado = redaccion_ia.estado_ia()
verificar("con clave y modelo configurados: listo (el paquete openai está instalado)", estado["listo"] or "paquete" in (estado["motivo"] or ""), str(estado))
if clave_original is not None:
    os.environ["OPENAI_API_KEY"] = clave_original
else:
    os.environ.pop("OPENAI_API_KEY", None)

print("\n2. Datos que se envían")
datos = redaccion_ia.preparar_datos(reporte, enviar_nombres=False)
texto_datos = json.dumps(datos, ensure_ascii=False)
verificar("no trae el nombre del equipo", "Secreto" not in texto_datos)
verificar("no trae el nombre de la planta", "Reservada" not in texto_datos)
verificar("no trae señales ni espectros", "datos_fft" not in texto_datos and "vibracion_x" not in texto_datos)
verificar("trae las hipótesis con su confianza", f'"confianza_pct": {confianza}' in texto_datos)
verificar("con enviar_nombres sí trae el nombre", "Motor Secreto 7" in json.dumps(redaccion_ia.preparar_datos(reporte, enviar_nombres=True), ensure_ascii=False))

print("\n3. Comprobación de cifras")
verificar("acepta la confianza del diagnóstico", redaccion_ia.cifras_no_verificadas(f"Hallazgo con {confianza} % de confianza", datos, [1, 2, 3]) == [])
verificar("acepta 1x, 2x y la norma ISO 20816-3", redaccion_ia.cifras_no_verificadas("Línea 1x y 2x; ISO 20816-3", datos, [20816, 13373, 1, 2, 3]) == [])
verificar("rechaza una cifra inventada", redaccion_ia.cifras_no_verificadas("La vibración alcanza 7,35 mm/s", datos, [1, 2, 3]) == ["7,35"])


def respuesta_buena(mensajes, config):
    return json.dumps({
        "resumen": f"Se identificó una posible falla de {falla} con una confianza de {confianza} %, que requiere confirmación con inspección física.",
        "observaciones": ["La confianza es un puntaje de evidencia, no una probabilidad de falla."],
    })


print("\n4. Flujo completo con IA simulada")
resultado = redaccion_ia.redactar_resumen(reporte, CONFIG, llamar_modelo=respuesta_buena)
verificar("devuelve resumen, observaciones, modelo y fecha", set(resultado) == {"resumen", "observaciones", "modelo", "fecha"})
verificar("rotula el modelo usado", resultado["modelo"] == "modelo-de-prueba")

mensajes_recibidos = {}


def espia(mensajes, config):
    mensajes_recibidos["m"] = mensajes
    return respuesta_buena(mensajes, config)


redaccion_ia.redactar_resumen(reporte, CONFIG, llamar_modelo=espia)
verificar("el mensaje a la IA no contiene los nombres reales", "Secreto" not in json.dumps(mensajes_recibidos["m"], ensure_ascii=False))
verificar("las instrucciones prohíben inventar cifras", "No cambies ni redondees" in mensajes_recibidos["m"][0]["content"])


def respuesta_con_cifra_inventada(mensajes, config):
    return json.dumps({"resumen": "La vibración subió a 9,87 mm/s.", "observaciones": []})


def respuesta_no_json(mensajes, config):
    return "esto no es JSON"


def respuesta_que_falla(mensajes, config):
    raise redaccion_ia.ErrorIA("OpenAI rechazó la solicitud por límite de uso o falta de créditos.")


for nombre, funcion, esperado in (
    ("descarta el texto con una cifra inventada", respuesta_con_cifra_inventada, "cifras que no están"),
    ("informa una respuesta que no es JSON", respuesta_no_json, "formato esperado"),
    ("informa un fallo de la IA con su mensaje", respuesta_que_falla, "créditos"),
):
    try:
        redaccion_ia.redactar_resumen(reporte, CONFIG, llamar_modelo=funcion)
        verificar(nombre, False, "no lanzó ErrorIA")
    except redaccion_ia.ErrorIA as error:
        verificar(nombre, esperado in str(error), str(error))

try:
    redaccion_ia.redactar_resumen(reporte, {**CONFIG, "modelo": ""}, llamar_modelo=respuesta_buena)
    verificar("sin modelo configurado lanza ErrorIA", False)
except redaccion_ia.ErrorIA as error:
    verificar("sin modelo configurado lanza ErrorIA", "modelo" in str(error))

print("\n5. PDF: el reporte de siempre + UNA página")
pdf_sin_ia = generar_pdf_reporte(reporte)
pdf_con_ia = generar_pdf_reporte({**reporte, "resumen_ia": resultado})
verificar("con IA tiene una página más", paginas(pdf_con_ia) == paginas(pdf_sin_ia) + 1, f"{paginas(pdf_sin_ia)} → {paginas(pdf_con_ia)}")
larguisimo = {**resultado, "resumen": " ".join(["Texto de relleno muy largo para probar que todo cabe en una sola página."] * 120),
              "observaciones": ["Observación de relleno larga para probar la página única. " * 6] * 5}
verificar("un texto larguísimo sigue en UNA sola página", paginas(generar_pdf_reporte({**reporte, "resumen_ia": larguisimo})) == paginas(pdf_sin_ia) + 1)
salida = Path(os.environ.get("TEMP", ".")) / "prueba_reporte_con_ia.pdf"
salida.write_bytes(pdf_con_ia)
print(f"  PDF de ejemplo guardado en {salida}")

print()
if fallos:
    print(f"FALLARON {len(fallos)} comprobaciones: {fallos}")
    sys.exit(1)
print("Todas las comprobaciones pasaron.")
