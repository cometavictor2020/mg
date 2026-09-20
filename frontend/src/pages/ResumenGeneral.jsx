import { useMemo } from "react"

import Sidebar from "../components/Sidebar"
import { useEquiposReales } from "../hooks/useEquiposReales"

const ETIQUETA_ESTADO = {
  critico: "CRÍTICO",
  advertencia: "ADVERTENCIA",
  normal: "NORMAL",
  inactivo: "FUERA DE LÍNEA",
}

function colorProbabilidad(probabilidad) {
  if (probabilidad === null) return null
  if (probabilidad >= 60) return "rojo"
  if (probabilidad >= 20) return "ambar"
  return "verde"
}

function TarjetaEquipo({ equipo, onSeleccionar }) {
  const colorBarra = colorProbabilidad(equipo.probabilidadFalla)

  return (
    <article
      className={`tarjeta-equipo-resumen borde-${equipo.estado}`}
      onClick={() => onSeleccionar(equipo)}
    >
      <div className="tarjeta-equipo-resumen-encabezado">
        <h3>{equipo.nombre}</h3>
        <span className={`badge-estado badge-${equipo.estado}`}>
          {ETIQUETA_ESTADO[equipo.estado]}
        </span>
      </div>

      <p className="tarjeta-equipo-resumen-subtitulo">
        {equipo.id} · {equipo.ubicacionDetalle}
      </p>

      <div className="tarjeta-equipo-resumen-metricas">
        <div>
          <span>VIBRACIÓN RMS</span>
          <strong>
            {equipo.vibracionRms ?? "—"}
            {equipo.vibracionRms !== null && (
              <small> mm/s</small>
            )}
          </strong>
        </div>

        <div>
          <span>TEMPERATURA</span>
          <strong>
            {equipo.temperatura ?? "—"}
            {equipo.temperatura !== null && <small> °C</small>}
          </strong>
        </div>

        <div>
          <span>VEL. NOMINAL</span>
          <strong>
            {equipo.velNominal ?? "—"}
            {equipo.velNominal !== null && <small> RPM</small>}
          </strong>
        </div>
      </div>

      {equipo.probabilidadFalla !== null && (
        <div className="tarjeta-equipo-resumen-probabilidad">
          <div className="tarjeta-equipo-resumen-probabilidad-encabezado">
            <span>Probabilidad de Falla</span>
            <strong className={`texto-${colorBarra}`}>
              {equipo.probabilidadFalla}%
            </strong>
          </div>

          <div className="barra-probabilidad">
            <div
              className={`barra-probabilidad-relleno fondo-${colorBarra}`}
              style={{ width: `${equipo.probabilidadFalla}%` }}
            />
          </div>

          {equipo.diasFallaEstimada !== null && (
            <p className={`tarjeta-equipo-resumen-alerta texto-${colorBarra}`}>
              ⚠ Falla estimada en ~{equipo.diasFallaEstimada} días
            </p>
          )}
        </div>
      )}
    </article>
  )
}

function ResumenGeneral({ sesion, onCerrarSesion, onSeleccionarEquipo, onIrAConfiguracion, onIrAReportes }) {
  const { equipos, cargando, error } = useEquiposReales()

  const conteos = useMemo(() => {
    const base = { critico: 0, advertencia: 0, normal: 0, inactivo: 0 }

    equipos.forEach((equipo) => {
      base[equipo.estado] += 1
    })

    return base
  }, [equipos])

  const totalEquipos = equipos.length
  const equiposActivos = totalEquipos - conteos.inactivo

  const segmentos = [
    { estado: "normal", color: "verde", cantidad: conteos.normal },
    { estado: "advertencia", color: "ambar", cantidad: conteos.advertencia },
    { estado: "critico", color: "rojo", cantidad: conteos.critico },
    { estado: "inactivo", color: "gris", cantidad: conteos.inactivo },
  ]

  const iniciales = sesion.usuario.nombre
    .split(" ")
    .map((parte) => parte[0])
    .slice(0, 2)
    .join("")
    .toUpperCase()

  return (
    <div className="app-shell">
      <Sidebar
        vistaActiva="resumen"
        onIrAResumen={() => {}}
        onIrAReportes={onIrAReportes}
        onIrAConfiguracion={onIrAConfiguracion}
        equipoActivoId={null}
        onSeleccionarEquipo={onSeleccionarEquipo}
      />

      <div className="main-area">
        <header className="topbar">
          <p className="topbar-equipo">Resumen General</p>

          <div className="topbar-user">
            <span className="estado-en-vivo">
              <span className="punto-en-vivo" />
              EN VIVO
            </span>

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
          {cargando && <p className="seccion-titulo">Cargando equipos…</p>}

          {!cargando && error && <p className="login-error">{error}</p>}

          {!cargando && !error && totalEquipos === 0 && (
            <section className="tarjeta">
              <h1>No hay equipos registrados</h1>
              <p>
                Crea el primer equipo en Configuración → Equipos para
                empezar a monitorearlo.
              </p>
            </section>
          )}

          {!cargando && !error && totalEquipos > 0 && (
            <>
              <section className="kpis-resumen">
                <article className="kpi-tarjeta">
                  <span>TOTAL EQUIPOS</span>
                  <p>
                    <strong>{totalEquipos}</strong> motores
                  </p>
                </article>

                <article className="kpi-tarjeta">
                  <span>ESTADO CRÍTICO</span>
                  <p>
                    <strong className="texto-rojo">{conteos.critico}</strong>{" "}
                    equipos
                  </p>
                </article>

                <article className="kpi-tarjeta">
                  <span>ADVERTENCIAS</span>
                  <p>
                    <strong className="texto-ambar">
                      {conteos.advertencia}
                    </strong>{" "}
                    equipos
                  </p>
                </article>

                <article className="kpi-tarjeta">
                  <span>OPERANDO NORMAL</span>
                  <p>
                    <strong className="texto-verde">{conteos.normal}</strong>{" "}
                    equipos
                  </p>
                </article>
              </section>

              <section className="tarjeta salud-flota">
                <div className="salud-flota-encabezado">
                  <span>SALUD DE FLOTA</span>
                  <span className="salud-flota-activos">
                    {equiposActivos} equipos activos
                  </span>
                </div>

                <div className="salud-flota-barra">
                  {segmentos.map((segmento) => (
                    <div
                      key={segmento.estado}
                      className={`salud-flota-segmento fondo-${segmento.color}`}
                      style={{
                        width: `${(segmento.cantidad / totalEquipos) * 100}%`,
                      }}
                    />
                  ))}
                </div>

                <div className="salud-flota-leyenda">
                  <span>
                    <i className="punto-leyenda fondo-verde" /> NORMAL
                  </span>
                  <span>
                    <i className="punto-leyenda fondo-ambar" /> ADVERTENCIA
                  </span>
                  <span>
                    <i className="punto-leyenda fondo-rojo" /> CRÍTICO
                  </span>
                  <span>
                    <i className="punto-leyenda fondo-gris" /> FUERA DE LÍNEA
                  </span>
                </div>
              </section>

              <section>
                <p className="seccion-titulo">EQUIPOS MONITOREADOS</p>

                <div className="grilla-equipos">
                  {equipos.map((equipo) => (
                    <TarjetaEquipo
                      key={equipo.id}
                      equipo={equipo}
                      onSeleccionar={onSeleccionarEquipo}
                    />
                  ))}
                </div>
              </section>
            </>
          )}
        </main>
      </div>
    </div>
  )
}

export default ResumenGeneral
