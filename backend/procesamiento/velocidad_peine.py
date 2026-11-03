"""
Estimacion de la velocidad de giro por peine armonico (D-066, ver PROYECTO.md).

La estimacion de D-057 toma el pico dominante cerca de la velocidad nominal y
supone que es 1x. Falla cuando el 1x no destaca (un espectro dominado por
2x/3x o por un armonico del motor) y no ve nada fuera de su banda de busqueda.

Aca se usa lo que si es propio de una maquina que gira: sus componentes
sincronas aparecen en los multiplos enteros k*fr de la velocidad de giro fr.
Se prueba cada velocidad candidata de una banda alrededor de la nominal y se
puntua cuantas lineas significativas del espectro caen en k*fr (k = 1..K):

    - Una linea cuenta si su razon sobre el piso de ruido local supera la
      critica de lineas_espectrales.py (misma estadistica y mismos parametros
      que el diagnostico de rodamientos).
    - El puntaje de una linea es su sorpresa en bits (razon^2) con tope
      `saturacion_bits`: asi la cantidad de armonicos que coinciden pesa mas
      que la intensidad de uno solo.
    - Se exigen al menos `minimo_armonicos` armonicos significativos: con uno
      solo, el estimador no se distingue de "el pico mayor de la banda" y se
      deja a la regla anterior (D-057). Una velocidad a mas de
      `zona_cercana_pct` de la nominal es menos verosimil a priori (la
      nominal rara vez esta tan equivocada), asi que ahi se exigen
      `minimo_armonicos_fuera_de_zona`. Sin esta distincion, el espectro de un
      rodamiento con falla (lleno de lineas: bandas laterales cada 1x) alineaba
      por azar dos "armonicos" de una velocidad falsa en 3 de 7 ensayos reales.
      Se probo exigir los armonicos segun la densidad de lineas del espectro
      (prueba binomial con correccion por las velocidades candidatas) y se
      descarto: pedia 4 armonicos incluso en espectros limpios.
    - La velocidad ganadora debe ser unica: si otra velocidad, separada de ella
      al menos `separacion_unicidad_pct`, tiene un puntaje mayor que
      1/`razon_minima_unicidad` del ganador, el peine es ambiguo y no estima
      (la velocidad queda a la regla siguiente); el rival se cuenta con
      `minimo_armonicos`, aunque este lejos de la nominal. Donde fallaba, la velocidad
      falsa ganaba por poco (puntaje del segundo / puntaje del primero cercano
      a 1); donde acertaba, el segundo quedaba muy por debajo.
    - La busqueda se limita a la banda: una velocidad mitad o doble tambien
      alinea la mitad de los armonicos, pero queda fuera.
    - Los armonicos que caen sobre un multiplo de la frecuencia de la red
      electrica (`frecuencias_red_hz`, 50 y 60 Hz) no cuentan: esas lineas no
      se mueven con la velocidad y, si contaran, el peine las tomaria por
      armonicos de una maquina a velocidad sincrona (en una prueba sintetica
      con solo red y ruido, inventaba una velocidad en el 100 % de los casos).
      Costo: si la velocidad real coincide con la sincrona, esos armonicos
      quedan ocultos y el peine puede no tener suficientes (cae al pico
      dominante o a la nominal).

Lo que se estima sigue siendo una estimacion de la señal, no una medicion:
quien la use debe declararla como tal.
"""

import numpy as np

from backend.procesamiento.ejes import ejes_en_datos_fft
from backend.procesamiento.lineas_espectrales import EspectroLineas, razon_critica

BINS_VENTANA_LINEA = 3  # una linea se busca en +-1 bin: de ahi la cantidad de bins de la prueba de significancia
FRACCION_PLATEAU = 0.9  # las velocidades con al menos esta fraccion del puntaje maximo forman el plateau cuyo centro se informa


def _sobre_multiplo_de_red(posicion, frecuencias_red, margen):
    """Verdadero donde `posicion` (Hz) cae a menos de `margen` de un multiplo de alguna frecuencia de red."""
    sobre = np.zeros(len(posicion), dtype=bool)
    for f_red in frecuencias_red:
        sobre |= np.abs(posicion - f_red * np.maximum(np.round(posicion / f_red), 1)) <= margen
    return sobre


def estimar_velocidad_por_peine(datos_fft, rpm_nominal, normativa):
    """
    Devuelve {"rpm", "armonicos" (los k con linea significativa), "puntaje"} o None si ninguna velocidad de la
    banda de busqueda alinea `minimo_armonicos` armonicos significativos.
    """
    criterios = normativa["criterios_proyecto"]
    peine = criterios["velocidad_real"]["peine"]
    parametros_lineas = criterios["deteccion_lineas_rodamiento"]

    frecuencias = np.array([fila["frecuencia"] for fila in datos_fft], dtype=float)
    ejes = ejes_en_datos_fft(datos_fft)
    if len(frecuencias) < 16 or not rpm_nominal:
        return None

    razones = [
        EspectroLineas(frecuencias, [fila[f"amplitud_{eje}"] for fila in datos_fft], parametros_lineas, len(ejes)).razones
        for eje in ejes
    ]
    critica = parametros_lineas["margen_estimacion_piso"] * razon_critica(
        BINS_VENTANA_LINEA * len(ejes), parametros_lineas["probabilidad_falsa_alarma"]
    )

    frecuencia_nominal = rpm_nominal / 60
    paso = frecuencia_nominal * peine["paso_busqueda_pct"] / 100
    candidatas = np.arange(
        frecuencia_nominal * (1 - peine["ventana_inferior_pct"] / 100),
        frecuencia_nominal * (1 + peine["ventana_superior_pct"] / 100) + paso / 2,
        paso,
    )
    frecuencia_maxima = frecuencias[-1]
    margen_red = peine["margen_red_bins"] * (frecuencias[1] - frecuencias[0])

    puntaje = np.zeros(len(candidatas))
    significativos = np.zeros((peine["armonicos_maximos"], len(candidatas)), dtype=bool)
    for indice_armonico in range(peine["armonicos_maximos"]):
        posicion = (indice_armonico + 1) * candidatas
        dentro = (posicion <= frecuencia_maxima) & ~_sobre_multiplo_de_red(posicion, peine["frecuencias_red_hz"], margen_red)
        for razon in razones:
            valor = np.interp(posicion, frecuencias, razon)
            cuenta = dentro & (valor >= critica)
            puntaje += np.where(cuenta, np.minimum(valor ** 2, peine["saturacion_bits"]), 0.0)
            significativos[indice_armonico] |= cuenta

    cantidad = significativos.sum(axis=0)
    cerca = np.abs(candidatas / frecuencia_nominal - 1) * 100 <= peine["zona_cercana_pct"]
    elegibles = cantidad >= np.where(cerca, peine["minimo_armonicos"], peine["minimo_armonicos_fuera_de_zona"])

    if not elegibles.any():
        return None

    mejor = int(np.argmax(np.where(elegibles, puntaje, -np.inf)))

    separadas = np.abs(candidatas - candidatas[mejor]) / candidatas[mejor] * 100 > peine["separacion_unicidad_pct"]
    # El rival se cuenta con el minimo basico, sin la exigencia extra de las velocidades lejanas: la velocidad
    # verdadera puede estar lejos de la nominal y mostrar solo dos armonicos, y no por eso es menos rival.
    rivales = (cantidad >= peine["minimo_armonicos"]) & separadas
    if rivales.any() and puntaje[mejor] < peine["razon_minima_unicidad"] * puntaje[rivales].max():
        return None
    izquierda = derecha = mejor
    umbral = FRACCION_PLATEAU * puntaje[mejor]
    while izquierda > 0 and elegibles[izquierda - 1] and puntaje[izquierda - 1] >= umbral:
        izquierda -= 1
    while derecha < len(candidatas) - 1 and elegibles[derecha + 1] and puntaje[derecha + 1] >= umbral:
        derecha += 1
    frecuencia = float((candidatas[izquierda] + candidatas[derecha]) / 2)

    return {
        "rpm": frecuencia * 60,
        "armonicos": [k + 1 for k in range(peine["armonicos_maximos"]) if significativos[k, mejor]],
        "puntaje": float(puntaje[mejor]),
    }
