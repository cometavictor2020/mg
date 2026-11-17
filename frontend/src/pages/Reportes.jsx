import { useEffect, useState } from "react"

import GraficoEnvolvente from "../components/GraficoEnvolvente"
import InterruptorIA from "../components/InterruptorIA"
import Sidebar from "../components/Sidebar"
import { useEquiposReales } from "../hooks/useEquiposReales"
import { useEstadoIA } from "../hooks/useEstadoIA"
import { apiFetch } from "../utils/apiFetch"

const URL_BASE = "http://127.0.0.1:8000"

const ETIQUETAS_FALLA = {
  desbalanceo: "Desbalanceo",
  desalineacion_angular: "Desalineación angular",
  desalineacion_paralela: "Desalineación paralela",
  rodamiento_pista_exterior: "Rodamiento — pista exterior (BPFO)",
  rodamiento_pista_interior: "Rodamiento — pista interior (BPFI)",
  rodamiento_elemento_rodante: "Rodamiento — elemento rodante (BSF)",
  rodamiento_jaula: "Rodamiento — jaula (FTF)",
}

function nivelConfianza(confianza) {
  if (confianza >= 0.7) return "alta"
  if (confianza >= 0.5) return "media"
  return "baja"
}

function SeveridadIso({ severidad }) {
  if (!severidad) return null

  if (!severidad.aplicable) {
    return (
      <p className="reporte-severidad-iso-no-aplicable">
        Severidad ISO 20816-3: no evaluable — {severidad.motivo_no_aplicable}
      </p>
    )
  }

  return (
    <div className="reporte-severidad-iso">
      <span>Severidad ISO 20816-3:</span>
      <span className={`reporte-severidad-iso-zona reporte-severidad-iso-zona-${severidad.zona.toLowerCase()}`}>
        Zona {severidad.zona}
      </span>
      <span>{severidad.severidad?.replaceAll("_", " ")}</span>
      <span className="config-mensaje">
        ({severidad.velocidad_rms_mm_s?.toFixed(2)} mm/s RMS, {severidad.grupo?.replace("_", " ")}, soporte {severidad.tipo_soporte})
      </span>
    </div>
  )
}

const NOMBRES_NIVEL_CAMBIO = {
  sin_cambio: "sin cambio relevante",
  elevado: "elevado",
  muy_elevado: "muy elevado",
  disminuyo: "disminuyó",
}

// Cambio de la velocidad RMS respecto de la linea base (D-059): criterio
// relativo para equipos donde la severidad ISO no aplica (bajo 15 kW).
function CambioLineaBase({ cambio }) {
  if (!cambio) return null

  if (!cambio.aplicable) {
    return (
      <p className="reporte-severidad-iso-no-aplicable">
        Cambio respecto de la línea base: no evaluable — {cambio.motivo_no_aplicable}
      </p>
    )
  }

  return (
    <div className="reporte-severidad-iso">
      <span>Cambio respecto de la línea base:</span>
      <span className={`reporte-cambio-nivel reporte-cambio-nivel-${cambio.nivel}`}>
        {NOMBRES_NIVEL_CAMBIO[cambio.nivel] ?? cambio.nivel}
      </span>
      <span className="config-mensaje">
        ({cambio.velocidad_rms_actual_mm_s.toFixed(2)} mm/s RMS frente a {cambio.velocidad_rms_referencia_mm_s.toFixed(2)} mm/s
        de la referencia: {cambio.razon} veces; banda {cambio.banda_hz[0]}–{Math.round(cambio.banda_hz[1])} Hz, peor eje)
      </span>
      <span
        className="config-mensaje"
        title="El nivel se decide con el peor eje de cada medición; un aumento grande en un eje secundario puede quedar oculto, por eso se muestra el cambio de cada eje."
      >
        Por eje:{" "}
        {Object.entries(cambio.por_eje ?? {})
          .map(([eje, valores]) => `${eje.toUpperCase()} ×${valores.razon ?? "—"}`)
          .join(" · ")}
      </span>
    </div>
  )
}

function CalidadMedicion({ calidad }) {
  if (!calidad || calidad.estado === "valida") return null

  const mensajes = [...calidad.criticas, ...calidad.advertencias]
  return (
    <p className="reporte-calidad-medicion">
      Calidad de medición (ISO 13373-1) — {calidad.estado.replaceAll("_", " ")}: {mensajes.join(" ")}
    </p>
  )
}

const ORIGEN_VELOCIDAD = {
  medida: "declarada en la medición",
  estimada: "estimada desde el espectro",
  nominal: "nominal del equipo",
}

function textoPico(pico) {
  return pico ? `${pico.frecuencia.toFixed(1)} Hz (${Number(pico.amplitud).toPrecision(3)})` : "ninguno"
}

// Velocidad de giro usada y control de consistencia (D-057/D-058): que
// frecuencia de 1x se esperaba, que pico se encontro dentro de la ventana y
// cual es el pico dominante del espectro - para que quien analiza vea de un
// vistazo si el 1x encontrado es creible, sin depender del calculo.
function VelocidadGiro({ velocidad, verificacion }) {
  if (!velocidad) return null

  return (
    <>
      <p className="reporte-velocidad">
        Velocidad de giro usada: {Math.round(velocidad.rpm)} r/min ({ORIGEN_VELOCIDAD[velocidad.origen] ?? velocidad.origen}
        {velocidad.origen !== "nominal" &&
          `, ${velocidad.desviacion_pct > 0 ? "+" : ""}${velocidad.desviacion_pct}% respecto de la nominal`}
        )
        {verificacion && (
          <>
            <br />
            1x esperado: {verificacion.frecuencia_1x_esperada} Hz (±{verificacion.tolerancia_pct}%) · pico encontrado ahí:{" "}
            {textoPico(verificacion.pico_1x)} · pico dominante del espectro: {textoPico(verificacion.pico_dominante)}
          </>
        )}
      </p>

      {verificacion?.inconsistente && (
        <p className="reporte-calidad-medicion">
          Posible inconsistencia de velocidad: hay un pico en {textoPico(verificacion.pico_externo)}, fuera de la
          ventana donde se busca el 1x
          {verificacion.razon_pico_externo
            ? `, ${verificacion.razon_pico_externo} veces el pico encontrado dentro de ella`
            : " (dentro de la ventana no se encontró ningún pico)"}
          . La velocidad usada puede no ser la real: declárala al cargar la medición.
        </p>
      )}
    </>
  )
}

function TarjetaSensor({ sensor }) {
  return (
    <article className="tarjeta reporte-sensor">
      <h3>{sensor.nombre_tipo}</h3>

      {!sensor.tiene_medicion && <p className="config-mensaje">{sensor.mensaje}</p>}

      {sensor.tiene_medicion && (
        <>
          <SeveridadIso severidad={sensor.diagnostico.severidad_iso} />
          <CambioLineaBase cambio={sensor.diagnostico.cambio_linea_base} />
          <CalidadMedicion calidad={sensor.diagnostico.calidad_medicion} />
          <VelocidadGiro
            velocidad={sensor.diagnostico.velocidad}
            verificacion={sensor.diagnostico.verificacion_velocidad}
          />

          {sensor.diagnostico.hipotesis.length === 0 && (
            <p className="config-mensaje">
              No se encontraron hipótesis de falla con confianza suficiente.
            </p>
          )}

          {sensor.diagnostico.hipotesis.map((hipotesis) => (
            <div key={hipotesis.falla} className="reporte-hipotesis">
              <div className="reporte-hipotesis-encabezado">
                <strong>{ETIQUETAS_FALLA[hipotesis.falla] ?? hipotesis.falla}</strong>
                <span className={`reporte-confianza reporte-confianza-${nivelConfianza(hipotesis.confianza)}`}>
                  {Math.round(hipotesis.confianza * 100)}% de confianza
                </span>
              </div>
              <p className="config-mensaje">Evidencia: {hipotesis.evidencias.join(", ")}</p>
              {hipotesis.recomendacion.length > 0 && (
                <p className="config-mensaje">
                  Recomendaciones: {hipotesis.recomendacion.map((r) => r.replaceAll("_", " ")).join(", ")}
                </p>
              )}
            </div>
          ))}

          {sensor.diagnostico.grafico_rodamiento && (
            <GraficoEnvolvente grafico={sensor.diagnostico.grafico_rodamiento} />
          )}

          <details className="reporte-limitaciones">
            <summary>Limitaciones de este diagnóstico</summary>
            <ul>
              {sensor.diagnostico.limitaciones.map((limitacion) => (
                <li key={limitacion}>{limitacion}</li>
              ))}
            </ul>
          </details>
        </>
      )}
    </article>
  )
}

async function descargarPdf(reporteId, nombreEquipo) {
  const respuesta = await apiFetch(`${URL_BASE}/api/reportes/${reporteId}/pdf`)
  if (!respuesta.ok) {
    throw new Error("No fue posible descargar el PDF")
  }

  const blob = await respuesta.blob()
  const url = URL.createObjectURL(blob)

  const enlace = document.createElement("a")
  enlace.href = url
  enlace.download = `reporte_${nombreEquipo.replaceAll(" ", "_")}.pdf`
  document.body.appendChild(enlace)
  enlace.click()
  document.body.removeChild(enlace)

  URL.revokeObjectURL(url)
}

function Reportes({ sesion, onCerrarSesion, onIrAResumen, onIrAConfiguracion, onIrALaboratorio, onSeleccionarEquipo }) {
  const { equipos } = useEquiposReales()

  const [equipoId, setEquipoId] = useState("")
  const [generando, setGenerando] = useState(false)
  const [mensaje, setMensaje] = useState("")
  const [reporteActual, setReporteActual] = useState(null)

  // Redaccion con IA (opcional): el backend informa si se puede usar (clave, modelo) y que se enviara.
  const estadoIA = useEstadoIA()
  const [conIA, setConIA] = useState(false)

  const [historial, setHistorial] = useState([])
  const [cargandoHistorial, setCargandoHistorial] = useState(true)
  const [seleccionados, setSeleccionados] = useState(new Set())

  function cargarHistorial() {
    setCargandoHistorial(true)
    apiFetch(`${URL_BASE}/api/reportes`)
      .then((respuesta) => {
        if (!respuesta.ok) throw new Error()
        return respuesta.json()
      })
      .then(setHistorial)
      .catch(() => setHistorial([]))
      .finally(() => setCargandoHistorial(false))
  }

  useEffect(cargarHistorial, [])

  async function generarReporte(evento) {
    evento.preventDefault()
    setMensaje("")
    setReporteActual(null)

    if (!equipoId) {
      setMensaje("Selecciona un equipo primero.")
      return
    }

    setGenerando(true)

    try {
      const respuesta = await apiFetch(`${URL_BASE}/api/reportes`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ equipo_id: Number(equipoId), con_ia: conIA && Boolean(estadoIA?.listo) }),
      })

      if (!respuesta.ok) {
        const detalle = await respuesta.json().catch(() => null)
        throw new Error(detalle?.detail ?? "No fue posible generar el reporte")
      }

      const reporte = await respuesta.json()
      setReporteActual(reporte)
      cargarHistorial()
    } catch (err) {
      setMensaje(err.message)
    } finally {
      setGenerando(false)
    }
  }

  async function eliminarReporte(reporte) {
    if (!window.confirm(`¿Eliminar el reporte de "${reporte.equipo_nombre}" del ${new Date(reporte.fecha_generacion).toLocaleString()}?`)) {
      return
    }
    await apiFetch(`${URL_BASE}/api/reportes/${reporte.id}`, { method: "DELETE" })
    cargarHistorial()
  }

  function alternarSeleccion(id) {
    setSeleccionados((actual) => {
      const siguiente = new Set(actual)
      if (siguiente.has(id)) {
        siguiente.delete(id)
      } else {
        siguiente.add(id)
      }
      return siguiente
    })
  }

  function alternarSeleccionarTodos() {
    setSeleccionados((actual) =>
      actual.size === historial.length ? new Set() : new Set(historial.map((r) => r.id))
    )
  }

  async function eliminarSeleccionados() {
    const cantidad = seleccionados.size
    if (cantidad === 0) return
    if (!window.confirm(`¿Eliminar los ${cantidad} reportes seleccionados? Esta acción no se puede deshacer.`)) {
      return
    }
    await apiFetch(`${URL_BASE}/api/reportes/eliminar-lote`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ reporte_ids: [...seleccionados] }),
    })
    setSeleccionados(new Set())
    cargarHistorial()
  }

  const iniciales = sesion.usuario.nombre
    .split(" ")
    .map((parte) => parte[0])
    .slice(0, 2)
    .join("")
    .toUpperCase()

  return (
    <div className="app-shell">
      <Sidebar
        vistaActiva="reportes"
        onIrAResumen={onIrAResumen}
        onIrAConfiguracion={onIrAConfiguracion}
        onIrAReportes={() => {}}
        onIrALaboratorio={onIrALaboratorio}
        equipoActivoId={null}
        onSeleccionarEquipo={onSeleccionarEquipo}
      />

      <div className="main-area">
        <header className="topbar">
          <p className="topbar-equipo">Reportes</p>

          <div className="topbar-user">
            <div className="usuario-avatar">{iniciales}</div>

            <div className="usuario-info">
              <strong>{sesion.usuario.nombre}</strong>
              <small>
                {sesion.usuario.rol === "administrador" ? "Administrador" : sesion.usuario.rol}
              </small>
            </div>

            <button type="button" className="boton-salir" onClick={onCerrarSesion}>
              SALIR
            </button>
          </div>
        </header>

        <main className="dashboard-content">
          <section className="tarjeta">
            <p className="config-nota">
              Diagnóstico basado en picos de 1x/2x/3x RPM (desbalanceo, desalineación angular y
              paralela) y, si el sensor tiene un rodamiento vinculado con geometría completa, en su
              espectro de envolvente (pista exterior, pista interior, elemento rodante, jaula —
              incluyendo bandas laterales en pista interior y elemento rodante) — contra{" "}
              <code>conocimiento/normativa_motorguardian.yaml</code>. No incluye todavía engranajes,
              kurtosis, filtro de banda pasante en la envolvente, ni línea base histórica — ver
              limitaciones en cada resultado.
            </p>

            <form className="config-form" onSubmit={generarReporte}>
              <div className="config-form-campo">
                <label>Equipo</label>
                <select value={equipoId} onChange={(e) => setEquipoId(e.target.value)} required>
                  <option value="" disabled>Selecciona un equipo</option>
                  {equipos.map((equipo) => (
                    <option key={equipo.id} value={equipo.id}>{equipo.nombre}</option>
                  ))}
                </select>
              </div>

              <InterruptorIA estadoIA={estadoIA} activado={conIA} onCambio={setConIA} deshabilitado={generando} />

              <div className="config-form-acciones">
                <button type="submit" className="config-boton-primario" disabled={generando}>
                  {generando ? "Generando…" : "Generar reporte"}
                </button>
              </div>

              {mensaje && <p className="config-error">{mensaje}</p>}
            </form>
          </section>

          {reporteActual && (
            <section className="tarjeta">
              <div className="reporte-encabezado">
                <div>
                  <h2>{reporteActual.resultado.equipo.nombre}</h2>
                  <p className="config-mensaje">
                    {reporteActual.resultado.equipo.tipo ?? "—"} · Planta:{" "}
                    {reporteActual.resultado.equipo.planta ?? "—"} · RPM nominal:{" "}
                    {reporteActual.resultado.equipo.rpm_nominal} · Generado:{" "}
                    {reporteActual.resultado.fecha_generacion}
                  </p>
                </div>

                <div className="reporte-encabezado-acciones">
                  <button
                    type="button"
                    className="config-boton-primario"
                    onClick={() => descargarPdf(reporteActual.id, reporteActual.equipo_nombre)}
                  >
                    Descargar PDF
                  </button>

                  <button
                    type="button"
                    className="reporte-boton-cerrar"
                    onClick={() => setReporteActual(null)}
                    aria-label="Cerrar diagnóstico"
                    title="Cerrar"
                  >
                    ×
                  </button>
                </div>
              </div>

              {reporteActual.resultado.sensores.map((sensor) => (
                <TarjetaSensor key={sensor.sensor_id} sensor={sensor} />
              ))}

              {reporteActual.resultado.resumen_ia && (
                <div className="reporte-resumen-ia">
                  <h3>Resumen redactado por IA</h3>
                  <p className="config-mensaje">
                    Redactado con inteligencia artificial (modelo {reporteActual.resultado.resumen_ia.modelo}). No
                    modifica el diagnóstico ni las cifras; debe revisarlo el analista.
                  </p>
                  {reporteActual.resultado.resumen_ia.resumen
                    .split("\n")
                    .filter((parrafo) => parrafo.trim())
                    .map((parrafo, indice) => (
                      <p key={indice}>{parrafo}</p>
                    ))}
                  <h4>Observaciones de la IA</h4>
                  {reporteActual.resultado.resumen_ia.observaciones.length > 0 ? (
                    <ul>
                      {reporteActual.resultado.resumen_ia.observaciones.map((observacion, indice) => (
                        <li key={indice}>{observacion}</li>
                      ))}
                    </ul>
                  ) : (
                    <p className="config-mensaje">La IA no encontró aspectos que advertir.</p>
                  )}
                </div>
              )}

              {reporteActual.resultado.aviso_ia && (
                <p className="config-error">
                  El reporte se generó sin la página de IA: {reporteActual.resultado.aviso_ia}
                </p>
              )}
            </section>
          )}

          <section className="tarjeta">
            <div className="reporte-encabezado">
              <h3>Historial de reportes</h3>
              {seleccionados.size > 0 && (
                <button type="button" className="config-boton-secundario" onClick={eliminarSeleccionados}>
                  Eliminar seleccionados ({seleccionados.size})
                </button>
              )}
            </div>

            {cargandoHistorial && <p className="config-mensaje">Cargando…</p>}

            {!cargandoHistorial && historial.length === 0 && (
              <p className="config-mensaje">Todavía no se ha generado ningún reporte.</p>
            )}

            {historial.length > 0 && (
              <table className="config-tabla">
                <thead>
                  <tr>
                    <th>
                      <label className="config-checkbox" title="Seleccionar todos">
                        <input
                          type="checkbox"
                          checked={historial.length > 0 && seleccionados.size === historial.length}
                          onChange={alternarSeleccionarTodos}
                        />
                        Todos
                      </label>
                    </th>
                    <th>Equipo</th>
                    <th>Fecha</th>
                    <th>Hipótesis</th>
                    <th></th>
                  </tr>
                </thead>
                <tbody>
                  {historial.map((reporte) => (
                    <tr key={reporte.id}>
                      <td>
                        <input
                          type="checkbox"
                          checked={seleccionados.has(reporte.id)}
                          onChange={() => alternarSeleccion(reporte.id)}
                        />
                      </td>
                      <td>{reporte.equipo_nombre}</td>
                      <td>{new Date(reporte.fecha_generacion).toLocaleString()}</td>
                      <td>{reporte.cantidad_hipotesis}</td>
                      <td className="config-tabla-acciones">
                        <button type="button" onClick={() => descargarPdf(reporte.id, reporte.equipo_nombre)}>
                          Descargar PDF
                        </button>
                        <button type="button" onClick={() => eliminarReporte(reporte)}>
                          Eliminar
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </section>
        </main>
      </div>
    </div>
  )
}

export default Reportes
