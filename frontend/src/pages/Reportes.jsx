import { useEffect, useState } from "react"

import GraficoEnvolvente from "../components/GraficoEnvolvente"
import Sidebar from "../components/Sidebar"
import { useEquiposReales } from "../hooks/useEquiposReales"
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

function TarjetaSensor({ sensor }) {
  return (
    <article className="tarjeta reporte-sensor">
      <h3>{sensor.nombre_tipo}</h3>

      {!sensor.tiene_medicion && <p className="config-mensaje">{sensor.mensaje}</p>}

      {sensor.tiene_medicion && (
        <>
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

function Reportes({ sesion, onCerrarSesion, onIrAResumen, onIrAConfiguracion, onSeleccionarEquipo }) {
  const { equipos } = useEquiposReales()

  const [equipoId, setEquipoId] = useState("")
  const [generando, setGenerando] = useState(false)
  const [mensaje, setMensaje] = useState("")
  const [reporteActual, setReporteActual] = useState(null)

  const [historial, setHistorial] = useState([])
  const [cargandoHistorial, setCargandoHistorial] = useState(true)

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
        body: JSON.stringify({ equipo_id: Number(equipoId) }),
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
            </section>
          )}

          <section className="tarjeta">
            <h3>Historial de reportes</h3>

            {cargandoHistorial && <p className="config-mensaje">Cargando…</p>}

            {!cargandoHistorial && historial.length === 0 && (
              <p className="config-mensaje">Todavía no se ha generado ningún reporte.</p>
            )}

            {historial.length > 0 && (
              <table className="config-tabla">
                <thead>
                  <tr>
                    <th>Equipo</th>
                    <th>Fecha</th>
                    <th>Hipótesis</th>
                    <th></th>
                  </tr>
                </thead>
                <tbody>
                  {historial.map((reporte) => (
                    <tr key={reporte.id}>
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
