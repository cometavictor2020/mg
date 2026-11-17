import { useEffect, useRef, useState } from "react"
import {
  CartesianGrid,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts"

import ComparacionPSO from "../components/ComparacionPSO"
import GraficoEnvolvente from "../components/GraficoEnvolvente"
import InterruptorIA from "../components/InterruptorIA"
import Sidebar from "../components/Sidebar"
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

// Mapea el nombre de falla de una hipótesis a la clave de
// resultado.grafico.frecuencias_falla correspondiente, para poder
// ofrecer "qué frecuencia optimizar" ordenado por la misma prioridad
// (confianza) con la que el motor ya ordena las hipótesis - sin tocar
// el backend, resultado.hipotesis ya viene ordenado por confianza.
const FALLA_A_FRECUENCIA = {
  rodamiento_pista_exterior: "BPFO",
  rodamiento_pista_interior: "BPFI",
  rodamiento_elemento_rodante: "BSF",
  rodamiento_jaula: "FTF",
}

function nivelConfianza(confianza) {
  if (confianza >= 0.7) return "alta"
  if (confianza >= 0.5) return "media"
  return "baja"
}

function TablaMetadata({ variables }) {
  return (
    <table className="config-tabla">
      <thead>
        <tr>
          <th>Variable</th>
          <th>Forma</th>
          <th>Tipo de dato</th>
          <th>Elementos</th>
          <th>Vista previa</th>
        </tr>
      </thead>
      <tbody>
        {variables.map((variable) => (
          <tr key={variable.nombre}>
            <td>
              <code>{variable.nombre}</code>
            </td>
            <td>{variable.forma.join(" × ") || "escalar"}</td>
            <td>{variable.tipo_dato}</td>
            <td>{variable.cantidad_elementos}</td>
            <td>
              {variable.vista_previa
                ? `${variable.vista_previa.join(", ")}${variable.cantidad_elementos > 10 ? "…" : ""}`
                : "—"}
              {variable.minimo !== undefined && (
                <> (mín {variable.minimo}, máx {variable.maximo})</>
              )}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}

function EspectroCrudo({ grafico, espectroCrudo }) {
  return (
    <div className="reporte-grafico-rodamiento">
      <p className="config-mensaje">
        Espectro FFT crudo (0–5000 Hz) — así se ve la señal sin demodular. El pico directo en
        la frecuencia de falla suele quedar oculto entre la energía de resonancia de alta
        frecuencia, tal como muestra la Figura 2 del paper; por eso hace falta la envolvente.
      </p>

      <div style={{ width: "100%", height: "280px" }}>
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={espectroCrudo} margin={{ top: 40, right: 16, bottom: 5, left: 0 }}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis
              dataKey="frecuencia"
              type="number"
              domain={[0, 5000]}
              label={{ value: "Frecuencia [Hz]", position: "insideBottom", offset: -5 }}
            />
            <YAxis label={{ value: "Amplitud", angle: -90, position: "insideLeft" }} />
            <Tooltip formatter={(valor) => Number(valor).toFixed(4)} labelFormatter={(valor) => `${valor} Hz`} />
            <Line
              type="linear"
              dataKey="amplitud"
              name="Espectro crudo"
              stroke="#94a3b8"
              dot={false}
              strokeWidth={1}
              isAnimationActive={false}
            />
            {Object.entries(grafico.frecuencias_falla)
              .sort(([, a], [, b]) => a - b)
              .map(([nombre, frecuencia], indice) => (
                <ReferenceLine
                  key={nombre}
                  x={frecuencia}
                  stroke="#94a3b8"
                  strokeDasharray="4 4"
                  label={{
                    value: `${nombre} ${frecuencia.toFixed(1)} Hz`,
                    position: "top",
                    offset: indice % 2 === 0 ? 8 : 22,
                    fontSize: 10,
                    fill: "#475569",
                  }}
                />
              ))}
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  )
}

function Laboratorio({ sesion, onCerrarSesion, onIrAResumen, onIrAConfiguracion, onIrAReportes, onSeleccionarEquipo }) {
  const [archivo, setArchivo] = useState(null)
  const [frecuenciaMuestreo, setFrecuenciaMuestreo] = useState("48000")
  const [variableSeñal, setVariableSeñal] = useState("")
  const [variableRpm, setVariableRpm] = useState("")
  // D-060: archivos que declaran su propia frecuencia de muestreo y/o su
  // velocidad en Hz (ej. los del MFPT: bearing.sr y bearing.rate).
  const [variableFrecuencia, setVariableFrecuencia] = useState("")
  const [unidadRpm, setUnidadRpm] = useState("rpm")
  const [sugerencias, setSugerencias] = useState(null)
  const [rpm, setRpm] = useState("")
  const [numeroElementosRodantes, setNumeroElementosRodantes] = useState("9")
  const [diametroElementoMm, setDiametroElementoMm] = useState("7.94")
  const [diametroPasoMm, setDiametroPasoMm] = useState("39.04")
  const [anguloContactoGrados, setAnguloContactoGrados] = useState("0")

  const [metadata, setMetadata] = useState(null)
  const [cargandoMetadata, setCargandoMetadata] = useState(false)
  const [errorMetadata, setErrorMetadata] = useState("")

  const [analizando, setAnalizando] = useState(false)
  const [error, setError] = useState("")

  // Reporte PDF del archivo (con redaccion de IA opcional)
  const estadoIA = useEstadoIA()
  const [conIA, setConIA] = useState(false)
  const [generandoReporte, setGenerandoReporte] = useState(false)
  const [mensajeReporte, setMensajeReporte] = useState("")
  const [resultado, setResultado] = useState(null)

  const [usarPso, setUsarPso] = useState(false)
  const [frecuenciaObjetivoPso, setFrecuenciaObjetivoPso] = useState("")
  const [ejecutandoPso, setEjecutandoPso] = useState(false)
  const [progresoPso, setProgresoPso] = useState(0)
  const [resultadoPso, setResultadoPso] = useState(null)
  const [errorPso, setErrorPso] = useState("")
  const intervaloPsoRef = useRef(null)

  useEffect(() => {
    return () => clearInterval(intervaloPsoRef.current)
  }, [])

  function elegirArchivo(nuevoArchivo) {
    setArchivo(nuevoArchivo)
    setMetadata(null)
    setErrorMetadata("")
    setVariableSeñal("")
    setVariableRpm("")
    setVariableFrecuencia("")
    setUnidadRpm("rpm")
    setSugerencias(null)
  }

  // Aplica lo que el sistema sugirio al leer la metadata. Nada se aplica
  // solo: quien sube el archivo lo confirma con este boton y puede cambiarlo.
  function aplicarSugerencias() {
    if (!sugerencias) return
    if (sugerencias.variable_señal) setVariableSeñal(sugerencias.variable_señal)
    if (sugerencias.variable_frecuencia_muestreo) setVariableFrecuencia(sugerencias.variable_frecuencia_muestreo)
    if (sugerencias.variable_rpm) {
      setVariableRpm(sugerencias.variable_rpm)
      setUnidadRpm(sugerencias.unidad_rpm ?? "rpm")
    }
  }

  const hayAlgunaSugerencia =
    sugerencias &&
    (sugerencias.variable_señal || sugerencias.variable_frecuencia_muestreo || sugerencias.variable_rpm)

  // Lista de candidatas a optimizar, ordenada por prioridad (misma
  // confianza con la que el motor ya ordena las hipótesis) — derivada
  // en el frontend de datos que /analizar-mat ya entrega, sin pedirle
  // nada nuevo al backend.
  const candidatosPso = (resultado?.hipotesis ?? [])
    .filter((h) => FALLA_A_FRECUENCIA[h.falla])
    .map((h) => ({
      falla: h.falla,
      etiqueta: ETIQUETAS_FALLA[h.falla] ?? h.falla,
      confianza: h.confianza,
      claveFrecuencia: FALLA_A_FRECUENCIA[h.falla],
      frecuencia: resultado.grafico.frecuencias_falla[FALLA_A_FRECUENCIA[h.falla]],
    }))

  async function iniciarPso() {
    const candidata = candidatosPso.find((c) => c.claveFrecuencia === frecuenciaObjetivoPso)
    if (!candidata) {
      setErrorPso("Elige qué frecuencia optimizar.")
      return
    }

    setErrorPso("")
    setResultadoPso(null)
    setProgresoPso(0)
    setEjecutandoPso(true)

    try {
      const formulario = new FormData()
      formulario.append("archivo", archivo)
      // La frecuencia que realmente uso el analisis (manual o la del archivo).
      formulario.append("frecuencia_muestreo", resultado?.frecuencia_muestreo ?? frecuenciaMuestreo)
      formulario.append("frecuencia_objetivo", candidata.frecuencia)
      if (variableSeñal) formulario.append("variable_señal", variableSeñal)
      formulario.append("enjambre", "30")
      formulario.append("iteraciones", "30")

      const respuestaInicio = await apiFetch(`${URL_BASE}/api/laboratorio/pso/iniciar`, {
        method: "POST",
        body: formulario,
      })

      if (!respuestaInicio.ok) {
        const detalle = await respuestaInicio.json().catch(() => null)
        throw new Error(detalle?.detail ?? "No fue posible iniciar la optimización PSO")
      }

      const { job_id: jobId } = await respuestaInicio.json()

      intervaloPsoRef.current = setInterval(async () => {
        try {
          const respuestaEstado = await apiFetch(`${URL_BASE}/api/laboratorio/pso/estado/${jobId}`)
          if (!respuestaEstado.ok) throw new Error("No fue posible consultar el avance del trabajo PSO")

          const trabajo = await respuestaEstado.json()
          setProgresoPso(trabajo.progreso)

          if (trabajo.estado === "completado") {
            clearInterval(intervaloPsoRef.current)
            setResultadoPso(trabajo.resultado)
            setEjecutandoPso(false)
          } else if (trabajo.estado === "error") {
            clearInterval(intervaloPsoRef.current)
            setErrorPso(trabajo.error ?? "La optimización PSO terminó con un error")
            setEjecutandoPso(false)
          }
        } catch (err) {
          clearInterval(intervaloPsoRef.current)
          setErrorPso(err.message)
          setEjecutandoPso(false)
        }
      }, 3000)
    } catch (err) {
      setErrorPso(err.message)
      setEjecutandoPso(false)
    }
  }

  async function verMetadata() {
    if (!archivo) {
      setErrorMetadata("Selecciona un archivo .mat primero.")
      return
    }

    setCargandoMetadata(true)
    setErrorMetadata("")
    try {
      const formulario = new FormData()
      formulario.append("archivo", archivo)

      const respuesta = await apiFetch(`${URL_BASE}/api/laboratorio/inspeccionar-mat`, {
        method: "POST",
        body: formulario,
      })

      if (!respuesta.ok) {
        const detalle = await respuesta.json().catch(() => null)
        throw new Error(detalle?.detail ?? "No fue posible leer la metadata del archivo")
      }

      const datos = await respuesta.json()
      setMetadata(datos.variables)
      setSugerencias(datos.sugerencias ?? null)
    } catch (err) {
      setErrorMetadata(err.message)
    } finally {
      setCargandoMetadata(false)
    }
  }

  // Los mismos datos del formulario sirven para analizar y para generar el reporte.
  function construirFormulario() {
    const formulario = new FormData()
    formulario.append("archivo", archivo)
    if (variableFrecuencia) {
      formulario.append("variable_frecuencia_muestreo", variableFrecuencia)
    } else {
      formulario.append("frecuencia_muestreo", frecuenciaMuestreo)
    }
    if (variableSeñal) formulario.append("variable_señal", variableSeñal)
    if (variableRpm) {
      formulario.append("variable_rpm", variableRpm)
      formulario.append("unidad_variable_rpm", unidadRpm)
    }
    if (rpm) formulario.append("rpm", rpm)
    formulario.append("numero_elementos_rodantes", numeroElementosRodantes)
    formulario.append("diametro_elemento_mm", diametroElementoMm)
    formulario.append("diametro_paso_mm", diametroPasoMm)
    formulario.append("angulo_contacto_grados", anguloContactoGrados)
    return formulario
  }

  // Descarga un PDF de diagnostico del archivo cargado. No guarda nada: ni en la base de datos ni en el servidor.
  async function generarReporte() {
    setError("")
    setMensajeReporte("")

    if (!archivo) {
      setError("Selecciona un archivo .mat.")
      return
    }

    const formulario = construirFormulario()
    const pedirIA = conIA && Boolean(estadoIA?.listo)
    formulario.append("con_ia", pedirIA ? "true" : "false")

    setGenerandoReporte(true)
    try {
      const respuesta = await apiFetch(`${URL_BASE}/api/laboratorio/reporte-mat`, {
        method: "POST",
        body: formulario,
      })

      if (!respuesta.ok) {
        const detalle = await respuesta.json().catch(() => null)
        throw new Error(detalle?.detail ?? "No fue posible generar el reporte")
      }

      const aviso = respuesta.headers.get("X-Aviso-IA")
      const conResumenIA = respuesta.headers.get("X-Con-IA") === "1"

      const blob = await respuesta.blob()
      const url = URL.createObjectURL(blob)
      const enlace = document.createElement("a")
      enlace.href = url
      enlace.download = `reporte_${archivo.name.replace(/\.mat$/i, "")}.pdf`
      document.body.appendChild(enlace)
      enlace.click()
      enlace.remove()
      URL.revokeObjectURL(url)

      setMensajeReporte(
        aviso
          ? `Reporte descargado sin la página de IA: ${decodeURIComponent(aviso)}`
          : conResumenIA
            ? "Reporte descargado, con la página «Resumen redactado por IA». No se guardó nada en el sistema."
            : "Reporte descargado. No se guardó nada en el sistema.",
      )
    } catch (err) {
      setError(err.message)
    } finally {
      setGenerandoReporte(false)
    }
  }

  async function analizar(evento) {
    evento.preventDefault()
    setError("")
    setResultado(null)
    clearInterval(intervaloPsoRef.current)
    setUsarPso(false)
    setFrecuenciaObjetivoPso("")
    setEjecutandoPso(false)
    setProgresoPso(0)
    setResultadoPso(null)
    setErrorPso("")

    if (!archivo) {
      setError("Selecciona un archivo .mat.")
      return
    }

    const formulario = construirFormulario()

    setAnalizando(true)
    try {
      const respuesta = await apiFetch(`${URL_BASE}/api/laboratorio/analizar-mat`, {
        method: "POST",
        body: formulario,
      })

      if (!respuesta.ok) {
        const detalle = await respuesta.json().catch(() => null)
        throw new Error(detalle?.detail ?? "No fue posible analizar el archivo")
      }

      setResultado(await respuesta.json())
    } catch (err) {
      setError(err.message)
    } finally {
      setAnalizando(false)
    }
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
        vistaActiva="laboratorio"
        onIrAResumen={onIrAResumen}
        onIrAConfiguracion={onIrAConfiguracion}
        onIrAReportes={onIrAReportes}
        onIrALaboratorio={() => {}}
        equipoActivoId={null}
        onSeleccionarEquipo={onSeleccionarEquipo}
      />

      <div className="main-area">
        <header className="topbar">
          <p className="topbar-equipo">Laboratorio</p>

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
              Analiza cualquier archivo <code>.mat</code> de Matlab con el mismo motor de
              diagnóstico de rodamientos que usa el resto de la aplicación — sirve para validar
              el motor contra casos con resultado ya publicado (por ejemplo, del CWRU Bearing
              Data Center), sin registrar nada en la base de datos ni depender de un equipo real.
              No asume ninguna estructura fija: revisa la metadata del archivo, elige qué
              variable analizar y con qué geometría de rodamiento.
            </p>

            <form className="config-form" onSubmit={analizar}>
              <div className="config-form-campo config-form-campo-ancho">
                <label>Archivo .mat</label>
                <input
                  type="file"
                  accept=".mat"
                  onChange={(e) => elegirArchivo(e.target.files?.[0] ?? null)}
                  required
                />
              </div>

              <div className="config-form-campo config-form-campo-ancho">
                <button type="button" className="config-boton-secundario" onClick={verMetadata} disabled={cargandoMetadata}>
                  {cargandoMetadata ? "Leyendo…" : "Ver metadata del archivo"}
                </button>

                {errorMetadata && <p className="config-error">{errorMetadata}</p>}

                {metadata && (
                  <div style={{ marginTop: "10px" }}>
                    <p className="config-mensaje">
                      Variables encontradas en el archivo — elige cuáles usar más abajo (si no
                      eliges ninguna, se intenta autodetectar la convención de nombres de CWRU).
                    </p>
                    <TablaMetadata variables={metadata} />

                    {hayAlgunaSugerencia && (
                      <div className="reporte-limitaciones" style={{ marginTop: "10px" }}>
                        <p className="config-mensaje">
                          <strong>Sugerencia del sistema</strong> (no se aplica sola; confírmala o cámbiala abajo):
                        </p>
                        <ul>
                          {sugerencias.variable_señal && (
                            <li>Señal: <code>{sugerencias.variable_señal}</code></li>
                          )}
                          {sugerencias.variable_frecuencia_muestreo && (
                            <li>
                              Frecuencia de muestreo: <code>{sugerencias.variable_frecuencia_muestreo}</code> (
                              {sugerencias.valores?.frecuencia_muestreo} Hz)
                            </li>
                          )}
                          {sugerencias.variable_rpm && (
                            <li>
                              Velocidad de giro: <code>{sugerencias.variable_rpm}</code> ({sugerencias.valores?.velocidad}{" "}
                              {sugerencias.unidad_rpm === "hz" ? "Hz" : "r/min"})
                            </li>
                          )}
                          {(sugerencias.notas ?? []).map((nota) => (
                            <li key={nota} className="config-nota">{nota}</li>
                          ))}
                        </ul>
                        <button type="button" className="config-boton-secundario" onClick={aplicarSugerencias}>
                          Usar esta sugerencia
                        </button>
                      </div>
                    )}
                  </div>
                )}
              </div>

              <div className="config-form-campo">
                <label>Variable de señal (opcional — si se deja vacío, se autodetecta)</label>
                <select value={variableSeñal} onChange={(e) => setVariableSeñal(e.target.value)}>
                  <option value="">Autodetectar (*_DE_time / *_FE_time)</option>
                  {(metadata ?? []).map((variable) => (
                    <option key={variable.nombre} value={variable.nombre}>{variable.nombre}</option>
                  ))}
                </select>
              </div>

              <div className="config-form-campo">
                <label>Variable de RPM (opcional — si se deja vacío, se autodetecta)</label>
                <select value={variableRpm} onChange={(e) => setVariableRpm(e.target.value)}>
                  <option value="">Autodetectar (*RPM)</option>
                  {(metadata ?? []).map((variable) => (
                    <option key={variable.nombre} value={variable.nombre}>{variable.nombre}</option>
                  ))}
                </select>
              </div>

              {metadata && (
                <>
                  <div className="config-form-campo">
                    <label>Variable de frecuencia de muestreo (opcional — si la eliges, se usa la del archivo)</label>
                    <select value={variableFrecuencia} onChange={(e) => setVariableFrecuencia(e.target.value)}>
                      <option value="">No: indicar el valor manualmente</option>
                      {metadata
                        .filter((variable) => variable.cantidad_elementos === 1 && variable.vista_previa)
                        .map((variable) => (
                          <option key={variable.nombre} value={variable.nombre}>
                            {variable.nombre} ({variable.vista_previa[0]})
                          </option>
                        ))}
                    </select>
                  </div>

                  {variableRpm && (
                    <div className="config-form-campo">
                      <label>Unidad de la variable de velocidad</label>
                      <select value={unidadRpm} onChange={(e) => setUnidadRpm(e.target.value)}>
                        <option value="rpm">r/min (RPM)</option>
                        <option value="hz">Hz (revoluciones por segundo)</option>
                      </select>
                    </div>
                  )}
                </>
              )}

              <div className="config-form-campo">
                <label>Frecuencia de muestreo (Hz){variableFrecuencia ? " — tomada del archivo" : ""}</label>
                <input
                  type="number"
                  step="1"
                  min="1"
                  value={frecuenciaMuestreo}
                  onChange={(e) => setFrecuenciaMuestreo(e.target.value)}
                  disabled={Boolean(variableFrecuencia)}
                  required={!variableFrecuencia}
                />
              </div>

              <div className="config-form-campo">
                <label>RPM manual (opcional — si se deja vacío, se usa el RPM del archivo)</label>
                <input
                  type="number"
                  step="any"
                  value={rpm}
                  onChange={(e) => setRpm(e.target.value)}
                />
              </div>

              <details className="reporte-limitaciones config-form-campo-ancho">
                <summary>Geometría del rodamiento (valores de ejemplo — edítalos según el rodamiento de tu archivo)</summary>

                <div className="config-form" style={{ marginTop: "10px" }}>
                  <p className="config-nota config-form-campo-ancho">
                    Las frecuencias de falla solo dependen de la proporción entre el diámetro del elemento y el de
                    paso: si tu rodamiento viene en otra unidad (por ejemplo pulgadas), ingresa ambos en esa misma
                    unidad.
                  </p>

                  <div className="config-form-campo">
                    <label>Número de elementos rodantes</label>
                    <input
                      type="number"
                      step="1"
                      min="1"
                      value={numeroElementosRodantes}
                      onChange={(e) => setNumeroElementosRodantes(e.target.value)}
                      required
                    />
                  </div>
                  <div className="config-form-campo">
                    <label>Diámetro del elemento (mm)</label>
                    <input
                      type="number"
                      step="any"
                      value={diametroElementoMm}
                      onChange={(e) => setDiametroElementoMm(e.target.value)}
                      required
                    />
                  </div>
                  <div className="config-form-campo">
                    <label>Diámetro de paso (mm)</label>
                    <input
                      type="number"
                      step="any"
                      value={diametroPasoMm}
                      onChange={(e) => setDiametroPasoMm(e.target.value)}
                      required
                    />
                  </div>
                  <div className="config-form-campo">
                    <label>Ángulo de contacto (grados)</label>
                    <input
                      type="number"
                      step="any"
                      value={anguloContactoGrados}
                      onChange={(e) => setAnguloContactoGrados(e.target.value)}
                      required
                    />
                  </div>
                </div>
              </details>

              {error && <p className="config-error">{error}</p>}
              {mensajeReporte && <p className="config-mensaje">{mensajeReporte}</p>}

              <InterruptorIA
                estadoIA={estadoIA}
                activado={conIA}
                onCambio={setConIA}
                deshabilitado={generandoReporte}
                sujeto="del archivo"
              />

              <div className="config-form-acciones">
                <button type="submit" className="config-boton-primario" disabled={analizando || generandoReporte}>
                  {analizando ? "Analizando…" : "Analizar"}
                </button>
                <button
                  type="button"
                  className="config-boton-secundario"
                  onClick={generarReporte}
                  disabled={analizando || generandoReporte || !archivo}
                >
                  {generandoReporte ? "Generando reporte…" : "Generar reporte (PDF)"}
                </button>
              </div>
            </form>
          </section>

          {resultado && (
            <section className="tarjeta">
              <h3>Resultado</h3>
              <p className="config-mensaje">
                Variable leída: <code>{resultado.variable_señal}</code> · RPM: {resultado.rpm} ·
                Frecuencia de muestreo: {resultado.frecuencia_muestreo} Hz
                {resultado.origen_frecuencia_muestreo && resultado.origen_frecuencia_muestreo !== "manual" && (
                  <> (del archivo: <code>{resultado.origen_frecuencia_muestreo}</code>)</>
                )}{" "}
                · Muestras: {resultado.cantidad_muestras}
              </p>

              {resultado.hipotesis.length === 0 && (
                <p className="config-mensaje">
                  No se encontraron hipótesis de falla con confianza suficiente.
                </p>
              )}

              {resultado.hipotesis.map((hipotesis) => (
                <div key={hipotesis.falla} className="reporte-hipotesis">
                  <div className="reporte-hipotesis-encabezado">
                    <strong>{ETIQUETAS_FALLA[hipotesis.falla] ?? hipotesis.falla}</strong>
                    <span className={`reporte-confianza reporte-confianza-${nivelConfianza(hipotesis.confianza)}`}>
                      {Math.round(hipotesis.confianza * 100)}% de confianza
                    </span>
                  </div>
                  <p className="config-mensaje">Evidencia: {hipotesis.evidencias.join(", ")}</p>
                </div>
              ))}

              {resultado.grafico && (
                <>
                  <EspectroCrudo grafico={resultado.grafico} espectroCrudo={resultado.espectro_crudo} />
                  <GraficoEnvolvente grafico={resultado.grafico} />
                </>
              )}

              {candidatosPso.length > 0 && (
                <div className="reporte-grafico-rodamiento">
                  <label>
                    <input type="checkbox" checked={usarPso} onChange={(e) => setUsarPso(e.target.checked)} />
                    {" "}Usar PSO para optimizar la ventana de filtro pasa-banda (más preciso, pero puede tardar
                    varios minutos — 30 partículas × 30 iteraciones)
                  </label>

                  {usarPso && (
                    <div className="config-form" style={{ marginTop: "10px" }}>
                      <div className="config-form-campo config-form-campo-ancho">
                        <label>Frecuencia a optimizar (ordenadas por confianza de la hipótesis)</label>
                        <select value={frecuenciaObjetivoPso} onChange={(e) => setFrecuenciaObjetivoPso(e.target.value)}>
                          <option value="" disabled>Elige una frecuencia</option>
                          {candidatosPso.map((candidata) => (
                            <option key={candidata.claveFrecuencia} value={candidata.claveFrecuencia}>
                              {candidata.claveFrecuencia} — {candidata.etiqueta} — {Math.round(candidata.confianza * 100)}%
                              de confianza — {candidata.frecuencia.toFixed(1)} Hz
                            </option>
                          ))}
                        </select>
                      </div>

                      <div className="config-form-acciones">
                        <button
                          type="button"
                          className="config-boton-primario"
                          onClick={iniciarPso}
                          disabled={ejecutandoPso || !frecuenciaObjetivoPso}
                        >
                          {ejecutandoPso ? "Optimizando…" : "Optimizar con PSO"}
                        </button>
                      </div>

                      {ejecutandoPso && (
                        <div className="config-form-campo-ancho">
                          <progress value={progresoPso} max={1} style={{ width: "100%" }} />
                          <p className="config-mensaje">{Math.round(progresoPso * 100)}% completado</p>
                        </div>
                      )}

                      {errorPso && <p className="config-error">{errorPso}</p>}

                      {resultadoPso && (
                        <ComparacionPSO
                          resultado={resultadoPso}
                          etiquetaFrecuencia={
                            candidatosPso.find((c) => c.claveFrecuencia === frecuenciaObjetivoPso)?.claveFrecuencia
                          }
                        />
                      )}
                    </div>
                  )}
                </div>
              )}
            </section>
          )}
        </main>
      </div>
    </div>
  )
}

export default Laboratorio
