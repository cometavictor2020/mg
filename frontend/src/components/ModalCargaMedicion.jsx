import { useEffect, useState } from "react"

import { apiFetch } from "../utils/apiFetch"

const URL_BASE = "http://127.0.0.1:8000"

// D-061: se analiza solo el inicio del archivo (basta para ver columnas y
// rangos); el archivo completo se envía recién al cargar la medición.
const BYTES_PARA_ANALIZAR = 1_000_000
// D-063: un .mat es binario (no se puede cortar): se envía completo para analizarlo.
const EXTENSIONES_IMPORTABLES = [".csv", ".txt", ".tsv", ".mat"]

const ROLES = [
  { valor: "ignorar", etiqueta: "No usar" },
  { valor: "x", etiqueta: "Vibración X" },
  { valor: "y", etiqueta: "Vibración Y" },
  { valor: "z", etiqueta: "Vibración Z" },
  { valor: "tiempo", etiqueta: "Tiempo" },
  { valor: "temperatura", etiqueta: "Temperatura" },
]

const EJES = ["x", "y", "z"]

function rolesDesdeColumnas(columnas) {
  const roles = {}
  for (const [rol, nombre] of Object.entries(columnas ?? {})) {
    if (nombre) roles[nombre] = rol
  }
  return roles
}

function formatearRango(canal) {
  if (canal.tipo !== "numerico" || canal.minimo === null) return canal.tipo === "fecha_hora" ? "fecha y hora" : "texto"
  const rango = `${canal.minimo} … ${canal.maximo}`
  return canal.muestras ? `${canal.muestras.toLocaleString("es-CL")} muestras · ${rango}` : rango
}

// Variables de un .mat que el archivo declara (frecuencia de muestreo, velocidad): su
// valor sale del propio archivo analizado, tanto para la propuesta como para una plantilla.
function valoresDeVariables(mapeo, escalares) {
  const resultado = { frecuencia: null, velocidadRpm: null, descripcionVelocidad: "" }
  const frecuencia = escalares?.[mapeo.variable_frecuencia_muestreo]
  if (frecuencia) resultado.frecuencia = Math.round(frecuencia)

  const velocidad = escalares?.[mapeo.variable_rpm]
  if (velocidad) {
    const enHz = mapeo.unidad_variable_rpm === "hz"
    resultado.velocidadRpm = Math.round((enHz ? velocidad * 60 : velocidad) * 100) / 100
    resultado.descripcionVelocidad = `${velocidad} ${enHz ? "Hz (rev/s)" : "r/min"} en la variable «${mapeo.variable_rpm}»`
  }
  return resultado
}

function ModalCargaMedicion({ equipoId, equipoNombre, onCerrar, onCargada }) {
  const [sensores, setSensores] = useState([])
  const [cargandoSensores, setCargandoSensores] = useState(true)

  const [sensorId, setSensorId] = useState("")
  const [frecuenciaMuestreo, setFrecuenciaMuestreo] = useState("10000")
  const [rpmReal, setRpmReal] = useState("")
  const [unidad, setUnidad] = useState("")
  const [archivo, setArchivo] = useState(null)

  // Importador (D-061): lo que se entiende del archivo y lo que la persona confirma.
  const [analisis, setAnalisis] = useState(null)
  const [analizando, setAnalizando] = useState(false)
  const [roles, setRoles] = useState({})
  const [rolesPropuestos, setRolesPropuestos] = useState({})
  const [unidadDelArchivo, setUnidadDelArchivo] = useState("")
  const [plantillaId, setPlantillaId] = useState("")
  const [guardarPlantilla, setGuardarPlantilla] = useState(false)
  const [nombrePlantilla, setNombrePlantilla] = useState("")
  // Solo .mat: de qué variables del archivo salieron la frecuencia y la velocidad.
  const [variablesMat, setVariablesMat] = useState({})
  const [notaVelocidad, setNotaVelocidad] = useState("")

  const [enviando, setEnviando] = useState(false)
  const [errores, setErrores] = useState([])
  const [mensajeExito, setMensajeExito] = useState("")
  const [avisoPlantilla, setAvisoPlantilla] = useState("")

  useEffect(() => {
    apiFetch(`${URL_BASE}/api/sensores`)
      .then((respuesta) => (respuesta.ok ? respuesta.json() : []))
      .then((todos) => {
        const delEquipo = todos.filter((sensor) => sensor.equipo_id === equipoId)
        setSensores(delEquipo)
        if (delEquipo.length === 1) {
          setSensorId(String(delEquipo[0].id))
        }
      })
      .finally(() => setCargandoSensores(false))
  }, [equipoId])

  const sensorSeleccionado = sensores.find((sensor) => sensor.id === Number(sensorId)) ?? null
  const unidadesDisponibles = sensorSeleccionado?.unidades ?? []

  // D-062: un sensor puede medir 1 o 3 ejes; solo se piden (y se ofrecen) los suyos.
  const ejesSensor = (sensorSeleccionado?.ejes?.length ? sensorSeleccionado.ejes : ["X", "Y", "Z"]).map((eje) =>
    eje.toLowerCase()
  )
  const esMat = analisis?.formato?.tipo === "mat"
  // Un .mat no trae columna de tiempo: el timestamp se genera desde la frecuencia de muestreo.
  const rolesDisponibles = ROLES.filter(
    (rol) => (!EJES.includes(rol.valor) || ejesSensor.includes(rol.valor)) && !(esMat && rol.valor === "tiempo")
  )
  const etiquetaRol = (rol) => (ejesSensor.length === 1 && rol.valor === "x" ? "Vibración (eje X)" : rol.etiqueta)
  const hayEjesDescartados = Object.values(rolesPropuestos).some((rol) => EJES.includes(rol) && !ejesSensor.includes(rol))

  const necesitaAdaptacion = Boolean(analisis && !analisis.propuesta.formato_nativo)
  const unidadNoConfigurada =
    necesitaAdaptacion && unidadDelArchivo && sensorSeleccionado && !unidadesDisponibles.includes(unidadDelArchivo)

  // La unidad que declara el archivo se preselecciona si el sensor la tiene configurada.
  useEffect(() => {
    if (unidadDelArchivo && unidadesDisponibles.includes(unidadDelArchivo)) {
      setUnidad(unidadDelArchivo)
    }
  }, [unidadDelArchivo, sensorId, sensores])

  // La asignación propuesta (o de la plantilla) se restringe a los ejes del sensor elegido:
  // las columnas asignadas a un eje que el sensor no tiene pasan a «No usar».
  useEffect(() => {
    const restringidos = {}
    for (const [nombre, rol] of Object.entries(rolesPropuestos)) {
      restringidos[nombre] = EJES.includes(rol) && !ejesSensor.includes(rol) ? "ignorar" : rol
    }
    setRoles(restringidos)
  }, [rolesPropuestos, sensorId, sensores])

  function aplicarMapeo(mapeo, analisisActual = analisis) {
    setRolesPropuestos(rolesDesdeColumnas(mapeo.columnas))
    setUnidadDelArchivo(mapeo.unidad ?? "")

    // .mat: la frecuencia y la velocidad se leen de las variables que el archivo declara.
    const delArchivo = valoresDeVariables(mapeo, analisisActual?.escalares)
    setVariablesMat({
      variable_frecuencia_muestreo: mapeo.variable_frecuencia_muestreo ?? null,
      variable_rpm: mapeo.variable_rpm ?? null,
      unidad_variable_rpm: mapeo.unidad_variable_rpm ?? null,
    })
    if (delArchivo.velocidadRpm) {
      setRpmReal(String(delArchivo.velocidadRpm))
      setNotaVelocidad(
        `La velocidad de giro se completó desde el archivo (${delArchivo.descripcionVelocidad}): ` +
          `${delArchivo.velocidadRpm} r/min. Confírmala o corrígela.`
      )
    } else {
      setNotaVelocidad("")
    }

    // Si el archivo no declara la frecuencia, el campo queda vacío y obligatorio:
    // no se deja el valor de ejemplo como si fuera un dato del archivo.
    const frecuencia = delArchivo.frecuencia ?? mapeo.frecuencia_muestreo
    setFrecuenciaMuestreo(frecuencia ? String(frecuencia) : "")
  }

  function elegirPlantilla(id) {
    setPlantillaId(id)
    const plantilla = analisis.plantillas_coincidentes.find((p) => String(p.id) === id)
    aplicarMapeo(plantilla ? plantilla.mapeo : analisis.propuesta)
  }

  async function elegirArchivo(nuevo) {
    // Un archivo adaptado deja la frecuencia vacía si no la declaraba: al cambiar
    // de archivo se vuelve al valor por defecto de siempre. Lo mismo con la velocidad
    // que se había completado desde el archivo anterior.
    if (necesitaAdaptacion) setFrecuenciaMuestreo("10000")
    if (notaVelocidad) setRpmReal("")
    setNotaVelocidad("")
    setVariablesMat({})
    setArchivo(nuevo)
    setAnalisis(null)
    setRolesPropuestos({})
    setRoles({})
    setUnidadDelArchivo("")
    setPlantillaId("")
    setGuardarPlantilla(false)
    setNombrePlantilla("")
    setErrores([])

    if (!nuevo || !EXTENSIONES_IMPORTABLES.some((extension) => nuevo.name.toLowerCase().endsWith(extension))) return

    const archivoEsMat = nuevo.name.toLowerCase().endsWith(".mat")
    const formulario = new FormData()
    formulario.append("archivo", archivoEsMat ? nuevo : nuevo.slice(0, BYTES_PARA_ANALIZAR), nuevo.name)

    setAnalizando(true)
    try {
      const respuesta = await apiFetch(`${URL_BASE}/api/importacion/analizar`, { method: "POST", body: formulario })
      const datos = await respuesta.json().catch(() => null)
      if (!respuesta.ok) {
        // Un CSV que el importador no entiende no impide el flujo de siempre: el
        // servidor lo valida al cargarlo y devuelve sus errores. Un .mat, en cambio,
        // no tiene flujo sin importador: se muestra el motivo.
        if (archivoEsMat) setErrores(datos?.detail?.errores ?? ["No fue posible leer el archivo .mat."])
        return
      }

      setAnalisis(datos)
      if (datos.propuesta.formato_nativo) return

      const plantilla = datos.plantillas_coincidentes[0]
      if (plantilla) {
        setPlantillaId(String(plantilla.id))
        aplicarMapeo(plantilla.mapeo, datos)
      } else {
        aplicarMapeo(datos.propuesta, datos)
      }
    } catch {
      // Sin respuesta del importador se sigue con el flujo de siempre.
    } finally {
      setAnalizando(false)
    }
  }

  function construirMapeo() {
    const columnas = { tiempo: null, x: null, y: null, z: null, temperatura: null }
    for (const [nombre, rol] of Object.entries(roles)) {
      if (rol === "ignorar" || !(rol in columnas)) continue
      if (columnas[rol]) {
        return { error: `Más de una columna tiene el uso «${ROLES.find((r) => r.valor === rol).etiqueta}».` }
      }
      columnas[rol] = nombre
    }

    const faltantes = ejesSensor.filter((eje) => !columnas[eje])
    if (faltantes.length > 0) {
      return {
        error: `Asigna una columna a: ${faltantes.map((eje) => `Vibración ${eje.toUpperCase()}`).join(", ")}. El sensor es ${
          ejesSensor.length === 1 ? "de un solo eje" : "triaxial"
        }.`,
      }
    }

    return {
      mapeo: {
        version: 1,
        formato: analisis.formato,
        columnas,
        unidad,
        frecuencia_muestreo: Number(frecuenciaMuestreo),
        // Un .mat registra de qué variables salieron la frecuencia y la velocidad; una
        // tabla de texto, la unidad de su columna de tiempo.
        ...(esMat ? variablesMat : { unidad_tiempo: analisis.propuesta.unidad_tiempo }),
      },
    }
  }

  async function enviar(evento) {
    evento.preventDefault()
    setErrores([])
    setMensajeExito("")
    setAvisoPlantilla("")

    if (!sensorId) {
      setErrores(["Selecciona el sensor al que pertenece este archivo."])
      return
    }
    if (!unidad) {
      setErrores(["Selecciona la unidad en la que vienen los datos."])
      return
    }
    if (!archivo) {
      setErrores(["Selecciona un archivo de datos."])
      return
    }

    let mapeo = null
    if (necesitaAdaptacion) {
      const construido = construirMapeo()
      if (construido.error) {
        setErrores([construido.error])
        return
      }
      if (guardarPlantilla && !nombrePlantilla.trim()) {
        setErrores(["Escribe un nombre para la plantilla, o desmarca «Guardar como plantilla»."])
        return
      }
      mapeo = construido.mapeo
    }

    const formulario = new FormData()
    formulario.append("sensor_id", sensorId)
    formulario.append("frecuencia_muestreo", frecuenciaMuestreo)
    formulario.append("unidad", unidad)
    if (rpmReal.trim() !== "") {
      formulario.append("rpm_real", rpmReal)
    }
    if (mapeo) {
      formulario.append("mapeo", JSON.stringify(mapeo))
    }
    formulario.append("archivo", archivo)

    setEnviando(true)
    try {
      const respuesta = await apiFetch(`${URL_BASE}/api/mediciones`, {
        method: "POST",
        body: formulario,
      })

      if (!respuesta.ok) {
        const detalle = await respuesta.json().catch(() => null)
        const detalleError = detalle?.detail
        if (detalleError?.errores) {
          setErrores(detalleError.errores)
        } else {
          setErrores([detalleError ?? "No fue posible cargar la medición"])
        }
        return
      }

      // La plantilla se guarda solo después de que el mapeo funcionó de verdad.
      if (mapeo && guardarPlantilla) {
        const guardada = await apiFetch(`${URL_BASE}/api/importacion/plantillas`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ nombre: nombrePlantilla.trim(), huella: analisis.huella, mapeo }),
        })
        if (!guardada.ok) {
          const detalle = await guardada.json().catch(() => null)
          setAvisoPlantilla(`La medición se cargó, pero la plantilla no se guardó: ${detalle?.detail ?? "error desconocido"}`)
        } else {
          setAvisoPlantilla(`Plantilla «${nombrePlantilla.trim()}» guardada: se ofrecerá con los próximos archivos de este formato.`)
        }
      }

      setMensajeExito(
        mapeo
          ? "Medición adaptada al formato de MotorGuardian, validada y cargada correctamente."
          : "Medición cargada y validada correctamente."
      )
      onCargada?.()
    } catch (err) {
      setErrores([err.message])
    } finally {
      setEnviando(false)
    }
  }

  return (
    <div className="modal-fondo" onClick={onCerrar}>
      <div className="modal-contenido" onClick={(evento) => evento.stopPropagation()}>
        <div className="modal-encabezado">
          <h3>Cargar datos — {equipoNombre}</h3>
          <button type="button" className="modal-cerrar" onClick={onCerrar} aria-label="Cerrar">
            ×
          </button>
        </div>

        {cargandoSensores && <p className="config-mensaje">Cargando sensores…</p>}

        {!cargandoSensores && sensores.length === 0 && (
          <p className="config-error">
            Este equipo no tiene sensores registrados. Agrega uno en Configuración → Sensores primero.
          </p>
        )}

        {!cargandoSensores && sensores.length > 0 && !mensajeExito && (
          <form className="config-form" onSubmit={enviar}>
            <div className="config-form-campo config-form-campo-ancho">
              <label>Sensor</label>
              <select value={sensorId} onChange={(e) => { setSensorId(e.target.value); setUnidad("") }} required>
                <option value="" disabled>Selecciona un sensor</option>
                {sensores.map((sensor) => (
                  <option key={sensor.id} value={sensor.id}>
                    {sensor.codigo ?? sensor.tipo} {sensor.ubicacion ? `— ${sensor.ubicacion}` : ""}
                  </option>
                ))}
              </select>
            </div>

            <div className="config-form-campo config-form-campo-ancho">
              <label>Archivo de datos</label>
              <input
                type="file"
                accept=".csv,.txt,.tsv,.mat"
                onChange={(e) => elegirArchivo(e.target.files?.[0] ?? null)}
                required
              />
            </div>

            {analizando && <p className="config-mensaje">Leyendo el archivo…</p>}

            {analisis && analisis.propuesta.formato_nativo && (
              <p className="config-nota config-form-campo-ancho">
                El archivo ya tiene el formato interno de MotorGuardian: no necesita adaptarse.
              </p>
            )}

            {necesitaAdaptacion && (
              <div className="config-subformulario config-form-campo-ancho">
                <strong>Adaptar el archivo al formato de MotorGuardian</strong>
                <p className="config-nota">
                  {esMat ? (
                    <>
                      Este archivo es un .mat de Matlab: elige cuál de sus variables es la señal de vibración de
                      cada eje del sensor.
                    </>
                  ) : (
                    <>
                      Este archivo no tiene el formato interno (columnas{" "}
                      <code>{["timestamp", ...ejesSensor.map((eje) => `vibracion_${eje}`)].join(", ")}</code>).
                      Confirma qué es cada columna.
                    </>
                  )}{" "}
                  El sistema propone una asignación por los nombres, pero solo tú sabes cómo se montó cada sensor.
                  El archivo original no se modifica; se guarda una copia convertida junto con esta asignación.
                </p>

                {analisis.plantillas_coincidentes.length > 0 && (
                  <div className="config-form-campo">
                    <label>Plantilla</label>
                    <select value={plantillaId} onChange={(e) => elegirPlantilla(e.target.value)}>
                      <option value="">Propuesta del sistema (sin plantilla)</option>
                      {analisis.plantillas_coincidentes.map((plantilla) => (
                        <option key={plantilla.id} value={plantilla.id}>{plantilla.nombre}</option>
                      ))}
                    </select>
                    {plantillaId && (
                      <p className="config-mensaje">Se aplicó una plantilla guardada para este formato; revísala igual.</p>
                    )}
                  </div>
                )}

                <table className="config-tabla">
                  <thead>
                    <tr>
                      <th>Columna del archivo</th>
                      <th>Valores</th>
                      <th>Uso</th>
                    </tr>
                  </thead>
                  <tbody>
                    {analisis.canales.map((canal) => (
                      <tr key={canal.nombre}>
                        <td>{canal.nombre}</td>
                        <td>{formatearRango(canal)}</td>
                        <td>
                          <select
                            value={roles[canal.nombre] ?? "ignorar"}
                            onChange={(e) => setRoles({ ...roles, [canal.nombre]: e.target.value })}
                          >
                            {rolesDisponibles.map((rol) => (
                              <option key={rol.valor} value={rol.valor}>{etiquetaRol(rol)}</option>
                            ))}
                          </select>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>

                {!plantillaId && analisis.propuesta.notas.map((nota, indice) => (
                  <p key={indice} className="config-nota">{nota}</p>
                ))}

                {hayEjesDescartados && (
                  <p className="config-nota">
                    El sensor elegido mide {ejesSensor.length === 1 ? "un solo eje" : `${ejesSensor.length} ejes`}: del
                    resto de las columnas asignadas solo se conservó la de su eje. Si la señal que quieres analizar es
                    otra, cámbiala en «Uso».
                  </p>
                )}

                {!frecuenciaMuestreo && (
                  <p className="config-error">
                    El archivo no declara su frecuencia de muestreo: indícala abajo (está en la ficha del
                    instrumento o del dataset).
                  </p>
                )}
                {unidadNoConfigurada && (
                  <p className="config-error">
                    El archivo indica la unidad «{unidadDelArchivo}», que este sensor no tiene configurada. Agrégala
                    en Configuración → Sensores para poder usarla: el sistema no convierte unidades.
                  </p>
                )}

                <div className="config-form-campo">
                  <label className="config-checkbox">
                    <input
                      type="checkbox"
                      checked={guardarPlantilla}
                      onChange={(e) => setGuardarPlantilla(e.target.checked)}
                    />
                    Guardar esta asignación como plantilla
                  </label>
                  {guardarPlantilla && (
                    <input
                      type="text"
                      placeholder="Ej: Dataset Ottawa 42 kHz"
                      value={nombrePlantilla}
                      onChange={(e) => setNombrePlantilla(e.target.value)}
                    />
                  )}
                </div>
              </div>
            )}

            {sensorSeleccionado && (
              <div className="config-form-campo">
                <label>Unidad de los datos</label>
                <select value={unidad} onChange={(e) => setUnidad(e.target.value)} required>
                  <option value="" disabled>Selecciona una unidad</option>
                  {unidadesDisponibles.map((u) => (
                    <option key={u} value={u}>{u}</option>
                  ))}
                </select>
                {unidadesDisponibles.length === 0 && (
                  <p className="config-mensaje">
                    Este sensor no tiene unidades configuradas — agrégalas en Configuración → Sensores.
                  </p>
                )}
              </div>
            )}

            <div className="config-form-campo">
              <label>Frecuencia de muestreo (Hz)</label>
              <input
                type="number"
                step="1"
                min="1"
                value={frecuenciaMuestreo}
                onChange={(e) => setFrecuenciaMuestreo(e.target.value)}
                required
              />
            </div>

            <div className="config-form-campo">
              <label>Velocidad real del motor (r/min) — opcional</label>
              <input
                type="number"
                step="any"
                min="1"
                placeholder="Ej: 1425"
                value={rpmReal}
                onChange={(e) => setRpmReal(e.target.value)}
              />
              <p className="config-nota">
                Un motor con carga gira por debajo de su velocidad nominal. Si la conoces (tacómetro,
                placa con carga), decláralo aquí. Si la dejas vacía, el sistema la estima desde el
                espectro y lo indica en el reporte.
              </p>
              {notaVelocidad && <p className="config-nota">{notaVelocidad}</p>}
            </div>

            <p className="config-nota">
              Se admiten sensores de vibración de 3 ejes o de un solo eje. Un archivo con el formato
              interno debe tener las columnas <code>timestamp</code>, <code>vibracion_x</code> y, si el
              sensor es triaxial, <code>vibracion_y</code> y <code>vibracion_z</code> y, opcionalmente,{" "}
              <code>temperatura</code>. Si trae otras columnas, otro delimitador o no trae tiempo, el
              sistema te ayuda a adaptarlo (CSV, TXT, TSV o .mat de Matlab).
            </p>

            {errores.length > 0 && (
              <ul className="config-error">
                {errores.map((error, indice) => (
                  <li key={indice}>{error}</li>
                ))}
              </ul>
            )}

            <div className="config-form-acciones">
              <button type="submit" className="config-boton-primario" disabled={enviando || analizando}>
                {enviando ? "Validando y cargando…" : "Cargar medición"}
              </button>
              <button type="button" className="config-boton-secundario" onClick={onCerrar}>
                Cancelar
              </button>
            </div>
          </form>
        )}

        {mensajeExito && (
          <div className="config-seccion">
            <p className="config-mensaje">{mensajeExito}</p>
            {avisoPlantilla && <p className="config-mensaje">{avisoPlantilla}</p>}
            <button type="button" className="config-boton-primario" onClick={onCerrar}>
              Cerrar
            </button>
          </div>
        )}
      </div>
    </div>
  )
}

export default ModalCargaMedicion
