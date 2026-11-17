"""
Redaccion de un resumen del reporte con IA (OpenAI) y observaciones sobre el.

Principios (ver "Ideas futuras" en PROYECTO.md):
    - La IA REDACTA y COMENTA; nunca decide. El diagnostico, las confianzas y las cifras son los del motor de reglas.
    - Solo se le envian los resultados del diagnostico (no las señales). Por defecto, sin los nombres del equipo ni de
      la planta (config/ia.yaml: enviar_nombres).
    - Todo numero que aparezca en el texto de la IA debe estar en los datos enviados; si no, el texto se descarta.
    - Un fallo de la IA (sin clave, sin creditos, sin conexion, modelo inexistente) nunca impide generar el reporte:
      se lanza ErrorIA con un mensaje claro y quien llama sigue sin la pagina de IA.

Este modulo no conoce la base de datos ni HTTP: recibe el reporte ya calculado y devuelve texto.
La clave OPENAI_API_KEY se lee de .env; la configuracion no secreta, de config/ia.yaml.
"""

import json
import os
import re
from datetime import datetime
from pathlib import Path

import yaml
from dotenv import load_dotenv

RUTA_PROYECTO = Path(__file__).parent.parent.parent
RUTA_CONFIGURACION = RUTA_PROYECTO / "config" / "ia.yaml"

load_dotenv(RUTA_PROYECTO / ".env")

PATRON_NUMERO = re.compile(r"\d+(?:[.,]\d+)?")


class ErrorIA(Exception):
    """La redaccion con IA no se pudo hacer; el mensaje se muestra al usuario."""


def cargar_configuracion_ia():
    try:
        with open(RUTA_CONFIGURACION, encoding="utf-8") as archivo:
            return (yaml.safe_load(archivo) or {}).get("ia") or {}
    except FileNotFoundError:
        return {}


def estado_ia():
    """
    Si la redaccion con IA se puede usar ahora y, si no, por que. Lo consulta la pantalla de Reportes para
    habilitar o no el interruptor y para informar al usuario que se enviara.
    """
    config = cargar_configuracion_ia()
    estado = {
        "listo": False,
        "motivo": None,
        "modelo": config.get("modelo") or None,
        "enviar_nombres": bool(config.get("enviar_nombres", False)),
    }
    if not config.get("habilitado", False):
        estado["motivo"] = "La redacción con IA está deshabilitada en config/ia.yaml."
    elif config.get("proveedor", "openai") != "openai":
        estado["motivo"] = f"Proveedor de IA no soportado: {config.get('proveedor')}."
    elif not config.get("modelo"):
        estado["motivo"] = "Falta el modelo en config/ia.yaml."
    elif not os.getenv("OPENAI_API_KEY"):
        estado["motivo"] = "Falta la clave OPENAI_API_KEY en el archivo .env."
    else:
        try:
            import openai  # noqa: F401
        except ImportError:
            estado["motivo"] = "Falta instalar el paquete openai (pip install openai)."
        else:
            estado["listo"] = True
    return estado


# ---------------------------------------------------------------------------
# Datos que se envian
# ---------------------------------------------------------------------------

def preparar_datos(reporte, enviar_nombres=False):
    """
    Resultados del diagnostico que se le entregan a la IA: solo lo que el motor ya calculo, sin las señales, sin los
    espectros ni los graficos. Sin nombres del equipo ni de la planta, salvo que la configuracion lo permita.
    """
    equipo = reporte["equipo"]
    datos = {
        "equipo": {
            "nombre": equipo.get("nombre") if enviar_nombres else "Equipo",
            "tipo": equipo.get("tipo"),
            "planta": equipo.get("planta") if enviar_nombres else "Planta",
            "rpm_nominal": equipo.get("rpm_nominal"),
        },
        "sensores": [],
    }
    for sensor in reporte["sensores"]:
        if not sensor.get("tiene_medicion"):
            datos["sensores"].append({"sensor": sensor["nombre_tipo"], "tiene_medicion": False})
            continue
        d = sensor["diagnostico"]
        iso = d.get("severidad_iso") or {}
        cambio = d.get("cambio_linea_base") or {}
        calidad = d.get("calidad_medicion") or {}
        velocidad = d.get("velocidad") or {}
        verificacion = d.get("verificacion_velocidad") or {}
        datos["sensores"].append(
            {
                "sensor": sensor["nombre_tipo"],
                "tiene_medicion": True,
                "hipotesis": [
                    {
                        "falla": h["falla"].replace("_", " "),
                        "confianza_pct": round(h["confianza"] * 100),
                        "evidencias": h["evidencias"],
                        "recomendaciones": [r.replace("_", " ") for r in (h.get("recomendacion") or [])],
                    }
                    for h in d.get("hipotesis", [])
                ],
                "velocidad_de_giro": {
                    "rpm": round(velocidad["rpm"]) if velocidad.get("rpm") else None,
                    "origen": velocidad.get("origen"),
                    "posible_inconsistencia": bool(verificacion.get("inconsistente")),
                },
                "linea_base_disponible": bool((d.get("linea_base") or {}).get("disponible")),
                "severidad_iso_20816_3": (
                    {
                        "zona": iso.get("zona"),
                        "severidad": iso.get("severidad"),
                        "velocidad_rms_mm_s": round(iso["velocidad_rms_mm_s"], 2),
                        "accion_recomendada": (iso.get("accion_recomendada") or "").replace("_", " "),
                    }
                    if iso.get("aplicable")
                    else {"no_evaluable": iso.get("motivo_no_aplicable")}
                ),
                "cambio_respecto_de_la_linea_base": (
                    {
                        "nivel": (cambio.get("nivel") or "").replace("_", " "),
                        "veces": cambio.get("razon"),
                        "velocidad_rms_actual_mm_s": round(cambio["velocidad_rms_actual_mm_s"], 2),
                        "velocidad_rms_referencia_mm_s": round(cambio["velocidad_rms_referencia_mm_s"], 2),
                    }
                    if cambio.get("aplicable")
                    else {"no_evaluable": cambio.get("motivo_no_aplicable")}
                ),
                "calidad_de_la_medicion": {
                    "estado": (calidad.get("estado") or "").replace("_", " "),
                    "mensajes": (calidad.get("criticas") or []) + (calidad.get("advertencias") or []),
                },
                "limitaciones": d.get("limitaciones", []),
            }
        )
    return datos


# ---------------------------------------------------------------------------
# Comprobacion de cifras
# ---------------------------------------------------------------------------

def _a_numero(texto):
    return float(texto.replace(",", "."))


def _numeros_de(valor, destino):
    """Todos los numeros que aparecen en `valor` (numeros y texto), tal cual y sus porcentajes."""
    if isinstance(valor, bool) or valor is None:
        return
    if isinstance(valor, (int, float)):
        destino.add(float(valor))
    elif isinstance(valor, str):
        for coincidencia in PATRON_NUMERO.findall(valor):
            destino.add(_a_numero(coincidencia))
    elif isinstance(valor, dict):
        for v in valor.values():
            _numeros_de(v, destino)
    elif isinstance(valor, (list, tuple)):
        for v in valor:
            _numeros_de(v, destino)


def cifras_no_verificadas(texto, datos, cifras_permitidas=()):
    """
    Cifras del texto que NO se pueden rastrear hasta los datos enviados. Una cifra se acepta si coincide (salvo
    redondeo) con algun numero de los datos, con ese numero como porcentaje, o si esta en la lista de permitidas.
    """
    permitidas = {float(c) for c in cifras_permitidas}
    _numeros_de(datos, permitidas)
    permitidas |= {v * 100 for v in list(permitidas) if 0 < abs(v) <= 1}
    no_verificadas = []
    for coincidencia in PATRON_NUMERO.findall(texto):
        x = _a_numero(coincidencia)
        if not any(abs(x - a) <= max(0.051, 0.01 * abs(a)) for a in permitidas):
            no_verificadas.append(coincidencia)
    return no_verificadas


# ---------------------------------------------------------------------------
# Llamada al modelo
# ---------------------------------------------------------------------------

INSTRUCCIONES = """Eres un redactor técnico de mantenimiento por condición. Recibes, en formato JSON, el resultado de un
reporte de diagnóstico de vibraciones calculado por un sistema de reglas. Escribe en español formal e impersonal.

Reglas estrictas:
- Usa SOLO la información del JSON. No inventes datos, causas, fechas, costos ni recomendaciones que no estén allí.
- No cambies ni redondees distinto las cifras, y no agregues cifras que no estén en el JSON.
- La confianza de cada hipótesis es un puntaje de la evidencia encontrada por las reglas, no la probabilidad de que
  falle el equipo. Dilo si mencionas porcentajes.
- Toda hipótesis requiere confirmación con una inspección física; no ordenes detener ni intervenir el equipo.
- Si hay limitaciones del diagnóstico (por ejemplo, confianza acotada por falta de línea base), menciónalas.

Responde únicamente con un objeto JSON con dos campos:
- "resumen": un texto de a lo más {palabras_resumen} palabras (uno o dos párrafos) con el estado del equipo, el hallazgo
  principal con su evidencia, la severidad y el cambio respecto de la línea base si existen, y la inspección sugerida.
- "observaciones": una lista de a lo más {max_observaciones} advertencias o comentarios breves (cada una de a lo más
  {palabras_observacion} palabras) sobre aspectos del reporte que el analista debería revisar: hipótesis simultáneas
  con confianza máxima, confianza limitada por falta de línea base, unidad o velocidad no declarada, posible
  inconsistencia de velocidad, calidad de medición con reservas, severidad no evaluable u otros. Si no hay nada que
  advertir, devuelve una lista vacía."""


def _mensajes(datos, config):
    instrucciones = INSTRUCCIONES.format(
        palabras_resumen=config.get("maximo_palabras_resumen", 200),
        max_observaciones=config.get("maximo_observaciones", 5),
        palabras_observacion=config.get("maximo_palabras_observacion", 35),
    )
    return [
        {"role": "system", "content": instrucciones},
        {"role": "user", "content": json.dumps(datos, ensure_ascii=False)},
    ]


def _llamar_modelo(mensajes, config):
    """Llamada real a OpenAI (Chat Completions, respuesta JSON). Devuelve el texto de la respuesta."""
    try:
        import openai
    except ImportError as error:
        raise ErrorIA("Falta instalar el paquete openai (pip install openai).") from error

    clave = os.getenv("OPENAI_API_KEY")
    if not clave:
        raise ErrorIA("Falta la clave OPENAI_API_KEY en el archivo .env.")

    cliente = openai.OpenAI(api_key=clave, timeout=float(config.get("tiempo_maximo_segundos", 60)))
    try:
        respuesta = cliente.chat.completions.create(
            model=config["modelo"],
            messages=mensajes,
            response_format={"type": "json_object"},
            store=False,  # no se guarda la conversacion en la cuenta de OpenAI
        )
    except openai.AuthenticationError as error:
        raise ErrorIA("OpenAI rechazó la clave OPENAI_API_KEY (inválida o revocada).") from error
    except openai.PermissionDeniedError as error:
        raise ErrorIA("La cuenta de OpenAI no tiene permiso para usar este modelo.") from error
    except openai.NotFoundError as error:
        raise ErrorIA(f"El modelo «{config['modelo']}» no existe o no está disponible en tu cuenta (config/ia.yaml).") from error
    except openai.RateLimitError as error:
        raise ErrorIA("OpenAI rechazó la solicitud por límite de uso o falta de créditos.") from error
    except openai.APITimeoutError as error:
        raise ErrorIA("OpenAI no respondió a tiempo.") from error
    except openai.APIConnectionError as error:
        raise ErrorIA("No se pudo conectar con OpenAI.") from error
    except openai.OpenAIError as error:
        raise ErrorIA(f"Error de OpenAI: {error.__class__.__name__}.") from error

    contenido = respuesta.choices[0].message.content if respuesta.choices else None
    if not contenido:
        raise ErrorIA("OpenAI devolvió una respuesta vacía.")
    return contenido


# ---------------------------------------------------------------------------
# Resultado
# ---------------------------------------------------------------------------

def _como_lista_de_texto(valor):
    if not isinstance(valor, list):
        return []
    return [str(v).strip() for v in valor if str(v).strip()]


def redactar_resumen(reporte, config=None, llamar_modelo=None):
    """
    Devuelve {"resumen": str, "observaciones": [str], "modelo": str, "fecha": str} o lanza ErrorIA.
    `llamar_modelo(mensajes, config) -> str` se puede reemplazar (pruebas sin llamar a OpenAI).
    """
    config = config if config is not None else cargar_configuracion_ia()
    if not config.get("habilitado", False):
        raise ErrorIA("La redacción con IA está deshabilitada en config/ia.yaml.")
    if not config.get("modelo"):
        raise ErrorIA("Falta el modelo en config/ia.yaml.")

    datos = preparar_datos(reporte, enviar_nombres=bool(config.get("enviar_nombres", False)))
    respuesta = (llamar_modelo or _llamar_modelo)(_mensajes(datos, config), config)

    try:
        contenido = json.loads(respuesta)
        resumen = str(contenido["resumen"]).strip()
    except (ValueError, KeyError, TypeError) as error:
        raise ErrorIA("La respuesta de la IA no tuvo el formato esperado.") from error
    observaciones = _como_lista_de_texto(contenido.get("observaciones"))[: int(config.get("maximo_observaciones", 5))]
    if not resumen:
        raise ErrorIA("La IA no entregó un resumen.")

    permitidas = config.get("cifras_permitidas", [])
    sospechosas = cifras_no_verificadas(" ".join([resumen] + observaciones), datos, permitidas)
    if sospechosas:
        raise ErrorIA(
            "Se descartó el texto de la IA: menciona cifras que no están en el diagnóstico ("
            + ", ".join(dict.fromkeys(sospechosas))
            + ")."
        )

    return {
        "resumen": resumen,
        "observaciones": observaciones,
        "modelo": config["modelo"],
        "fecha": datetime.now().strftime("%Y-%m-%d %H:%M"),
    }
