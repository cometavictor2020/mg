"""
Notificacion de alertas por correo y Telegram (D-054/D-055, ver PROYECTO.md).

Cuando se carga una medicion, se evalua el equipo con el MISMO motor que ya
usa la pantalla (backend/api/administracion/alertas.py::evaluar_equipo) y,
si algun hallazgo cumple los disparadores de config/notificaciones.yaml,
se avisa por cada canal configurado. Este modulo no calcula nada de
diagnostico: solo decide si avisar, arma el texto y registra el envio.

Principios:
    - Un fallo de envio nunca rompe la carga de la medicion (se ejecuta en
      segundo plano y todo error queda en el log y en la tabla notificacion).
    - El mismo hallazgo no se repite dentro de la ventana de
      antiduplicacion, salvo que empeore (nivel mayor al ultimo avisado).
      El "ya avisado" se lleva POR DESTINATARIO (D-055): quien se agrega
      despues recibe lo vigente en la siguiente carga de medicion.
    - A quien se avisa sale de la tabla destinatario_notificacion
      (administrable desde la aplicacion) mas los destinatarios "base"
      opcionales de .env; solo los activos reciben avisos.
    - Un envio fallido NO cuenta como avisado: se reintenta en la proxima
      carga de medicion.
    - La "confianza" que se informa es el puntaje de evidencia del motor de
      reglas, no una probabilidad de falla; el texto lo aclara.
"""

import json
import logging
from datetime import datetime, timedelta
from pathlib import Path

import yaml

from backend.api.administracion.alertas import evaluar_equipo
from backend.notificaciones import canales
from basedatos.conexion import SesionLocal
from basedatos.modelos import DestinatarioNotificacion, Equipo, Medicion, Notificacion

logger = logging.getLogger("motorguardian.notificaciones")

RUTA_CONFIG = Path(__file__).parent.parent.parent / "config" / "notificaciones.yaml"
# Estado del interruptor general de la aplicacion: es del equipo donde corre el sistema, no se sube a Git (datos/).
RUTA_ESTADO = Path(__file__).parent.parent.parent / "datos" / "estado_notificaciones.json"

NOMBRES_FALLA = {
    "desbalanceo": "Desbalanceo",
    "desalineacion_paralela": "Desalineación paralela",
    "desalineacion_angular": "Desalineación angular",
    "rodamiento_pista_exterior": "Rodamiento — pista exterior (BPFO)",
    "rodamiento_pista_interior": "Rodamiento — pista interior (BPFI)",
    "rodamiento_elemento_rodante": "Rodamiento — elemento rodante (BSF)",
    "rodamiento_jaula": "Rodamiento — jaula (FTF)",
}

NOMBRES_NIVEL = {1: "alto", 2: "muy alto"}


def cargar_configuracion():
    with open(RUTA_CONFIG, "r", encoding="utf-8") as archivo:
        return yaml.safe_load(archivo)["notificaciones"]


def _leer_interruptor():
    """El estado guardado por el interruptor de la aplicacion, o None si nunca se uso (o no se puede leer)."""
    try:
        datos = json.loads(RUTA_ESTADO.read_text(encoding="utf-8"))
        if isinstance(datos.get("habilitado"), bool):
            return datos
    except FileNotFoundError:
        return None
    except (OSError, ValueError, AttributeError):
        logger.warning("No se pudo leer %s: se usa el valor de config/notificaciones.yaml.", RUTA_ESTADO)
    return None


def estado_global(config=None):
    """
    Estado de TODAS las notificaciones: {"habilitado", "origen", "cambiado_en", "cambiado_por"}.
    Lo que se fija con el interruptor de la aplicacion (fijar_habilitado) manda sobre el
    `habilitado` de config/notificaciones.yaml, que solo vale mientras el interruptor no se haya usado.
    """
    interruptor = _leer_interruptor()
    if interruptor is not None:
        return {
            "habilitado": interruptor["habilitado"],
            "origen": "interruptor",
            "cambiado_en": interruptor.get("cambiado_en"),
            "cambiado_por": interruptor.get("cambiado_por"),
        }
    config = config if config is not None else cargar_configuracion()
    return {"habilitado": bool(config.get("habilitado", False)), "origen": "configuracion", "cambiado_en": None, "cambiado_por": None}


def fijar_habilitado(habilitado, usuario=None):
    """Activa o desactiva todas las notificaciones (avisos automaticos y mensajes de prueba). Devuelve el estado."""
    RUTA_ESTADO.parent.mkdir(exist_ok=True)
    contenido = {
        "habilitado": bool(habilitado),
        "cambiado_en": datetime.utcnow().isoformat(timespec="seconds"),
        "cambiado_por": usuario,
    }
    temporal = RUTA_ESTADO.with_suffix(".tmp")
    temporal.write_text(json.dumps(contenido, ensure_ascii=False), encoding="utf-8")
    temporal.replace(RUTA_ESTADO)
    logger.info("Notificaciones %s por %s.", "activadas" if habilitado else "desactivadas", usuario or "desconocido")
    return estado_global()


def hallazgos_que_disparan(resultado, config):
    """
    Filtra lo que devolvio evaluar_equipo() segun los disparadores del YAML.
    Devuelve una lista ordenada del hallazgo mas grave al menos grave.
    """
    disparadores = config["disparadores"]
    hallazgos = []

    for hipotesis in resultado.get("hipotesis", []):
        confianza = hipotesis["confianza"]
        if confianza >= disparadores["confianza_minima"]:
            hallazgos.append(
                {
                    "tipo": "falla",
                    "clave": f"falla:{hipotesis['falla']}:sensor{hipotesis['sensor_id']}",
                    "nivel": 2 if confianza >= disparadores["confianza_muy_alta"] else 1,
                    "hipotesis": hipotesis,
                }
            )

    severidad = resultado.get("severidad_iso")
    if severidad and severidad.get("aplicable"):
        nivel_zona = disparadores["zonas_iso"].get(severidad.get("zona"))
        if nivel_zona:
            hallazgos.append(
                {"tipo": "iso", "clave": "iso_20816_3", "nivel": nivel_zona, "severidad": severidad}
            )

    # D-059: cambio de la vibracion respecto de la linea base. Solo avisa los
    # niveles que config/notificaciones.yaml lista en disparadores.
    # cambio_linea_base (por defecto, solo "muy_elevado").
    cambio = resultado.get("cambio_linea_base")
    if cambio and cambio.get("aplicable"):
        nivel_cambio = disparadores.get("cambio_linea_base", {}).get(cambio.get("nivel"))
        if nivel_cambio:
            hallazgos.append(
                {
                    "tipo": "cambio",
                    "clave": f"cambio_linea_base:sensor{cambio['sensor_id']}",
                    "nivel": nivel_cambio,
                    "cambio": cambio,
                }
            )

    hallazgos.sort(key=lambda h: h["nivel"], reverse=True)
    return hallazgos


def _ya_avisado(sesion, equipo_id, hallazgo, canal, destinatario, horas):
    desde = datetime.utcnow() - timedelta(hours=horas)
    previa = (
        sesion.query(Notificacion)
        .filter(
            Notificacion.equipo_id == equipo_id,
            Notificacion.clave == hallazgo["clave"],
            Notificacion.canal == canal,
            Notificacion.destinatario == destinatario,
            Notificacion.estado == "enviada",
            Notificacion.fecha_envio >= desde,
        )
        .order_by(Notificacion.nivel.desc())
        .first()
    )
    return previa is not None and previa.nivel >= hallazgo["nivel"]


def _numero(valor, decimales=1):
    return f"{valor:.{decimales}f}".replace(".", ",")


def _linea_hallazgo(numero, hallazgo):
    if hallazgo["tipo"] == "falla":
        hipotesis = hallazgo["hipotesis"]
        nombre = NOMBRES_FALLA.get(hipotesis["falla"], hipotesis["falla"].replace("_", " "))
        lineas = [
            f"{numero}. {nombre} — confianza {round(hipotesis['confianza'] * 100)} % "
            f"(nivel {NOMBRES_NIVEL[hallazgo['nivel']]}) — sensor {hipotesis.get('sensor_codigo')}"
        ]
        evidencias = hipotesis.get("evidencias") or []
        if evidencias:
            lineas.append("   Evidencia: " + "; ".join(evidencias))
        recomendaciones = hipotesis.get("recomendacion") or []
        if recomendaciones:
            legibles = [r.replace("_", " ") for r in recomendaciones[:2]]
            lineas.append("   Recomendación: " + "; ".join(legibles))
        return lineas

    if hallazgo["tipo"] == "cambio":
        cambio = hallazgo["cambio"]
        return [
            f"{numero}. Cambio de la vibración respecto de la línea base — velocidad RMS "
            f"{_numero(cambio['velocidad_rms_actual_mm_s'], 2)} mm/s frente a "
            f"{_numero(cambio['velocidad_rms_referencia_mm_s'], 2)} mm/s de la referencia "
            f"({_numero(cambio['razon'], 1)} veces, {cambio['nivel'].replace('_', ' ')}) — sensor {cambio.get('sensor_codigo')}",
            "   Criterio relativo del proyecto (no una norma): compara contra la medición sana marcada como referencia.",
        ]

    severidad = hallazgo["severidad"]
    lineas = [
        f"{numero}. Severidad ISO 20816-3: zona {severidad['zona']} ({severidad.get('severidad')}) — "
        f"velocidad RMS {_numero(severidad['velocidad_rms_mm_s'], 2)} mm/s — sensor {severidad.get('sensor_codigo')}"
    ]
    if severidad.get("accion_recomendada"):
        lineas.append(f"   Acción recomendada por la norma: {severidad['accion_recomendada']}")
    return lineas


def construir_mensaje(nombre_equipo, nombre_planta, medicion, hallazgos):
    """Devuelve (asunto, cuerpo) en texto plano."""
    principal = hallazgos[0]
    if principal["tipo"] == "falla":
        h = principal["hipotesis"]
        titulo = NOMBRES_FALLA.get(h["falla"], h["falla"].replace("_", " "))
    elif principal["tipo"] == "cambio":
        titulo = "cambio de la vibración respecto de la línea base"
    else:
        titulo = f"severidad ISO zona {principal['severidad']['zona']}"
    asunto = f"[MotorGuardian] Alerta en {nombre_equipo}: {titulo}"

    lineas = ["MotorGuardian detectó una condición que requiere revisión.", ""]
    lineas.append(f"Equipo: {nombre_equipo}" + (f" (planta {nombre_planta})" if nombre_planta else ""))
    if medicion is not None:
        fecha = medicion.fecha_captura.strftime("%Y-%m-%d %H:%M") if medicion.fecha_captura else "sin fecha"
        lineas.append(f"Medición: n.º {medicion.id}, sensor n.º {medicion.sensor_id}, capturada {fecha} UTC")
    lineas += ["", "Hallazgos:"]
    for numero, hallazgo in enumerate(hallazgos, start=1):
        lineas += _linea_hallazgo(numero, hallazgo)
    lineas += [
        "",
        "Nota: la confianza es el puntaje de la evidencia que encontró el motor de reglas, "
        "no una probabilidad de falla. Revise el detalle del equipo en MotorGuardian antes de "
        "decidir una intervención.",
    ]
    return asunto, "\n".join(lineas)


def _canales():
    """(nombre, configurado, enviar(asunto, cuerpo, destino), destinos_base_de_env)."""
    return [
        (
            "correo",
            canales.correo_configurado,
            lambda asunto, cuerpo, destino: canales.enviar_correo(asunto, cuerpo, destino),
            canales.destinatarios_correo_base,
        ),
        (
            "telegram",
            canales.telegram_configurado,
            lambda asunto, cuerpo, destino: canales.enviar_telegram(f"{asunto}\n\n{cuerpo}", destino),
            lambda: [canales.chat_id_base()] if canales.chat_id_base() else [],
        ),
    ]


def destinatarios_activos(sesion, canal, destinos_base):
    """
    Lista de {"id", "nombre", "direccion", "origen"}: los activos de la base
    de datos mas los "base" de .env que no esten ya en la tabla. Un
    destinatario desactivado en la tabla NO se reactiva por estar en .env.
    """
    filas = sesion.query(DestinatarioNotificacion).filter(DestinatarioNotificacion.canal == canal).all()
    en_tabla = {f.direccion for f in filas}
    resultado = [
        {"id": f.id, "nombre": f.nombre, "direccion": f.direccion, "origen": "aplicacion"}
        for f in filas
        if f.activo
    ]
    for direccion in destinos_base:
        if direccion not in en_tabla:
            resultado.append({"id": None, "nombre": "(definido en .env)", "direccion": direccion, "origen": "env"})
    return resultado


def _notificar(equipo_id, medicion_id):
    config = cargar_configuracion()
    estado = estado_global(config)
    if not estado["habilitado"]:
        origen = "desde la aplicación" if estado["origen"] == "interruptor" else "en config/notificaciones.yaml"
        return {"omitido": f"notificaciones desactivadas {origen}"}

    resultado = evaluar_equipo(equipo_id)
    if resultado.get("advertencia"):
        return {"omitido": resultado["advertencia"]}

    hallazgos = hallazgos_que_disparan(resultado, config)
    if not hallazgos:
        return {"hallazgos": 0, "canales": {}}

    sesion = SesionLocal()
    try:
        equipo = sesion.query(Equipo).filter(Equipo.id == equipo_id).first()
        medicion = sesion.query(Medicion).filter(Medicion.id == medicion_id).first() if medicion_id else None
        nombre_planta = equipo.planta.nombre if equipo and equipo.planta else None
        horas = config["antiduplicacion"]["horas_sin_repetir"]

        resumen = {}
        for nombre_canal, esta_configurado, enviar, destinos_base in _canales():
            if not config.get("canales", {}).get(nombre_canal, {}).get("habilitado", False):
                resumen[nombre_canal] = "deshabilitado"
                continue
            if not esta_configurado():
                resumen[nombre_canal] = "no configurado"
                logger.info("Canal %s sin credenciales en .env: aviso omitido.", nombre_canal)
                continue

            destinatarios = destinatarios_activos(sesion, nombre_canal, destinos_base())
            if not destinatarios:
                resumen[nombre_canal] = "sin destinatarios"
                continue

            enviados, fallidos, detalles_fallo = 0, 0, []
            for destinatario in destinatarios:
                pendientes = [
                    h
                    for h in hallazgos
                    if not _ya_avisado(sesion, equipo_id, h, nombre_canal, destinatario["direccion"], horas)
                ]
                if not pendientes:
                    continue

                asunto, cuerpo = construir_mensaje(equipo.nombre, nombre_planta, medicion, pendientes)
                ok, detalle = enviar(asunto, cuerpo, destinatario["direccion"])
                for h in pendientes:
                    sesion.add(
                        Notificacion(
                            equipo_id=equipo_id,
                            medicion_id=medicion_id,
                            clave=h["clave"],
                            nivel=h["nivel"],
                            canal=nombre_canal,
                            destinatario=destinatario["direccion"],
                            estado="enviada" if ok else "fallida",
                            detalle=detalle,
                        )
                    )
                sesion.commit()
                if ok:
                    enviados += 1
                else:
                    fallidos += 1
                    detalles_fallo.append(detalle)

            if enviados == 0 and fallidos == 0:
                resumen[nombre_canal] = "sin novedades (ya avisado)"
            elif fallidos == 0:
                resumen[nombre_canal] = f"enviada a {enviados} destinatario(s)"
            elif enviados == 0:
                resumen[nombre_canal] = f"fallida: {detalles_fallo[0]}"
            else:
                resumen[nombre_canal] = f"parcial: {enviados} enviada(s), {fallidos} fallida(s): {detalles_fallo[0]}"

        return {"hallazgos": len(hallazgos), "canales": resumen}
    finally:
        sesion.close()


def notificar_si_corresponde(equipo_id, medicion_id=None):
    """
    Punto de entrada (se llama en segundo plano tras cargar una medicion).
    Nunca lanza excepciones: cualquier error queda en el log.
    """
    try:
        resultado = _notificar(equipo_id, medicion_id)
        logger.info("Notificaciones equipo %s: %s", equipo_id, resultado)
        return resultado
    except Exception:
        logger.exception("Error al evaluar/enviar notificaciones del equipo %s", equipo_id)
        return {"error": "ver log"}


def enviar_prueba(destinatario_id=None):
    """
    Mensaje de prueba - para comprobar credenciales y destinatarios sin
    esperar una alerta real. Con destinatario_id envia solo a ese (aunque
    este desactivado: sirve para probar antes de activarlo); sin el, a todos
    los activos. No se registra en la tabla notificacion (no es un hallazgo).
    Con las notificaciones desactivadas en general no envia nada: la lista trae
    una sola fila que lo explica. Devuelve una lista de
    {"canal", "nombre", "direccion", "resultado"}.
    """
    if not estado_global()["habilitado"]:
        return [
            {
                "canal": "todos",
                "nombre": "—",
                "direccion": "—",
                "resultado": "no enviado: las notificaciones están desactivadas (actívalas con el interruptor de esta pantalla)",
            }
        ]
    asunto = "[MotorGuardian] Mensaje de prueba"
    cuerpo = (
        "Este es un mensaje de prueba de las notificaciones de MotorGuardian. "
        "Si lo recibes, estás configurado para recibir las alertas."
    )
    sesion = SesionLocal()
    try:
        resultados = []
        for nombre_canal, esta_configurado, enviar, destinos_base in _canales():
            if destinatario_id is not None:
                fila = sesion.query(DestinatarioNotificacion).filter(DestinatarioNotificacion.id == destinatario_id).first()
                if not fila or fila.canal != nombre_canal:
                    continue
                destinatarios = [{"nombre": fila.nombre, "direccion": fila.direccion}]
            else:
                destinatarios = destinatarios_activos(sesion, nombre_canal, destinos_base())

            for destinatario in destinatarios:
                if not esta_configurado():
                    faltan = ", ".join(canales.variables_faltantes(nombre_canal))
                    resultado = f"no configurado (faltan variables en .env: {faltan})"
                else:
                    ok, detalle = enviar(asunto, cuerpo, destinatario["direccion"])
                    resultado = "enviado" if ok else f"fallido: {detalle}"
                resultados.append(
                    {
                        "canal": nombre_canal,
                        "nombre": destinatario["nombre"],
                        "direccion": destinatario["direccion"],
                        "resultado": resultado,
                    }
                )
        return resultados
    finally:
        sesion.close()
