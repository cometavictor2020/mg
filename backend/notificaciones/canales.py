"""
Canales de envio de las notificaciones de alerta (D-054/D-055, ver
PROYECTO.md): correo (SMTP) y Telegram (Bot API).

Solo usa la biblioteca estandar (smtplib, urllib) - no agrega dependencias.
Las CREDENCIALES (servidor SMTP, token del bot) salen de .env (nunca del
YAML ni de Git). Los DESTINATARIOS se administran desde la aplicacion
(tabla destinatario_notificacion, ver servicio.py); .env solo puede traer
destinatarios "base" opcionales (NOTIF_CORREO_DESTINO, TELEGRAM_CHAT_ID).

Un canal sin sus credenciales se considera "no configurado": no es un
error, el servicio lo omite y lo deja anotado en el log.

Ninguna funcion de envio lanza excepciones al llamador por fallas de red o
de credenciales: devuelven (ok, detalle). Asi un correo caido no puede
romper la carga de una medicion. Los tokens y contrasenas nunca se escriben
en el detalle devuelto ni en el log.
"""

import json
import logging
import os
import re
import smtplib
import ssl
import urllib.error
import urllib.request
from email.message import EmailMessage
from pathlib import Path

from dotenv import load_dotenv

RUTA_PROYECTO = Path(__file__).parent.parent.parent
load_dotenv(RUTA_PROYECTO / ".env")

logger = logging.getLogger("motorguardian.notificaciones")

TIMEOUT_SEGUNDOS = 15
LIMITE_TELEGRAM = 4096

PATRON_CORREO = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
PATRON_CHAT_ID = re.compile(r"^-?\d{5,20}$")

VARIABLES_CORREO = ["SMTP_HOST", "SMTP_USER", "SMTP_PASSWORD"]
VARIABLES_TELEGRAM = ["TELEGRAM_BOT_TOKEN"]


def _limpiar(texto, secretos):
    texto = str(texto)
    for secreto in secretos:
        if secreto:
            texto = texto.replace(secreto, "***")
    return texto


def validar_direccion(canal, direccion):
    """Devuelve None si es valida, o el mensaje de error."""
    if canal == "correo":
        if len(direccion) > 200 or not PATRON_CORREO.match(direccion):
            return "El correo electrónico no es válido."
    elif canal == "telegram":
        if not PATRON_CHAT_ID.match(direccion):
            return "El chat id de Telegram debe ser un número (negativo en los grupos), por ejemplo 123456789."
    else:
        return "El canal debe ser «correo» o «telegram»."
    return None


# --------------------------------------------------------------- credenciales
def variables_faltantes(canal):
    nombres = VARIABLES_CORREO if canal == "correo" else VARIABLES_TELEGRAM
    return [n for n in nombres if not os.getenv(n)]


def correo_configurado():
    return not variables_faltantes("correo")


def telegram_configurado():
    return not variables_faltantes("telegram")


# ------------------------------------------------- destinatarios base (.env)
def destinatarios_correo_base():
    bruto = os.getenv("NOTIF_CORREO_DESTINO", "")
    return [c.strip() for c in bruto.split(",") if c.strip()]


def chat_id_base():
    return (os.getenv("TELEGRAM_CHAT_ID") or "").strip() or None


# ------------------------------------------------------------------- envios
def enviar_correo(asunto, cuerpo, destinatario):
    """Envia a UN destinatario. Devuelve (ok, detalle). Puerto 465 -> SSL directo; otro (587) -> STARTTLS."""
    host = os.getenv("SMTP_HOST")
    puerto = int(os.getenv("SMTP_PORT", "587"))
    usuario = os.getenv("SMTP_USER")
    clave = os.getenv("SMTP_PASSWORD")
    remitente = os.getenv("SMTP_REMITENTE") or usuario

    if not PATRON_CORREO.match(destinatario or ""):
        return False, "destinatario con formato de correo inválido"

    mensaje = EmailMessage()
    mensaje["Subject"] = asunto
    mensaje["From"] = remitente
    mensaje["To"] = destinatario
    mensaje.set_content(cuerpo)

    try:
        contexto = ssl.create_default_context()
        if puerto == 465:
            servidor = smtplib.SMTP_SSL(host, puerto, timeout=TIMEOUT_SEGUNDOS, context=contexto)
        else:
            servidor = smtplib.SMTP(host, puerto, timeout=TIMEOUT_SEGUNDOS)
        with servidor:
            if puerto != 465 and os.getenv("SMTP_STARTTLS", "1") != "0":
                servidor.starttls(context=contexto)
            servidor.login(usuario, clave)
            rechazados = servidor.send_message(mensaje)
        if rechazados:
            return False, "el servidor rechazó al destinatario"
        return True, "enviado"
    except Exception as error:
        detalle = _limpiar(f"{type(error).__name__}: {error}", [clave, usuario])
        logger.warning("Fallo el envio de correo: %s", detalle)
        return False, detalle


def _url_telegram(token, metodo):
    base = os.getenv("TELEGRAM_API_BASE", "https://api.telegram.org").rstrip("/")
    return f"{base}/bot{token}/{metodo}"


def _llamar_telegram(metodo, cuerpo=None, timeout=TIMEOUT_SEGUNDOS):
    """Devuelve (datos_json | None, error | None). Nunca filtra el token."""
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    peticion = urllib.request.Request(
        _url_telegram(token, metodo),
        data=json.dumps(cuerpo or {}).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(peticion, timeout=timeout) as respuesta:
            datos = json.loads(respuesta.read().decode("utf-8"))
        if datos.get("ok"):
            return datos, None
        return None, _limpiar(f"Telegram respondió ok=false: {datos.get('description')}", [token])
    except urllib.error.HTTPError as error:
        try:
            descripcion = json.loads(error.read().decode("utf-8")).get("description")
        except Exception:
            descripcion = error.reason
        return None, _limpiar(f"HTTP {error.code}: {descripcion}", [token])
    except Exception as error:
        return None, _limpiar(f"{type(error).__name__}: {error}", [token])


def enviar_telegram(texto, chat_id):
    """Envia a UN chat. Devuelve (ok, detalle). Texto plano (sin parse_mode) para no escapar nada."""
    if len(texto) > LIMITE_TELEGRAM:
        texto = texto[: LIMITE_TELEGRAM - 20] + "\n[mensaje recortado]"

    datos, error = _llamar_telegram("sendMessage", {"chat_id": chat_id, "text": texto})
    if error:
        logger.warning("Fallo el envio a Telegram: %s", error)
        return False, _limpiar(error, [chat_id])
    return True, "enviado"


def informacion_bot_telegram():
    """
    A que bot pertenece el token de .env (getMe). Devuelve (usuario, error):
    el nombre de usuario del bot sin "@", o el motivo por el que Telegram no
    acepto el token. Sirve para comprobar que se le escribe al bot correcto.
    """
    datos, error = _llamar_telegram("getMe", timeout=6)
    if error:
        return None, error
    return (datos.get("result") or {}).get("username"), None


def detectar_chats_telegram():
    """
    Lista los chats que le escribieron al bot recientemente (Telegram solo
    conserva esas actualizaciones por unas 24 h). Sirve para obtener el chat
    id de una persona nueva sin buscarlo a mano: ella le escribe /start al
    bot y aparece aqui. Devuelve (lista, error): lista de
    {"chat_id", "nombre", "tipo"} sin repetidos.
    """
    datos, error = _llamar_telegram("getUpdates", {"limit": 100, "timeout": 0})
    if error:
        return [], error

    chats = {}
    for actualizacion in datos.get("result", []):
        for clave in ("message", "edited_message", "channel_post", "my_chat_member"):
            chat = (actualizacion.get(clave) or {}).get("chat")
            if chat and chat.get("id") is not None:
                partes = [chat.get("first_name"), chat.get("last_name")]
                nombre = chat.get("title") or " ".join(p for p in partes if p) or chat.get("username") or str(chat["id"])
                if chat.get("username") and not chat.get("title"):
                    nombre = f"{nombre} (@{chat['username']})"
                chats[str(chat["id"])] = {"chat_id": str(chat["id"]), "nombre": nombre, "tipo": chat.get("type")}
    return list(chats.values()), None
