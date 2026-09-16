const CLAVE_SESION = "motorguardian_sesion"

export function obtenerSesion() {
  const guardada = localStorage.getItem(CLAVE_SESION)

  if (!guardada) {
    return null
  }

  try {
    return JSON.parse(guardada)
  } catch {
    return null
  }
}

export function guardarSesion(sesion) {
  localStorage.setItem(CLAVE_SESION, JSON.stringify(sesion))
}

export function borrarSesion() {
  localStorage.removeItem(CLAVE_SESION)
}
