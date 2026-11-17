"""
Lista los modelos de OpenAI que tu clave puede usar, para elegir cual poner en config/ia.yaml (campo "modelo").

Lee OPENAI_API_KEY del archivo .env (nunca la imprime). Listar modelos no consume creditos.
Por defecto oculta los que no sirven para redactar texto (imagenes, audio, embeddings, moderacion...); esa
lista es una aproximacion por nombre: con --todos se muestran todos.

Uso:
    cd C:\\Users\\comet\\Documents\\mg
    .\\venv\\Scripts\\python.exe herramientas\\listar_modelos_openai.py
    .\\venv\\Scripts\\python.exe herramientas\\listar_modelos_openai.py --todos
"""

import argparse
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

RUTA_PROYECTO = Path(__file__).parent.parent
load_dotenv(RUTA_PROYECTO / ".env")

NO_SIRVEN_PARA_TEXTO = ("embedding", "whisper", "tts", "dall-e", "image", "audio", "moderation", "realtime", "transcribe", "sora", "speech")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--todos", action="store_true", help="mostrar tambien los modelos que no son de texto")
    argumentos = parser.parse_args()

    if not os.getenv("OPENAI_API_KEY"):
        sys.exit("Falta OPENAI_API_KEY en el archivo .env.")

    import openai

    try:
        modelos = sorted(m.id for m in openai.OpenAI().models.list())
    except openai.AuthenticationError:
        sys.exit("OpenAI rechazó la clave OPENAI_API_KEY (inválida o revocada).")
    except openai.OpenAIError as error:
        sys.exit(f"No se pudo consultar OpenAI: {error.__class__.__name__}.")

    if not argumentos.todos:
        modelos = [m for m in modelos if not any(palabra in m for palabra in NO_SIRVEN_PARA_TEXTO)]

    print(f"{len(modelos)} modelos disponibles para tu clave:")
    for modelo in modelos:
        print(f"  {modelo}")
    print('\nCopia uno en config/ia.yaml, en la línea:  modelo: "..."')


if __name__ == "__main__":
    main()
