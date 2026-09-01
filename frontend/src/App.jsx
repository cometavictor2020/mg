import { useEffect, useState } from "react"

import Login from "./pages/Login"
import ResumenGeneral from "./pages/ResumenGeneral"
import AnalizadorVibraciones from "./pages/AnalizadorVibraciones"

const CLAVE_SESION = "motorguardian_sesion"

function App() {
  const [sesion, setSesion] = useState(null)
  const [cargandoSesion, setCargandoSesion] = useState(true)
  const [vista, setVista] = useState("resumen")
  const [equipoDetalleId, setEquipoDetalleId] = useState(null)

  useEffect(() => {
    const guardada = localStorage.getItem(CLAVE_SESION)

    if (guardada) {
      try {
        setSesion(JSON.parse(guardada))
      } catch {
        localStorage.removeItem(CLAVE_SESION)
      }
    }

    setCargandoSesion(false)
  }, [])

  function manejarLoginExitoso(datosSesion) {
    localStorage.setItem(CLAVE_SESION, JSON.stringify(datosSesion))
    setSesion(datosSesion)
    setVista("resumen")
  }

  function cerrarSesion() {
    localStorage.removeItem(CLAVE_SESION)
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
        equipoInicialId={equipoDetalleId}
      />
    )
  }

  return (
    <ResumenGeneral
      sesion={sesion}
      onCerrarSesion={cerrarSesion}
      onSeleccionarEquipo={irADetalleEquipo}
    />
  )
}

export default App
