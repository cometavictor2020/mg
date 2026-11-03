"""
Herramienta para comprobar las notificaciones (D-054/D-055) sin esperar una
alerta real: envia un mensaje de prueba a todos los destinatarios activos
(los de la aplicacion y los "base" de .env) con las credenciales de .env.
No imprime nunca contrasenas ni tokens.

Credenciales en .env (ver tambien config/notificaciones.yaml):
    SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD, SMTP_REMITENTE (opcional),
    TELEGRAM_BOT_TOKEN.
Los destinatarios se agregan desde la aplicacion (Configuracion ->
Notificaciones); .env admite destinatarios "base" opcionales:
    NOTIF_CORREO_DESTINO (correos separados por coma), TELEGRAM_CHAT_ID.

Es seguro ejecutarla varias veces. Los canales sin credenciales se informan
como "no configurado" y no fallan.
"""

from pathlib import Path
import sys

RUTA_PROYECTO = Path(__file__).parent.parent
sys.path.append(str(RUTA_PROYECTO))

from backend.notificaciones.servicio import enviar_prueba


def main():
    resultados = enviar_prueba()
    if not resultados:
        print("No hay destinatarios activos. Agrégalos en Configuración → Notificaciones.")
    for r in resultados:
        print(f"{r['canal']} -> {r['nombre']} <{r['direccion']}>: {r['resultado']}")


if __name__ == "__main__":
    main()
