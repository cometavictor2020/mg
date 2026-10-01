import { useEffect, useMemo, useRef, useState } from "react"
import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts"

import ComparacionPSO from "../components/ComparacionPSO"
import GraficoEnvolvente from "../components/GraficoEnvolvente"
import ModalCargaMedicion from "../components/ModalCargaMedicion"
import Sidebar from "../components/Sidebar"
import { dashboardDemo } from "../data/dashboardDemo"
import { useEquiposReales } from "../hooks/useEquiposReales"
import { apiFetch } from "../utils/apiFetch"

const ESTADISTICOS_VACIOS = {
  curtosis: [],
  factor_cresta: [],
  skewness: [],
}

const ETIQUETAS_FALLA = {
  desbalanceo: "Desbalanceo",
  desalineacion_angular: "Desalineación angular",
  desalineacion_paralela: "Desalineación paralela",
  rodamiento_pista_exterior: "Rodamiento — pista exterior (BPFO)",
  rodamiento_pista_interior: "Rodamiento — pista interior (BPFI)",
  rodamiento_elemento_rodante: "Rodamiento — elemento rodante (BSF)",
  rodamiento_jaula: "Rodamiento — jaula (FTF)",
}

// Mismos umbrales que Reportes.jsx/Laboratorio.jsx (nivelConfianza) -
// una hipotesis de alta confianza es la que dispara la alerta roja.
function nivelAlertaDe(confianza) {
  if (confianza >= 0.7) return "alta"
  if (confianza >= 0.5) return "media"
  return "baja"
}

// Zonas C/D de ISO 20816-3 son las que ISO clasifica como "alerta"/"critica"
// (ver significado_zonas en normativa_motorguardian.yaml) - mismo criterio
// visual (alta/media/baja) que ya usa la confianza de las hipotesis de falla.
function nivelSeveridadIsoDe(zona) {
  if (zona === "D") return "alta"
  if (zona === "C") return "media"
  return "baja"
}

// Mismo mapeo que Laboratorio.jsx: de la falla de una hipotesis a la
// clave de frecuencias_falla correspondiente, para poder ofrecer "que
// frecuencia optimizar con PSO" ordenado por la misma confianza con la
// que ya vienen las hipotesis del rodamiento (D-049, ver PROYECTO.md).
const FALLA_A_FRECUENCIA = {
  rodamiento_pista_exterior: "BPFO",
  rodamiento_pista_interior: "BPFI",
  rodamiento_elemento_rodante: "BSF",
  rodamiento_jaula: "FTF",
}

function AnalizadorVibraciones({
  sesion,
  onCerrarSesion,
  onIrAResumen,
  onIrAConfiguracion,
  onIrAReportes,
  onIrALaboratorio,
  equipoInicialId,
}) {
  const { equipos, cargando: cargandoEquipos } = useEquiposReales()

  const [equipoSeleccionadoId, setEquipoSeleccionadoId] = useState(
    equipoInicialId ?? null
  )

  useEffect(() => {
    if (equipoSeleccionadoId === null && equipos.length > 0) {
      setEquipoSeleccionadoId(equipos[0].id)
    }
  }, [equipos, equipoSeleccionadoId])

  const [pestanaActiva, setPestanaActiva] = useState("tiempo")
  const [mensajeBackend, setMensajeBackend] = useState("")
  const [mensajeFFT, setMensajeFFT] = useState("")
  const [mensajeEstadisticos, setMensajeEstadisticos] = useState("")
  const [datos, setDatos] = useState([])
  const [datosFFT, setDatosFFT] = useState([])
  // Tope real del espectro (D-049): antes fijo en 300 Hz, ahora lo
  // informa el backend (Nyquist real de la medicion, con
  // rango_completo=true) para que el eje del gráfico se adapte solo.
  const [frecuenciaMaximaFFT, setFrecuenciaMaximaFFT] = useState(300)
  const [datosEstadisticos, setDatosEstadisticos] = useState(
    ESTADISTICOS_VACIOS
  )
  const [mostrandoCargaMedicion, setMostrandoCargaMedicion] = useState(false)
  const [recargarContador, setRecargarContador] = useState(0)
  const [datosEnvolvente, setDatosEnvolvente] = useState(null)
  const [mensajeEnvolvente, setMensajeEnvolvente] = useState("")

  // Alerta automatica (D-048, ver PROYECTO.md): se calcula al entrar al
  // detalle de este equipo puntual (no para todos los equipos del
  // Resumen General - costo medido y documentado en BITACORA.md).
  // Evalua TODOS los sensores del equipo, no solo el seleccionado en
  // el selector de arriba - por eso depende de equipoSeleccionado, no
  // de sensorParaDatos.
  const [alertaDiagnostico, setAlertaDiagnostico] = useState(null)

  // Flujo bajo pedido en la pestaña "Espectro FFT" (D-049, ver
  // PROYECTO.md): espectro crudo de rango completo (siempre visible) ->
  // "Aplicar Hilbert" (opcional) -> "Optimizar con PSO" (opcional). No
  // reemplaza ni depende de la alerta automatica (D-048) ni del
  // diagnostico de rodamiento que ya corre solo (D-039/D-041) - esto es
  // puramente una visualizacion adicional bajo demanda.
  const [mostrarHilbert, setMostrarHilbert] = useState(false)
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

  // Que sensor o rodamiento eligio el operador en el selector - antes
  // las 4 pestañas mostraban siempre "la medicion mas reciente entre
  // todos los sensores del equipo", sin decir cual sensor era (D-047,
  // ver PROYECTO.md). { tipo: "sensor" | "rodamiento", id }.
  const [seleccion, setSeleccion] = useState(null)

  const equipoSeleccionado = useMemo(() => {
    return (
      equipos.find(
        (equipo) => equipo.id === equipoSeleccionadoId
      ) ?? null
    )
  }, [equipos, equipoSeleccionadoId])

  // Al cambiar de equipo, se selecciona su primer sensor por defecto
  // (mismo criterio "mas simple posible" que antes, pero ahora
  // explicito y visible en el selector en vez de implicito en el
  // backend).
  useEffect(() => {
    if (!equipoSeleccionado) {
      setSeleccion(null)
      return
    }
    const primerSensor = equipoSeleccionado.sensores?.[0]
    setSeleccion(primerSensor ? { tipo: "sensor", id: primerSensor.id } : null)
  }, [equipoSeleccionado?.id])

  // El sensor cuyos datos hay que pedir al backend: si se eligio un
  // sensor directamente, es ese; si se eligio un rodamiento, es el
  // primer sensor vinculado a el (un rodamiento no tiene mediciones
  // propias - las tiene el sensor que lo monitorea).
  const sensorParaDatos = useMemo(() => {
    if (!equipoSeleccionado || !seleccion) return null
    if (seleccion.tipo === "sensor") {
      return equipoSeleccionado.sensores.find((s) => s.id === seleccion.id) ?? null
    }
    return equipoSeleccionado.sensores.find((s) => s.rodamiento_id === seleccion.id) ?? null
  }, [equipoSeleccionado, seleccion])

  const rodamientoSeleccionado = useMemo(() => {
    if (!equipoSeleccionado || seleccion?.tipo !== "rodamiento") return null
    return equipoSeleccionado.rodamientos.find((r) => r.id === seleccion.id) ?? null
  }, [equipoSeleccionado, seleccion])

  function manejarCambioSeleccion(valor) {
    const [tipo, idTexto] = valor.split("-")
    const id = Number(idTexto)
    setSeleccion({ tipo, id })
    if (tipo === "rodamiento") {
      setPestanaActiva("envolvente")
    }
  }

  const datosVisualizacion = useMemo(() => {
    const cantidadMaxima = 100

    if (datos.length <= cantidadMaxima) {
      return datos
    }

    return Array.from({ length: cantidadMaxima }, (_, indice) => {
      const posicion = Math.round(
        (indice * (datos.length - 1)) / (cantidadMaxima - 1)
      )

      return datos[posicion]
    })
  }, [datos])

  useEffect(() => {
    if (!equipoSeleccionado) {
      return
    }

    const idEquipo = equipoSeleccionado.id
    const idSensor = sensorParaDatos?.id ?? null

    setDatos([])
    setDatosFFT([])
    setDatosEstadisticos(ESTADISTICOS_VACIOS)
    setDatosEnvolvente(null)
    setMensajeEnvolvente("")
    setFrecuenciaMaximaFFT(300)

    // Cambiar de equipo/sensor descarta cualquier vista de Hilbert/PSO
    // que se hubiera pedido para el sensor anterior - evita mostrar un
    // resultado que ya no corresponde a lo seleccionado.
    clearInterval(intervaloPsoRef.current)
    setMostrarHilbert(false)
    setUsarPso(false)
    setFrecuenciaObjetivoPso("")
    setEjecutandoPso(false)
    setProgresoPso(0)
    setResultadoPso(null)
    setErrorPso("")

    // Un rodamiento elegido en el selector puede no tener ningun sensor
    // vinculado todavia (Configuración → Sensores) - en ese caso no hay
    // ninguna medicion que pedir, se avisa y no se llama al backend.
    if (seleccion?.tipo === "rodamiento" && !idSensor) {
      const mensaje = `El rodamiento ${rodamientoSeleccionado?.codigo ?? ""} no tiene un sensor vinculado — no hay datos que mostrar (vincúlalo en Configuración → Sensores).`
      setMensajeBackend(mensaje)
      setMensajeFFT(mensaje)
      setMensajeEstadisticos(mensaje)
      setMensajeEnvolvente(mensaje)
      return
    }

    const parametroSensor = idSensor ? `&sensor_id=${idSensor}` : ""
    const etiquetaSensor = sensorParaDatos ? ` — sensor ${sensorParaDatos.codigo}` : ""

    function mensajeError(respuesta, generico) {
      return respuesta.status === 404
        ? "Este equipo no tiene mediciones registradas"
        : generico
    }

    apiFetch(`http://127.0.0.1:8000/api/datos?equipo_id=${idEquipo}${parametroSensor}`)
      .then(async (respuesta) => {
        if (!respuesta.ok) {
          throw new Error(
            mensajeError(respuesta, "No fue posible obtener los datos temporales")
          )
        }

        return respuesta.json()
      })
      .then((respuestaDatos) => {
        setDatos(respuestaDatos.datos)

        setMensajeBackend(
          `Se cargaron ${respuestaDatos.datos.length} muestras${etiquetaSensor}`
        )
      })
      .catch((error) => {
        setMensajeBackend(error.message)
      })

    apiFetch(`http://127.0.0.1:8000/api/fft?equipo_id=${idEquipo}${parametroSensor}&rango_completo=true`)
      .then((respuesta) => {
        if (!respuesta.ok) {
          throw new Error(mensajeError(respuesta, "No fue posible obtener los datos FFT"))
        }

        return respuesta.json()
      })
      .then((respuestaFFT) => {
        setDatosFFT(respuestaFFT.datos)
        setFrecuenciaMaximaFFT(respuestaFFT.frecuencia_maxima)

        setMensajeFFT(
          `Se cargaron ${respuestaFFT.cantidad_puntos} puntos de frecuencia, hasta ${Math.round(respuestaFFT.frecuencia_maxima)} Hz (Nyquist)${etiquetaSensor}`
        )
      })
      .catch((error) => {
        setMensajeFFT(error.message)
      })

    apiFetch(`http://127.0.0.1:8000/api/estadisticos?equipo_id=${idEquipo}${parametroSensor}`)
      .then((respuesta) => {
        if (!respuesta.ok) {
          throw new Error(
            mensajeError(respuesta, "No fue posible obtener los estadísticos")
          )
        }

        return respuesta.json()
      })
      .then((respuestaEstadisticos) => {
        setDatosEstadisticos(respuestaEstadisticos)

        setMensajeEstadisticos(
          `Estadísticos calculados sobre las mismas muestras cargadas${etiquetaSensor}`
        )
      })
      .catch((error) => {
        setMensajeEstadisticos(error.message)
      })

    apiFetch(`http://127.0.0.1:8000/api/envolvente?equipo_id=${idEquipo}${parametroSensor}`)
      .then(async (respuesta) => {
        if (!respuesta.ok) {
          const detalle = await respuesta.json().catch(() => null)
          throw new Error(
            mensajeError(respuesta, detalle?.detail ?? "No fue posible obtener el espectro de envolvente")
          )
        }
        return respuesta.json()
      })
      .then((respuestaEnvolvente) => {
        setDatosEnvolvente(respuestaEnvolvente)
        setMensajeEnvolvente("")
      })
      .catch((error) => {
        setDatosEnvolvente(null)
        setMensajeEnvolvente(error.message)
      })
  }, [equipoSeleccionado, sensorParaDatos, seleccion, rodamientoSeleccionado, recargarContador])

  useEffect(() => {
    if (!equipoSeleccionado) {
      setAlertaDiagnostico(null)
      return
    }

    const idEquipo = equipoSeleccionado.id

    apiFetch(`http://127.0.0.1:8000/api/alertas?equipo_id=${idEquipo}`)
      .then((respuesta) => (respuesta.ok ? respuesta.json() : { hipotesis: [], advertencia: "No fue posible evaluar este equipo" }))
      .then(setAlertaDiagnostico)
      .catch(() => setAlertaDiagnostico({ hipotesis: [], advertencia: "No fue posible evaluar este equipo" }))
  }, [equipoSeleccionado, recargarContador])

  const peorHipotesis = alertaDiagnostico?.hipotesis?.[0] ?? null
  const nivelAlerta = peorHipotesis ? nivelAlertaDe(peorHipotesis.confianza) : null
  const severidadIso = alertaDiagnostico?.severidad_iso ?? null

  // Lista de candidatas a optimizar con PSO, ordenada por prioridad
  // (misma confianza con la que datosEnvolvente.hipotesis ya viene
  // ordenado) - mismo patron que Laboratorio.jsx, derivado en el
  // frontend sin pedirle nada nuevo al backend.
  const candidatosPso = (datosEnvolvente?.hipotesis ?? [])
    .filter((h) => FALLA_A_FRECUENCIA[h.falla])
    .map((h) => ({
      falla: h.falla,
      etiqueta: ETIQUETAS_FALLA[h.falla] ?? h.falla,
      confianza: h.confianza,
      claveFrecuencia: FALLA_A_FRECUENCIA[h.falla],
      frecuencia: datosEnvolvente.grafico.frecuencias_falla[FALLA_A_FRECUENCIA[h.falla]],
    }))

  async function iniciarPso() {
    const candidata = candidatosPso.find((c) => c.claveFrecuencia === frecuenciaObjetivoPso)
    if (!candidata || !sensorParaDatos) {
      setErrorPso("Elige qué frecuencia optimizar.")
      return
    }

    setErrorPso("")
    setResultadoPso(null)
    setProgresoPso(0)
    setEjecutandoPso(true)

    try {
      const parametros = new URLSearchParams({
        equipo_id: equipoSeleccionado.id,
        sensor_id: sensorParaDatos.id,
        frecuencia_objetivo: candidata.frecuencia,
        enjambre: "30",
        iteraciones: "30",
      })

      const respuestaInicio = await apiFetch(`http://127.0.0.1:8000/api/analizador/pso/iniciar?${parametros}`, {
        method: "POST",
      })

      if (!respuestaInicio.ok) {
        const detalle = await respuestaInicio.json().catch(() => null)
        throw new Error(detalle?.detail ?? "No fue posible iniciar la optimización PSO")
      }

      const { job_id: jobId } = await respuestaInicio.json()

      intervaloPsoRef.current = setInterval(async () => {
        try {
          const respuestaEstado = await apiFetch(`http://127.0.0.1:8000/api/analizador/pso/estado/${jobId}`)
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

  function seleccionarEquipo(equipo) {
    setEquipoSeleccionadoId(equipo.id)

    const primeraPestana =
      equipo.analisisDisponibles?.[0]?.id ?? "tiempo"

    setPestanaActiva(primeraPestana)
  }

  if (!equipoSeleccionado) {
    return (
      <main className="dashboard-content">
        <section className="tarjeta">
          <h1>{cargandoEquipos ? "Cargando equipos…" : "No hay equipos registrados"}</h1>
          {!cargandoEquipos && (
            <p>
              Registra el primer equipo en Configuración → Equipos para
              comenzar a visualizar sus sensores y análisis.
            </p>
          )}
        </section>
      </main>
    )
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
        vistaActiva="detalle"
        onIrAResumen={onIrAResumen}
        onIrAConfiguracion={onIrAConfiguracion}
        onIrAReportes={onIrAReportes}
        onIrALaboratorio={onIrALaboratorio}
        equipoActivoId={equipoSeleccionado.id}
        onSeleccionarEquipo={seleccionarEquipo}
      />

      <div className="main-area">
        <header className="topbar">
          <p className="topbar-equipo">
            {equipoSeleccionado.id} — {equipoSeleccionado.nombre}
          </p>

          <div className="topbar-user">
            {dashboardDemo.estadoTiempoReal.activo && (
              <span className="estado-en-vivo">
                <span className="punto-en-vivo" />

                {dashboardDemo.estadoTiempoReal.texto}
              </span>
            )}

            <div className="usuario-avatar">{iniciales}</div>

            <div className="usuario-info">
              <strong>{sesion.usuario.nombre}</strong>
              <small>
                {sesion.usuario.rol === "administrador"
                  ? "Administrador"
                  : sesion.usuario.rol}
              </small>
            </div>

            <button
              type="button"
              className="boton-salir"
              onClick={onCerrarSesion}
            >
              SALIR
            </button>
          </div>
        </header>

        <main className="dashboard-content">
          <section className="tarjeta tarjeta-equipo-principal">
            <div className="equipo-principal-encabezado">
              <div>
                <p className="equipo-principal-tipo">
                  {equipoSeleccionado.tipo}
                </p>

                <h1>{equipoSeleccionado.nombre}</h1>

                <p>
                  {equipoSeleccionado.id} ·{" "}
                  {equipoSeleccionado.ubicacion}
                </p>
              </div>

              <div className="equipo-principal-acciones">
                <span
                  className={`estado-principal estado-principal-${equipoSeleccionado.estado}`}
                >
                  {equipoSeleccionado.descripcionEstado}
                </span>

                {peorHipotesis && (
                  <span
                    className={`alerta-diagnostico alerta-diagnostico-${nivelAlerta}`}
                    title={`Sensor ${peorHipotesis.sensor_codigo} — evidencia: ${peorHipotesis.evidencias.join(", ")}`}
                  >
                    Diagnóstico automático: {ETIQUETAS_FALLA[peorHipotesis.falla] ?? peorHipotesis.falla} (
                    {Math.round(peorHipotesis.confianza * 100)}%)
                  </span>
                )}

                {!peorHipotesis && alertaDiagnostico?.advertencia && (
                  <span className="alerta-diagnostico alerta-diagnostico-sin-datos">
                    {alertaDiagnostico.advertencia}
                  </span>
                )}

                {severidadIso && (
                  <span
                    className={`alerta-diagnostico alerta-diagnostico-${nivelSeveridadIsoDe(severidadIso.zona)}`}
                    title={`Sensor ${severidadIso.sensor_codigo} — ${severidadIso.velocidad_rms_mm_s?.toFixed(2)} mm/s RMS, ${severidadIso.grupo?.replace("_", " ")}, soporte ${severidadIso.tipo_soporte}`}
                  >
                    Severidad ISO 20816-3: Zona {severidadIso.zona} ({severidadIso.severidad?.replaceAll("_", " ")})
                  </span>
                )}

                <button
                  type="button"
                  className="boton-cargar-datos"
                  onClick={() => setMostrandoCargaMedicion(true)}
                >
                  Cargar datos
                </button>
              </div>
            </div>

            {mostrandoCargaMedicion && (
              <ModalCargaMedicion
                equipoId={equipoSeleccionado.id}
                equipoNombre={equipoSeleccionado.nombre}
                onCerrar={() => setMostrandoCargaMedicion(false)}
                onCargada={() => setRecargarContador((actual) => actual + 1)}
              />
            )}

            <div className="equipo-principal-datos">
              <article className="dato-equipo">
                <span>Potencia</span>
                <strong>{equipoSeleccionado.potenciaKw} kW</strong>
              </article>

              <article className="dato-equipo">
                <span>Última medición</span>
                <strong>{equipoSeleccionado.ultimaMedicion}</strong>
              </article>

              <article className="dato-equipo">
                <span>Sensor / Rodamiento</span>
                {equipoSeleccionado.sensores.length > 0 || equipoSeleccionado.rodamientos.length > 0 ? (
                  <select
                    className="selector-sensor-rodamiento"
                    value={seleccion ? `${seleccion.tipo}-${seleccion.id}` : ""}
                    onChange={(e) => manejarCambioSeleccion(e.target.value)}
                  >
                    {equipoSeleccionado.sensores.length > 0 && (
                      <optgroup label="Sensores">
                        {equipoSeleccionado.sensores.map((sensor) => (
                          <option key={`sensor-${sensor.id}`} value={`sensor-${sensor.id}`}>
                            {sensor.codigo}
                            {sensor.ubicacion ? ` — ${sensor.ubicacion}` : ""}
                          </option>
                        ))}
                      </optgroup>
                    )}
                    {equipoSeleccionado.rodamientos.length > 0 && (
                      <optgroup label="Rodamientos">
                        {equipoSeleccionado.rodamientos.map((rodamiento) => (
                          <option key={`rodamiento-${rodamiento.id}`} value={`rodamiento-${rodamiento.id}`}>
                            {rodamiento.codigo}
                            {rodamiento.modelo ? ` — ${rodamiento.modelo}` : ""}
                          </option>
                        ))}
                      </optgroup>
                    )}
                  </select>
                ) : (
                  <strong>Sin sensores registrados</strong>
                )}
              </article>

              <article className="dato-equipo">
                <span>Estado del sensor</span>
                <strong>
                  {sensorParaDatos?.estado ?? "Sin información"}
                </strong>
              </article>
            </div>
          </section>

          <nav className="pestanas">
            {equipoSeleccionado.analisisDisponibles.map(
              (analisis) => (
                <button
                  key={analisis.id}
                  type="button"
                  className={`pestana ${
                    pestanaActiva === analisis.id ? "activa" : ""
                  }`}
                  onClick={() => setPestanaActiva(analisis.id)}
                >
                  {analisis.nombre}
                </button>
              )
            )}
          </nav>

          {pestanaActiva === "tiempo" && (
            <section className="tarjeta">
              <h3>Vibración de los ejes X, Y y Z</h3>

              <p>
                Se muestran {datosVisualizacion.length} muestras reales
                distribuidas uniformemente a lo largo de la señal.
              </p>

              <p>
                <strong>Estado del backend:</strong>{" "}
                {mensajeBackend}
              </p>

              <div style={{ width: "100%", height: "400px" }}>
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={datosVisualizacion}>
                    <CartesianGrid strokeDasharray="3 3" />

                    <XAxis
                      dataKey="timestamp"
                      tick={false}
                      label={{
                        value: "Tiempo",
                        position: "insideBottom",
                        offset: -5,
                      }}
                    />

                    <YAxis
                      label={{
                        value: "Amplitud [g]",
                        angle: -90,
                        position: "insideLeft",
                      }}
                    />

                    <Tooltip
                      cursor={{
                        stroke: "#94a3b8",
                        strokeWidth: 1,
                      }}
                      formatter={(valor, nombre) => [
                        `${Number(valor).toFixed(3)} g`,
                        nombre,
                      ]}
                    />

                    <Legend />

                    <Line
                      type="monotone"
                      dataKey="vibracion_x"
                      name="Eje X"
                      stroke="#14b8a6"
                      dot={false}
                      activeDot={{ r: 5 }}
                      strokeWidth={1.8}
                      isAnimationActive={false}
                    />

                    <Line
                      type="monotone"
                      dataKey="vibracion_y"
                      name="Eje Y"
                      stroke="#38bdf8"
                      dot={false}
                      activeDot={{ r: 5 }}
                      strokeWidth={1.8}
                      isAnimationActive={false}
                    />

                    <Line
                      type="monotone"
                      dataKey="vibracion_z"
                      name="Eje Z"
                      stroke="#a78bfa"
                      dot={false}
                      activeDot={{ r: 5 }}
                      strokeWidth={1.8}
                      isAnimationActive={false}
                    />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            </section>
          )}

          {pestanaActiva === "fft" && (
            <section className="tarjeta">
              <h3>Transformada Rápida de Fourier (FFT) — rango completo</h3>

              <p className="config-mensaje">
                Espectro crudo hasta el Nyquist real del sensor — incluye las frecuencias altas de
                resonancia que un tope fijo de 300 Hz no dejaba ver. Sobre este mismo espectro
                puedes pedir la envolvente (Hilbert) y, si corresponde a un rodamiento, optimizarla
                con PSO.
              </p>

              <p>{mensajeFFT}</p>

              <div style={{ width: "100%", height: "400px" }}>
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={datosFFT}>
                    <CartesianGrid strokeDasharray="3 3" />

                    <XAxis
                      dataKey="frecuencia"
                      type="number"
                      domain={[0, frecuenciaMaximaFFT]}
                      label={{
                        value: "Frecuencia [Hz]",
                        position: "insideBottom",
                        offset: -5,
                      }}
                    />

                    <YAxis
                      label={{
                        value: "Amplitud",
                        angle: -90,
                        position: "insideLeft",
                      }}
                    />

                    <Tooltip />

                    <Legend />

                    <Line
                      type="linear"
                      dataKey="amplitud_x"
                      name="FFT Eje X"
                      stroke="#14b8a6"
                      dot={false}
                      strokeWidth={1.8}
                      isAnimationActive={false}
                    />

                    <Line
                      type="linear"
                      dataKey="amplitud_y"
                      name="FFT Eje Y"
                      stroke="#38bdf8"
                      dot={false}
                      strokeWidth={1.8}
                      isAnimationActive={false}
                    />

                    <Line
                      type="linear"
                      dataKey="amplitud_z"
                      name="FFT Eje Z"
                      stroke="#a78bfa"
                      dot={false}
                      strokeWidth={1.8}
                      isAnimationActive={false}
                    />
                  </LineChart>
                </ResponsiveContainer>
              </div>

              <div className="reporte-grafico-rodamiento">
                {!mostrarHilbert && (
                  <button type="button" className="config-boton-secundario" onClick={() => setMostrarHilbert(true)}>
                    Aplicar transformada de Hilbert (ver envolvente)
                  </button>
                )}

                {mostrarHilbert && (
                  <>
                    {datosEnvolvente?.grafico ? (
                      <GraficoEnvolvente grafico={datosEnvolvente.grafico} />
                    ) : (
                      <p className="config-mensaje">
                        {mensajeEnvolvente || "Este sensor no tiene un rodamiento vinculado — no hay envolvente que calcular."}
                      </p>
                    )}

                    {candidatosPso.length > 0 && (
                      <div style={{ marginTop: "14px" }}>
                        <label>
                          <input type="checkbox" checked={usarPso} onChange={(e) => setUsarPso(e.target.checked)} />
                          {" "}Optimizar la ventana con PSO (más preciso, puede tardar varios minutos — 30
                          partículas × 30 iteraciones)
                        </label>

                        {usarPso && (
                          <div className="config-form" style={{ marginTop: "10px" }}>
                            <div className="config-form-campo config-form-campo-ancho">
                              <label>Frecuencia a optimizar (ordenadas por confianza)</label>
                              <select
                                value={frecuenciaObjetivoPso}
                                onChange={(e) => setFrecuenciaObjetivoPso(e.target.value)}
                              >
                                <option value="" disabled>Elige una frecuencia</option>
                                {candidatosPso.map((candidata) => (
                                  <option key={candidata.claveFrecuencia} value={candidata.claveFrecuencia}>
                                    {candidata.claveFrecuencia} — {candidata.etiqueta} —{" "}
                                    {Math.round(candidata.confianza * 100)}% de confianza —{" "}
                                    {candidata.frecuencia.toFixed(1)} Hz
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
                  </>
                )}
              </div>
            </section>
          )}

          {pestanaActiva === "curtosis" && (
            <section className="tarjeta">
              <h3>Curtosis</h3>

              <p>{mensajeEstadisticos}</p>

              <div style={{ width: "100%", height: "400px" }}>
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={datosEstadisticos.curtosis}>
                    <CartesianGrid strokeDasharray="3 3" />

                    <XAxis dataKey="eje" />

                    <YAxis
                      label={{
                        value: "Curtosis",
                        angle: -90,
                        position: "insideLeft",
                      }}
                    />

                    <Tooltip />

                    <Bar dataKey="valor" name="Curtosis" fill="#14b8a6" />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </section>
          )}

          {pestanaActiva === "factor_cresta" && (
            <section className="tarjeta">
              <h3>Factor de Cresta</h3>

              <p>{mensajeEstadisticos}</p>

              <div style={{ width: "100%", height: "400px" }}>
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={datosEstadisticos.factor_cresta}>
                    <CartesianGrid strokeDasharray="3 3" />

                    <XAxis dataKey="eje" />

                    <YAxis
                      label={{
                        value: "Factor de Cresta",
                        angle: -90,
                        position: "insideLeft",
                      }}
                    />

                    <Tooltip />

                    <Bar
                      dataKey="valor"
                      name="Factor de Cresta"
                      fill="#38bdf8"
                    />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </section>
          )}

          {pestanaActiva === "skewness" && (
            <section className="tarjeta">
              <h3>Skewness</h3>

              <p>{mensajeEstadisticos}</p>

              <div style={{ width: "100%", height: "400px" }}>
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={datosEstadisticos.skewness}>
                    <CartesianGrid strokeDasharray="3 3" />

                    <XAxis dataKey="eje" />

                    <YAxis
                      label={{
                        value: "Skewness",
                        angle: -90,
                        position: "insideLeft",
                      }}
                    />

                    <Tooltip />

                    <Bar dataKey="valor" name="Skewness" fill="#a78bfa" />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </section>
          )}

          {pestanaActiva === "envolvente" && (
            <section className="tarjeta">
              <h3>Rodamiento — espectro de envolvente</h3>

              {mensajeEnvolvente && <p className="config-mensaje">{mensajeEnvolvente}</p>}

              {datosEnvolvente?.grafico && (
                <>
                  {datosEnvolvente.hipotesis.length === 0 && (
                    <p className="config-mensaje">
                      No se encontraron hipótesis de falla con confianza suficiente.
                    </p>
                  )}
                  {datosEnvolvente.hipotesis.map((h) => (
                    <p key={h.falla} className="config-mensaje">
                      <strong>{h.falla.replaceAll("_", " ")}</strong> — {Math.round(h.confianza * 100)}%
                      de confianza. Evidencia: {h.evidencias.join(", ")}
                    </p>
                  ))}

                  <GraficoEnvolvente grafico={datosEnvolvente.grafico} />
                </>
              )}
            </section>
          )}
        </main>
      </div>
    </div>
  )
}

export default AnalizadorVibraciones
