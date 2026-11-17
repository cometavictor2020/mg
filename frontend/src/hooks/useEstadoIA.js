import { useEffect, useState } from "react"

import { apiFetch } from "../utils/apiFetch"

const URL_BASE = "http://127.0.0.1:8000"

// Estado de la redaccion con IA segun el backend: { listo, motivo, modelo, enviar_nombres }, o null si no respondio.
export function useEstadoIA() {
  const [estadoIA, setEstadoIA] = useState(null)

  useEffect(() => {
    apiFetch(`${URL_BASE}/api/reportes/ia/estado`)
      .then((respuesta) => (respuesta.ok ? respuesta.json() : null))
      .then(setEstadoIA)
      .catch(() => setEstadoIA(null))
  }, [])

  return estadoIA
}
