import { useEffect, useState } from "react"

import Login from "./pages/Login"
import ResumenGeneral from "./pages/ResumenGeneral"
import AnalizadorVibraciones from "./pages/AnalizadorVibraciones"
import Configuracion from "./pages/Configuracion"
import Reportes from "./pages/Reportes"
import { obtenerSesion, guardarSesion, borrarSesion } from "./utils/sesion"

function App() {
  const [sesion, setSesion] = useState(null)
  const [cargandoSesion, setCargandoSesion] = useState(true)
  const [vista, setVista] = useState("resumen")
  const [equipoDetalleId, setEquipoDetalleId] = useState(null)

  useEffect(() => {
    setSesion(obtenerSesion())
    setCargandoSesion(false)
  }, [])

  function manejarLoginExitoso(datosSesion) {
    guardarSesion(datosSesion)
    setSesion(datosSesion)
    setVista("resumen")
  }

  function cerrarSesion() {
    borrarSesion()
    setSesion(null)
    setVista("resumen")
    setEquipoDetalleId(null)
  }

  function irADetalleEquipo(equipo) {
    setEquipoDetalleId(equipo.id)
    setVista("detalle")
  }

  function irAResumen() {
    setVista("resumen")
  }

  function irAConfiguracion() {
    setVista("configuracion")
  }

  function irAReportes() {
    setVista("reportes")
  }

  if (cargandoSesion) {
    return null
  }

  if (!sesion) {
    return <Login onLoginExitoso={manejarLoginExitoso} />
  }

  if (vista === "detalle") {
    return (
      <AnalizadorVibraciones
        sesion={sesion}
        onCerrarSesion={cerrarSesion}
        onIrAResumen={irAResumen}
        onIrAConfiguracion={irAConfiguracion}
        onIrAReportes={irAReportes}
        equipoInicialId={equipoDetalleId}
      />
    )
  }

  if (vista === "configuracion") {
    return (
      <Configuracion
        sesion={sesion}
        onCerrarSesion={cerrarSesion}
        onIrAResumen={irAResumen}
        onIrAReportes={irAReportes}
        onSeleccionarEquipo={irADetalleEquipo}
      />
    )
  }

  if (vista === "reportes") {
    return (
      <Reportes
        sesion={sesion}
        onCerrarSesion={cerrarSesion}
        onIrAResumen={irAResumen}
        onIrAConfiguracion={irAConfiguracion}
        onSeleccionarEquipo={irADetalleEquipo}
      />
    )
  }

  return (
    <ResumenGeneral
      sesion={sesion}
      onCerrarSesion={cerrarSesion}
      onSeleccionarEquipo={irADetalleEquipo}
      onIrAConfiguracion={irAConfiguracion}
      onIrAReportes={irAReportes}
    />
  )
}

export default App
