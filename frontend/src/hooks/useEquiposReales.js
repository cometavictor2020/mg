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

// Sensor.serializar()/Rodamiento.serializar() (backend) no traen un
// campo "nombre" - se deriva aca del codigo autogenerado (ej.
// "VIBPZO-01"), que es lo que ya se usa en el resto de la app
// (ModalCargaMedicion.jsx) para identificar un sensor/rodamiento
// puntual.
function adaptarSensor(sensor) {
  return {
    ...sensor,
    nombre: sensor.codigo ?? sensor.tipo ?? `Sensor ${sensor.id}`,
  }
}

function adaptarRodamiento(rodamiento) {
  return {
    ...rodamiento,
    nombre: rodamiento.codigo ?? rodamiento.modelo ?? `Rodamiento ${rodamiento.id}`,
  }
}

function adaptarEquipo(equipo, sensoresPorEquipo, rodamientosPorEquipo) {
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

    // Antes venia hardcodeado en [] (ver Deuda tecnica en PROYECTO.md) -
    // ahora son los sensores/rodamientos reales de este equipo, traidos
    // de /api/sensores y /api/rodamientos (una sola vez para todos los
    // equipos, agrupados aca por equipo_id - evita N llamadas, una por
    // equipo).
    sensores: (sensoresPorEquipo.get(equipo.id) ?? []).map(adaptarSensor),
    rodamientos: (rodamientosPorEquipo.get(equipo.id) ?? []).map(adaptarRodamiento),

    analisisDisponibles: analisisEstandar,
  }
}

function agruparPorEquipo(items) {
  const mapa = new Map()
  for (const item of items) {
    const lista = mapa.get(item.equipo_id) ?? []
    lista.push(item)
    mapa.set(item.equipo_id, lista)
  }
  return mapa
}

export function useEquiposReales() {
  const [equipos, setEquipos] = useState([])
  const [cargando, setCargando] = useState(true)
  const [error, setError] = useState("")

  useEffect(() => {
    Promise.all([
      apiFetch(`${URL_BASE}/api/equipos`),
      apiFetch(`${URL_BASE}/api/sensores`),
      apiFetch(`${URL_BASE}/api/rodamientos`),
    ])
      .then(async ([respuestaEquipos, respuestaSensores, respuestaRodamientos]) => {
        if (!respuestaEquipos.ok || !respuestaSensores.ok || !respuestaRodamientos.ok) {
          throw new Error("No fue posible cargar los equipos")
        }

        const [equiposData, sensoresData, rodamientosData] = await Promise.all([
          respuestaEquipos.json(),
          respuestaSensores.json(),
          respuestaRodamientos.json(),
        ])

        const sensoresPorEquipo = agruparPorEquipo(sensoresData)
        const rodamientosPorEquipo = agruparPorEquipo(rodamientosData)

        setEquipos(equiposData.map((equipo) => adaptarEquipo(equipo, sensoresPorEquipo, rodamientosPorEquipo)))
        setError("")
      })
      .catch(() => setError("No fue posible cargar los equipos"))
      .finally(() => setCargando(false))
  }, [])

  return { equipos, cargando, error }
}
