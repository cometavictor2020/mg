import { obtenerSesion } from "./sesion"

/**
 * Wrapper de fetch que agrega el token JWT de la sesion actual como
 * header Authorization. Los endpoints protegidos del backend lo exigen
 * (Depends(obtener_usuario_actual) en seguridad/auth.py).
 */
export function apiFetch(url, opciones = {}) {
  const token = obtenerSesion()?.access_token

  const encabezados = {
    ...opciones.headers,
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
  }

  return fetch(url, { ...opciones, headers: encabezados })
}
