import { useEffect, useState } from "react"

import { analisisEstandar } from "../data/analisisEstandar"
import { apiFetch } from "../utils/apiFetch"

const URL_BASE = "http://127.0.0.1:8000"

const DESCRIPCION_ESTADO = {
  critico: "Crítico",
  advertencia: "Advertencia",
  normal: "Normal",
  inactivo: "Fuera de línea",
}

function adaptarEquipo(equipo) {
  return {
    id: equipo.id,
    nombre: equipo.nombre,
    tipo: equipo.tipo ?? "Sin tipo",
    potenciaKw: equipo.potencia_kw,
    estado: equipo.estado,
    descripcionEstado: DESCRIPCION_ESTADO[equipo.estado] ?? equipo.estado,
    ubicacion: equipo.planta ?? "Sin planta asignada",
    ubicacionDetalle: equipo.planta ?? "Sin planta asignada",

    // Estas metricas todavia no vienen de una medicion real por equipo
    // (ver Deuda tecnica en PROYECTO.md): se muestran como "sin datos"
    // en vez de inventar numeros.
    ultimaMedicion: "Sin datos",
    vibracionRms: null,
    temperatura: null,
    velNominal: null,
    probabilidadFalla: null,
    diasFallaEstimada: null,
    sensores: [],

    analisisDisponibles: analisisEstandar,
  }
}

export function useEquiposReales() {
  const [equipos, setEquipos] = useState([])
  const [cargando, setCargando] = useState(true)
  const [error, setError] = useState("")

  useEffect(() => {
    apiFetch(`${URL_BASE}/api/equipos`)
      .then((respuesta) => {
        if (!respuesta.ok) {
          throw new Error("No fue posible cargar los equipos")
        }
        return respuesta.json()
      })
      .then((datos) => {
        setEquipos(datos.map(adaptarEquipo))
        setError("")
      })
      .catch(() => setError("No fue posible cargar los equipos"))
      .finally(() => setCargando(false))
  }, [])

  return { equipos, cargando, error }
}
