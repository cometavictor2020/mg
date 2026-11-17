import { dashboardDemo } from "../data/dashboardDemo"
import { useEquiposReales } from "../hooks/useEquiposReales"
import LogoMotorGuardian from "./LogoMotorGuardian"

function IconoResumen() {
  return (
    <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
      <rect x="1" y="1" width="6" height="6" rx="1.4" stroke="currentColor" strokeWidth="1.4" />
      <rect x="9" y="1" width="6" height="6" rx="1.4" stroke="currentColor" strokeWidth="1.4" />
      <rect x="1" y="9" width="6" height="6" rx="1.4" stroke="currentColor" strokeWidth="1.4" />
      <rect x="9" y="9" width="6" height="6" rx="1.4" stroke="currentColor" strokeWidth="1.4" />
    </svg>
  )
}

function IconoReportes() {
  return (
    <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
      <path d="M2 13.5 6 8l3 2.5 5-6" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round" />
      <path d="M2 13.5h12" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" />
    </svg>
  )
}

function IconoLaboratorio() {
  return (
    <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
      <path
        d="M6.2 1.5h3.6M6.7 1.5v4l-3.3 6.2c-.5 1 .2 2.3 1.4 2.3h6.4c1.2 0 1.9-1.3 1.4-2.3L9.3 5.5v-4"
        stroke="currentColor"
        strokeWidth="1.4"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <path d="M4.8 9.5h6.4" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" />
    </svg>
  )
}

function IconoConfiguracion() {
  return (
    <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
      <circle cx="8" cy="8" r="2.3" stroke="currentColor" strokeWidth="1.4" />
      <path
        d="M8 1.5v1.6M8 12.9v1.6M14.5 8h-1.6M3.1 8H1.5M12.4 3.6l-1.1 1.1M4.7 11.3l-1.1 1.1M12.4 12.4l-1.1-1.1M4.7 4.7 3.6 3.6"
        stroke="currentColor"
        strokeWidth="1.4"
        strokeLinecap="round"
      />
    </svg>
  )
}

function Sidebar({
  vistaActiva,
  onIrAResumen,
  onIrAConfiguracion,
  onIrAReportes,
  onIrALaboratorio,
  equipoActivoId,
  onSeleccionarEquipo,
}) {
  const { equipos } = useEquiposReales()

  return (
    <aside className="sidebar">
      <div className="sidebar-logo">
        <LogoMotorGuardian tamano={42} className="logo-icon" />

        <div>
          <h1>{dashboardDemo.aplicacion.nombre}</h1>

          <p>
            {dashboardDemo.aplicacion.version} ·{" "}
            {dashboardDemo.aplicacion.estado}
          </p>
        </div>
      </div>

      <nav className="sidebar-nav">
        <button
          type="button"
          className={vistaActiva === "resumen" ? "nav-item-activo" : ""}
          onClick={onIrAResumen}
        >
          <span className="nav-item-grupo">
            <span className="nav-item-icono">
              <IconoResumen />
            </span>
            Resumen General
          </span>
        </button>

        <button
          type="button"
          className={vistaActiva === "reportes" ? "nav-item-activo" : ""}
          onClick={onIrAReportes}
        >
          <span className="nav-item-grupo">
            <span className="nav-item-icono">
              <IconoReportes />
            </span>
            Reportes
          </span>
        </button>

        <button
          type="button"
          className={vistaActiva === "laboratorio" ? "nav-item-activo" : ""}
          onClick={onIrALaboratorio}
        >
          <span className="nav-item-grupo">
            <span className="nav-item-icono">
              <IconoLaboratorio />
            </span>
            Laboratorio
          </span>
        </button>

        <button
          type="button"
          className={vistaActiva === "configuracion" ? "nav-item-activo" : ""}
          onClick={onIrAConfiguracion}
        >
          <span className="nav-item-grupo">
            <span className="nav-item-icono">
              <IconoConfiguracion />
            </span>
            Configuración
          </span>
        </button>
      </nav>

      <section className="sidebar-equipos">
        <p className="sidebar-section-title">EQUIPOS</p>

        {equipos.map((equipo) => (
          <button
            key={equipo.id}
            type="button"
            className={`equipo ${
              equipo.id === equipoActivoId ? "equipo-activo" : ""
            }`}
            onClick={() => onSeleccionarEquipo(equipo)}
          >
            <span
              className={`estado-equipo estado-${equipo.estado}`}
            />

            <span className="equipo-texto">
              <strong>{equipo.nombre}</strong>

              <small>
                {equipo.potenciaKw !== null
                  ? `${equipo.potenciaKw} kW`
                  : "Sin potencia registrada"}
              </small>
            </span>
          </button>
        ))}
      </section>
    </aside>
  )
}

export default Sidebar
