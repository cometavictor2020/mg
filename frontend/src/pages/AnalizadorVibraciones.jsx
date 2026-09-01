import { useEffect, useMemo, useState } from "react"
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

import Sidebar from "../components/Sidebar"
import { dashboardDemo } from "../data/dashboardDemo"
import { equiposDemo } from "../data/equiposDemo"

const ESTADISTICOS_VACIOS = {
  curtosis: [],
  factor_cresta: [],
  skewness: [],
}

function AnalizadorVibraciones({
  sesion,
  onCerrarSesion,
  onIrAResumen,
  equipoInicialId,
}) {
  const [equipoSeleccionadoId, setEquipoSeleccionadoId] = useState(
    equipoInicialId ?? equiposDemo[0]?.id ?? null
  )

  const [pestanaActiva, setPestanaActiva] = useState("tiempo")
  const [mensajeBackend, setMensajeBackend] = useState("")
  const [mensajeFFT, setMensajeFFT] = useState("")
  const [mensajeEstadisticos, setMensajeEstadisticos] = useState("")
  const [datos, setDatos] = useState([])
  const [datosFFT, setDatosFFT] = useState([])
  const [datosEstadisticos, setDatosEstadisticos] = useState(
    ESTADISTICOS_VACIOS
  )

  const equipoSeleccionado = useMemo(() => {
    return (
      equiposDemo.find(
        (equipo) => equipo.id === equipoSeleccionadoId
      ) ?? null
    )
  }, [equipoSeleccionadoId])

  const sensorPrincipal = equipoSeleccionado?.sensores?.[0] ?? null

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
    fetch("http://127.0.0.1:8000/api/datos")
      .then((respuesta) => {
        if (!respuesta.ok) {
          throw new Error(
            "No fue posible obtener los datos temporales"
          )
        }

        return respuesta.json()
      })
      .then((respuestaDatos) => {
        console.log("Datos temporales:", respuestaDatos)

        setDatos(respuestaDatos.datos)

        setMensajeBackend(
          `Se cargaron ${respuestaDatos.datos.length} muestras`
        )
      })
      .catch((error) => {
        console.error(error)
        setMensajeBackend("Error al conectar con el backend")
      })

    fetch("http://127.0.0.1:8000/api/fft")
      .then((respuesta) => {
        if (!respuesta.ok) {
          throw new Error("No fue posible obtener los datos FFT")
        }

        return respuesta.json()
      })
      .then((respuestaFFT) => {
        console.log("Datos FFT:", respuestaFFT)

        setDatosFFT(respuestaFFT.datos)

        setMensajeFFT(
          `Se cargaron ${respuestaFFT.cantidad_puntos} puntos de frecuencia`
        )
      })
      .catch((error) => {
        console.error(error)
        setMensajeFFT("Error al obtener la FFT")
      })

    fetch("http://127.0.0.1:8000/api/estadisticos")
      .then((respuesta) => {
        if (!respuesta.ok) {
          throw new Error(
            "No fue posible obtener los estadísticos"
          )
        }

        return respuesta.json()
      })
      .then((respuestaEstadisticos) => {
        console.log("Estadísticos:", respuestaEstadisticos)

        setDatosEstadisticos(respuestaEstadisticos)

        setMensajeEstadisticos(
          "Estadísticos calculados sobre las mismas muestras cargadas"
        )
      })
      .catch((error) => {
        console.error(error)
        setMensajeEstadisticos("Error al obtener los estadísticos")
      })
  }, [])

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
          <h1>No hay equipos registrados</h1>
          <p>
            Registra el primer equipo para comenzar a visualizar sus
            sensores y análisis.
          </p>
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

              <span
                className={`estado-principal estado-principal-${equipoSeleccionado.estado}`}
              >
                {equipoSeleccionado.descripcionEstado}
              </span>
            </div>

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
                <span>Sensor principal</span>
                <strong>
                  {sensorPrincipal?.nombre ?? "Sin sensor"}
                </strong>
              </article>

              <article className="dato-equipo">
                <span>Estado del sensor</span>
                <strong>
                  {sensorPrincipal?.estado ?? "Sin información"}
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
              <h3>Transformada Rápida de Fourier (FFT)</h3>

              <p>{mensajeFFT}</p>

              <div style={{ width: "100%", height: "400px" }}>
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={datosFFT}>
                    <CartesianGrid strokeDasharray="3 3" />

                    <XAxis
                      dataKey="frecuencia"
                      type="number"
                      domain={[0, 300]}
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
        </main>
      </div>
    </div>
  )
}

export default AnalizadorVibraciones
