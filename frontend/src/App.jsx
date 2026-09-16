import { useEffect, useState } from "react"

import Login from "./pages/Login"
import ResumenGeneral from "./pages/ResumenGeneral"
import AnalizadorVibraciones from "./pages/AnalizadorVibraciones"
import Configuracion from "./pages/Configuracion"
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
    />
  )
}

export default App
