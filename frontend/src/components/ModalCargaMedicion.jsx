import { useEffect, useState } from "react"

import { apiFetch } from "../utils/apiFetch"

const URL_BASE = "http://127.0.0.1:8000"

function ModalCargaMedicion({ equipoId, equipoNombre, onCerrar, onCargada }) {
  const [sensores, setSensores] = useState([])
  const [cargandoSensores, setCargandoSensores] = useState(true)

  const [sensorId, setSensorId] = useState("")
  const [frecuenciaMuestreo, setFrecuenciaMuestreo] = useState("10000")
  const [unidad, setUnidad] = useState("")
  const [archivo, setArchivo] = useState(null)

  const [enviando, setEnviando] = useState(false)
  const [errores, setErrores] = useState([])
  const [mensajeExito, setMensajeExito] = useState("")

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

  async function enviar(evento) {
    evento.preventDefault()
    setErrores([])
    setMensajeExito("")

    if (!sensorId) {
      setErrores(["Selecciona el sensor al que pertenece este archivo."])
      return
    }
    if (!unidad) {
      setErrores(["Selecciona la unidad en la que vienen los datos."])
      return
    }
    if (!archivo) {
      setErrores(["Selecciona un archivo CSV."])
      return
    }

    const formulario = new FormData()
    formulario.append("sensor_id", sensorId)
    formulario.append("frecuencia_muestreo", frecuenciaMuestreo)
    formulario.append("unidad", unidad)
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

      setMensajeExito("Medición cargada y validada correctamente.")
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

            <div className="config-form-campo config-form-campo-ancho">
              <label>Archivo CSV</label>
              <input
                type="file"
                accept=".csv"
                onChange={(e) => setArchivo(e.target.files?.[0] ?? null)}
                required
              />
            </div>

            <p className="config-nota">
              Por ahora solo se admiten sensores de vibración triaxial (el único tipo que el
              motor de diagnóstico usa). El archivo debe tener las columnas <code>timestamp</code>,{" "}
              <code>vibracion_x</code>, <code>vibracion_y</code>, <code>vibracion_z</code> y,
              opcionalmente, <code>temperatura</code>.
            </p>

            {errores.length > 0 && (
              <ul className="config-error">
                {errores.map((error, indice) => (
                  <li key={indice}>{error}</li>
                ))}
              </ul>
            )}

            <div className="config-form-acciones">
              <button type="submit" className="config-boton-primario" disabled={enviando}>
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
