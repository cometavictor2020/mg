import { useEffect, useState } from "react"

import Sidebar from "../components/Sidebar"
import { apiFetch } from "../utils/apiFetch"

const URL_BASE = "http://127.0.0.1:8000"

function useColeccion(recurso) {
  const [items, setItems] = useState([])
  const [cargando, setCargando] = useState(true)
  const [error, setError] = useState("")

  function recargar() {
    setCargando(true)
    apiFetch(`${URL_BASE}${recurso}`)
      .then((respuesta) => {
        if (!respuesta.ok) throw new Error("No fue posible cargar los datos")
        return respuesta.json()
      })
      .then((datos) => {
        setItems(datos)
        setError("")
      })
      .catch(() => setError("No fue posible cargar los datos"))
      .finally(() => setCargando(false))
  }

  useEffect(recargar, [recurso])

  return { items, cargando, error, recargar }
}

async function enviarJSON(url, metodo, cuerpo) {
  const respuesta = await apiFetch(url, {
    method: metodo,
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(cuerpo),
  })

  if (!respuesta.ok) {
    const detalle = await respuesta.json().catch(() => null)
    throw new Error(detalle?.detail ?? "Ocurrió un error")
  }

  return respuesta.json()
}

/* ========================================================== */
/* USUARIOS                                                    */
/* ========================================================== */

function SeccionUsuarios() {
  const { items, cargando, error, recargar } = useColeccion("/api/usuarios")
  const [editandoId, setEditandoId] = useState(null)
  const [form, setForm] = useState({ nombre: "", email: "", password: "", rol: "visualizador" })
  const [mensaje, setMensaje] = useState("")

  function limpiarForm() {
    setForm({ nombre: "", email: "", password: "", rol: "visualizador" })
    setEditandoId(null)
  }

  function editar(usuario) {
    setEditandoId(usuario.id)
    setForm({ nombre: usuario.nombre, email: usuario.email, password: "", rol: usuario.rol })
  }

  async function guardar(evento) {
    evento.preventDefault()
    setMensaje("")

    try {
      if (editandoId) {
        await enviarJSON(`${URL_BASE}/api/usuarios/${editandoId}`, "PUT", form)
      } else {
        await enviarJSON(`${URL_BASE}/api/usuarios`, "POST", form)
      }
      limpiarForm()
      recargar()
    } catch (err) {
      setMensaje(err.message)
    }
  }

  async function eliminar(usuario) {
    if (!window.confirm(`¿Estás seguro que deseas eliminar el usuario "${usuario.nombre}"?`)) {
      return
    }
    await apiFetch(`${URL_BASE}/api/usuarios/${usuario.id}`, { method: "DELETE" })
    recargar()
  }

  return (
    <div className="config-seccion">
      <form className="config-form" onSubmit={guardar}>
        <div className="config-form-campo">
          <label>Nombre</label>
          <input
            value={form.nombre}
            onChange={(e) => setForm({ ...form, nombre: e.target.value })}
            required
          />
        </div>

        <div className="config-form-campo">
          <label>Correo electrónico</label>
          <input
            type="email"
            value={form.email}
            onChange={(e) => setForm({ ...form, email: e.target.value })}
            required
          />
        </div>

        <div className="config-form-campo">
          <label>{editandoId ? "Nueva contraseña (opcional)" : "Contraseña"}</label>
          <input
            type="password"
            value={form.password}
            onChange={(e) => setForm({ ...form, password: e.target.value })}
            required={!editandoId}
          />
        </div>

        <div className="config-form-campo">
          <label>Rol</label>
          <select value={form.rol} onChange={(e) => setForm({ ...form, rol: e.target.value })}>
            <option value="administrador">Administrador</option>
            <option value="operador">Operador</option>
            <option value="visualizador">Visualizador</option>
          </select>
        </div>

        <div className="config-form-acciones">
          <button type="submit" className="config-boton-primario">
            {editandoId ? "Guardar cambios" : "Agregar usuario"}
          </button>
          {editandoId && (
            <button type="button" className="config-boton-secundario" onClick={limpiarForm}>
              Cancelar
            </button>
          )}
        </div>

        {mensaje && <p className="config-error">{mensaje}</p>}
      </form>

      {cargando && <p className="config-mensaje">Cargando…</p>}
      {error && <p className="config-error">{error}</p>}

      <table className="config-tabla">
        <thead>
          <tr>
            <th>Nombre</th>
            <th>Correo</th>
            <th>Rol</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          {items.map((usuario) => (
            <tr key={usuario.id}>
              <td>{usuario.nombre}</td>
              <td>{usuario.email}</td>
              <td>{usuario.rol}</td>
              <td className="config-tabla-acciones">
                <button type="button" onClick={() => editar(usuario)}>Editar</button>
                <button type="button" onClick={() => eliminar(usuario)}>Eliminar</button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

/* ========================================================== */
/* EQUIPOS                                                     */
/* ========================================================== */

function SeccionEquipos() {
  const { items, cargando, error, recargar } = useColeccion("/api/equipos")
  const [editandoId, setEditandoId] = useState(null)
  const [form, setForm] = useState({ nombre: "", tipo: "", planta: "", estado: "normal", potencia_kw: "", rpm_nominal: "", tipo_soporte: "" })
  const [mensaje, setMensaje] = useState("")

  function limpiarForm() {
    setForm({ nombre: "", tipo: "", planta: "", estado: "normal", potencia_kw: "", rpm_nominal: "", tipo_soporte: "" })
    setEditandoId(null)
  }

  function editar(equipo) {
    setEditandoId(equipo.id)
    setForm({
      nombre: equipo.nombre,
      tipo: equipo.tipo ?? "",
      planta: equipo.planta ?? "",
      estado: equipo.estado,
      potencia_kw: equipo.potencia_kw ?? "",
      rpm_nominal: equipo.rpm_nominal ?? "",
      tipo_soporte: equipo.tipo_soporte ?? "",
    })
  }

  async function guardar(evento) {
    evento.preventDefault()
    setMensaje("")

    const cuerpo = {
      ...form,
      potencia_kw: form.potencia_kw === "" ? null : Number(form.potencia_kw),
      rpm_nominal: form.rpm_nominal === "" ? null : Number(form.rpm_nominal),
      planta: form.planta === "" ? null : form.planta,
      tipo_soporte: form.tipo_soporte === "" ? null : form.tipo_soporte,
    }

    try {
      if (editandoId) {
        await enviarJSON(`${URL_BASE}/api/equipos/${editandoId}`, "PUT", cuerpo)
      } else {
        await enviarJSON(`${URL_BASE}/api/equipos`, "POST", cuerpo)
      }
      limpiarForm()
      recargar()
    } catch (err) {
      setMensaje(err.message)
    }
  }

  async function eliminar(equipo) {
    if (!window.confirm(`¿Estás seguro que deseas eliminar el equipo "${equipo.nombre}"?`)) {
      return
    }
    await apiFetch(`${URL_BASE}/api/equipos/${equipo.id}`, { method: "DELETE" })
    recargar()
  }

  return (
    <div className="config-seccion">
      <form className="config-form" onSubmit={guardar}>
        <div className="config-form-campo">
          <label>Nombre</label>
          <input
            value={form.nombre}
            onChange={(e) => setForm({ ...form, nombre: e.target.value })}
            required
          />
        </div>

        <div className="config-form-campo">
          <label>Tipo de equipo</label>
          <input
            value={form.tipo}
            onChange={(e) => setForm({ ...form, tipo: e.target.value })}
            placeholder="Motor eléctrico monofásico"
            required
          />
        </div>

        <div className="config-form-campo">
          <label>Planta (opcional)</label>
          <input
            value={form.planta}
            onChange={(e) => setForm({ ...form, planta: e.target.value })}
          />
        </div>

        <div className="config-form-campo">
          <label>Potencia (kW, opcional)</label>
          <input
            type="number"
            step="0.1"
            value={form.potencia_kw}
            onChange={(e) => setForm({ ...form, potencia_kw: e.target.value })}
          />
        </div>

        <div className="config-form-campo">
          <label>RPM nominal (opcional, para diagnóstico)</label>
          <input
            type="number"
            step="1"
            value={form.rpm_nominal}
            onChange={(e) => setForm({ ...form, rpm_nominal: e.target.value })}
          />
        </div>

        <div className="config-form-campo">
          <label>Tipo de soporte (opcional, para severidad ISO 20816-3)</label>
          <select
            value={form.tipo_soporte}
            onChange={(e) => setForm({ ...form, tipo_soporte: e.target.value })}
          >
            <option value="">No especificado</option>
            <option value="rigido">Rígido</option>
            <option value="flexible">Flexible</option>
          </select>
        </div>

        <div className="config-form-campo">
          <label>Estado</label>
          <select value={form.estado} onChange={(e) => setForm({ ...form, estado: e.target.value })}>
            <option value="normal">Normal</option>
            <option value="advertencia">Advertencia</option>
            <option value="critico">Crítico</option>
            <option value="inactivo">Fuera de línea</option>
          </select>
        </div>

        <div className="config-form-acciones">
          <button type="submit" className="config-boton-primario">
            {editandoId ? "Guardar cambios" : "Agregar equipo"}
          </button>
          {editandoId && (
            <button type="button" className="config-boton-secundario" onClick={limpiarForm}>
              Cancelar
            </button>
          )}
        </div>

        {mensaje && <p className="config-error">{mensaje}</p>}
      </form>

      {cargando && <p className="config-mensaje">Cargando…</p>}
      {error && <p className="config-error">{error}</p>}

      <table className="config-tabla">
        <thead>
          <tr>
            <th>Nombre</th>
            <th>Tipo</th>
            <th>Planta</th>
            <th>Potencia</th>
            <th>RPM nominal</th>
            <th>Soporte</th>
            <th>Estado</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          {items.map((equipo) => (
            <tr key={equipo.id}>
              <td>{equipo.nombre}</td>
              <td>{equipo.tipo}</td>
              <td>{equipo.planta ?? "—"}</td>
              <td>{equipo.potencia_kw !== null ? `${equipo.potencia_kw} kW` : "—"}</td>
              <td>{equipo.rpm_nominal !== null ? `${equipo.rpm_nominal} RPM` : "—"}</td>
              <td>{equipo.tipo_soporte === "rigido" ? "Rígido" : equipo.tipo_soporte === "flexible" ? "Flexible" : "—"}</td>
              <td>{equipo.estado}</td>
              <td className="config-tabla-acciones">
                <button type="button" onClick={() => editar(equipo)}>Editar</button>
                <button type="button" onClick={() => eliminar(equipo)}>Eliminar</button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

/* ========================================================== */
/* SENSORES                                                     */
/* ========================================================== */

const FAMILIA_PERSONALIZADO = "Personalizado"
const FORM_SENSOR_VACIO = {
  equipo_id: "",
  tipo_sensor_id: "",
  unidades_seleccionadas: [],
  estado: "activo",
  ubicacion: "",
  rodamiento_id: "",
  orientacion_ejes: {},
}

const OPCIONES_ORIENTACION = [
  { valor: "", etiqueta: "No especificado" },
  { valor: "radial_horizontal", etiqueta: "Radial horizontal" },
  { valor: "radial_vertical", etiqueta: "Radial vertical" },
  { valor: "axial", etiqueta: "Axial" },
]

// Unidades estandar para la familia "Vibracion" (D-052, ver PROYECTO.md) -
// el mismo vocabulario ya curado en conocimiento/catalogo_sensores.csv, y
// las unicas que backend/procesamiento/severidad_iso.py reconoce para
// aceleracion/velocidad (desplazamiento se deja disponible para el
// catalogo aunque todavia no lo consume ningun calculo). Elegirlas con el
// mouse (en vez de texto libre) evita que un typo (ej. "mm/seg" en vez de
// "mm/s") haga que una medicion real quede con una unidad no reconocida.
const UNIDADES_VIBRACION_ESTANDAR = {
  "Aceleración": ["m/s2", "cm/s2", "g"],
  "Velocidad": ["mm/s", "in/s"],
  "Desplazamiento": ["um", "mm", "mils"],
}

const ABREVIATURA_ORIENTACION = {
  radial_horizontal: "rad.H",
  radial_vertical: "rad.V",
  axial: "axial",
}

function formatearOrientacion(orientacionEjes) {
  const entradas = Object.entries(orientacionEjes ?? {})
  if (entradas.length === 0) return "—"
  return entradas
    .map(([eje, orientacion]) => `${eje.toUpperCase()}:${ABREVIATURA_ORIENTACION[orientacion] ?? orientacion}`)
    .join(", ")
}

function derivarEjes(parametrosFisicos) {
  const texto = (parametrosFisicos ?? "").toLowerCase()

  if (texto.includes("eje x") && texto.includes("eje y") && texto.includes("eje z")) {
    return ["X", "Y", "Z"]
  }

  return ["X"]
}

// Los tipos del catalogo curado (conocimiento/catalogo_sensores.csv) ya
// vienen con familia "Vibracion", pero los tipos creados a mano antes de
// D-034 (D-038) quedan en familia "Personalizado" (D-034) aunque
// fisicamente sean sensores de vibracion - por eso no basta con mirar la
// familia, hay que revisar tambien parametros_fisicos (mismo criterio que
// ya usa derivarEjes()).
function esTipoVibracion(tipoSensor) {
  if (tipoSensor.familia === "Vibracion") return true
  const texto = (tipoSensor.parametros_fisicos ?? "").toLowerCase()
  return texto.includes("aceleracion") || texto.includes("velocidad vibratoria") || texto.includes("vibracion")
}

function SeccionSensores() {
  const { items, cargando, error, recargar } = useColeccion("/api/sensores")
  const { items: equipos } = useColeccion("/api/equipos")
  const { items: tiposSensor, recargar: recargarTipos } = useColeccion("/api/tipos-sensor")
  const { items: rodamientos } = useColeccion("/api/rodamientos")

  const [editandoId, setEditandoId] = useState(null)
  const [form, setForm] = useState(FORM_SENSOR_VACIO)
  const [mensaje, setMensaje] = useState("")

  const [busquedaTipo, setBusquedaTipo] = useState("")
  const [filtroFamilia, setFiltroFamilia] = useState("")
  const [mostrandoCrearTipo, setMostrandoCrearTipo] = useState(false)
  const [nuevoTipo, setNuevoTipo] = useState({ nombre: "", nemonico: "", parametros_fisicos: "", unidad_inicial: "" })
  const [nuevaUnidad, setNuevaUnidad] = useState("")

  const rodamientosDelEquipo = rodamientos.filter(
    (r) => r.equipo_id === Number(form.equipo_id)
  )

  const familias = [...new Set(tiposSensor.map((t) => t.familia).filter(Boolean))].sort()

  const tiposFiltrados = tiposSensor.filter((tipo) => {
    const coincideFamilia = !filtroFamilia || tipo.familia === filtroFamilia
    const texto = busquedaTipo.trim().toLowerCase()
    const coincideBusqueda =
      !texto ||
      tipo.nombre.toLowerCase().includes(texto) ||
      (tipo.familia ?? "").toLowerCase().includes(texto)
    return coincideFamilia && coincideBusqueda
  })

  const tiposPorFamilia = tiposFiltrados.reduce((acc, tipo) => {
    const familia = tipo.familia ?? "Sin familia"
    acc[familia] = acc[familia] ?? []
    acc[familia].push(tipo)
    return acc
  }, {})

  const tipoSeleccionado = tiposSensor.find((t) => t.id === Number(form.tipo_sensor_id)) ?? null

  function limpiarForm() {
    setForm(FORM_SENSOR_VACIO)
    setEditandoId(null)
    setMostrandoCrearTipo(false)
    setNuevoTipo({ nombre: "", nemonico: "", parametros_fisicos: "", unidad_inicial: "" })
    setNuevaUnidad("")
  }

  function editar(sensor) {
    setEditandoId(sensor.id)
    setForm({
      equipo_id: String(sensor.equipo_id),
      tipo_sensor_id: String(sensor.tipo_sensor_id ?? ""),
      unidades_seleccionadas: sensor.unidades ?? [],
      estado: sensor.estado,
      ubicacion: sensor.ubicacion ?? "",
      rodamiento_id: sensor.rodamiento_id ? String(sensor.rodamiento_id) : "",
      orientacion_ejes: sensor.orientacion_ejes ?? {},
    })
    setMostrandoCrearTipo(false)
  }

  function alternarUnidad(unidad) {
    setForm((actual) => {
      const yaElegida = actual.unidades_seleccionadas.includes(unidad)
      return {
        ...actual,
        unidades_seleccionadas: yaElegida
          ? actual.unidades_seleccionadas.filter((u) => u !== unidad)
          : [...actual.unidades_seleccionadas, unidad],
      }
    })
  }

  function cambiarOrientacionEje(eje, valor) {
    setForm((actual) => {
      const clave = eje.toLowerCase()
      const siguiente = { ...actual.orientacion_ejes }
      if (valor === "") {
        delete siguiente[clave]
      } else {
        siguiente[clave] = valor
      }
      return { ...actual, orientacion_ejes: siguiente }
    })
  }

  async function crearTipoSensor(evento) {
    evento.preventDefault()
    setMensaje("")

    if (!nuevoTipo.nombre.trim() || !nuevoTipo.nemonico.trim() || !nuevoTipo.unidad_inicial.trim()) {
      setMensaje("Completa el nombre, el nemónico y al menos una unidad para el tipo de sensor nuevo.")
      return
    }

    try {
      const creado = await enviarJSON(`${URL_BASE}/api/tipos-sensor`, "POST", nuevoTipo)
      await recargarTipos()
      setForm((actual) => ({ ...actual, tipo_sensor_id: String(creado.id), unidades_seleccionadas: [] }))
      setMostrandoCrearTipo(false)
      setNuevoTipo({ nombre: "", nemonico: "", parametros_fisicos: "", unidad_inicial: "" })
    } catch (err) {
      setMensaje(err.message)
    }
  }

  async function agregarUnidad() {
    setMensaje("")

    if (!tipoSeleccionado || !nuevaUnidad.trim()) {
      return
    }

    try {
      await enviarJSON(
        `${URL_BASE}/api/tipos-sensor/${tipoSeleccionado.id}/unidades`,
        "POST",
        { unidad: nuevaUnidad.trim() }
      )
      await recargarTipos()
      setNuevaUnidad("")
    } catch (err) {
      setMensaje(err.message)
    }
  }

  async function agregarUnidadEstandar(evento) {
    const unidad = evento.target.value
    evento.target.value = ""
    if (!tipoSeleccionado || !unidad) return

    setMensaje("")
    try {
      await enviarJSON(
        `${URL_BASE}/api/tipos-sensor/${tipoSeleccionado.id}/unidades`,
        "POST",
        { unidad }
      )
      await recargarTipos()
    } catch (err) {
      setMensaje(err.message)
    }
  }

  async function guardar(evento) {
    evento.preventDefault()
    setMensaje("")

    if (!form.equipo_id || !form.tipo_sensor_id) {
      setMensaje("Completa el equipo y el tipo de sensor antes de guardar.")
      return
    }

    if (form.unidades_seleccionadas.length === 0) {
      setMensaje("Elige al menos una unidad de medida para este sensor.")
      return
    }

    const cuerpo = {
      ...form,
      equipo_id: Number(form.equipo_id),
      tipo_sensor_id: Number(form.tipo_sensor_id),
      ubicacion: form.ubicacion.trim() === "" ? null : form.ubicacion.trim(),
      rodamiento_id: form.rodamiento_id === "" ? null : Number(form.rodamiento_id),
    }

    try {
      if (editandoId) {
        await enviarJSON(`${URL_BASE}/api/sensores/${editandoId}`, "PUT", cuerpo)
      } else {
        await enviarJSON(`${URL_BASE}/api/sensores`, "POST", cuerpo)
      }
      limpiarForm()
      recargar()
    } catch (err) {
      setMensaje(err.message)
    }
  }

  async function eliminar(sensor) {
    if (!window.confirm(`¿Estás seguro que deseas eliminar el sensor "${sensor.codigo ?? sensor.tipo}" de "${sensor.equipo_nombre}"?`)) {
      return
    }
    await apiFetch(`${URL_BASE}/api/sensores/${sensor.id}`, { method: "DELETE" })
    recargar()
  }

  return (
    <div className="config-seccion">
      <form className="config-form" onSubmit={guardar}>
        <div className="config-form-campo">
          <label>Equipo</label>
          <select
            value={form.equipo_id}
            onChange={(e) => setForm({ ...form, equipo_id: e.target.value, rodamiento_id: "" })}
            required
          >
            <option value="" disabled>Selecciona un equipo</option>
            {equipos.map((equipo) => (
              <option key={equipo.id} value={equipo.id}>{equipo.nombre}</option>
            ))}
          </select>
        </div>

        <div className="config-form-campo config-form-campo-ancho">
          <label>Buscar tipo de sensor (por nombre o familia)</label>
          <input
            value={busquedaTipo}
            onChange={(e) => setBusquedaTipo(e.target.value)}
            placeholder="Ej: triaxial, temperatura, vibración..."
          />
        </div>

        <div className="config-form-campo">
          <label>Familia</label>
          <select value={filtroFamilia} onChange={(e) => setFiltroFamilia(e.target.value)}>
            <option value="">Todas</option>
            {familias.map((familia) => (
              <option key={familia} value={familia}>{familia}</option>
            ))}
          </select>
        </div>

        <div className="config-form-campo config-form-campo-ancho">
          <label>Tipo de sensor</label>
          <select
            value={form.tipo_sensor_id}
            onChange={(e) => setForm({ ...form, tipo_sensor_id: e.target.value, unidades_seleccionadas: [] })}
            size={6}
          >
            {Object.entries(tiposPorFamilia).map(([familia, tipos]) => (
              <optgroup key={familia} label={familia}>
                {tipos.map((tipo) => (
                  <option key={tipo.id} value={tipo.id}>{tipo.nombre}</option>
                ))}
              </optgroup>
            ))}
          </select>

          {!mostrandoCrearTipo && (
            <button
              type="button"
              className="config-boton-secundario"
              onClick={() => setMostrandoCrearTipo(true)}
            >
              ¿No está en la lista? Crear tipo de sensor nuevo
            </button>
          )}
        </div>

        {mostrandoCrearTipo && (
          <div className="config-form-campo config-form-campo-ancho config-subformulario">
            <label>Nuevo tipo de sensor (familia: {FAMILIA_PERSONALIZADO})</label>
            <input
              value={nuevoTipo.nombre}
              onChange={(e) => setNuevoTipo({ ...nuevoTipo, nombre: e.target.value })}
              placeholder="Nombre del sensor"
            />
            <input
              value={nuevoTipo.nemonico}
              onChange={(e) => setNuevoTipo({ ...nuevoTipo, nemonico: e.target.value.toUpperCase() })}
              placeholder="Nemónico (ej: VIBPZO)"
            />
            <input
              value={nuevoTipo.parametros_fisicos}
              onChange={(e) => setNuevoTipo({ ...nuevoTipo, parametros_fisicos: e.target.value })}
              placeholder="Qué mide (parámetros físicos, opcional)"
            />
            <input
              value={nuevoTipo.unidad_inicial}
              onChange={(e) => setNuevoTipo({ ...nuevoTipo, unidad_inicial: e.target.value })}
              placeholder="Unidad de medida inicial"
            />
            <div className="config-form-acciones">
              <button type="button" className="config-boton-primario" onClick={crearTipoSensor}>
                Crear tipo de sensor
              </button>
              <button type="button" className="config-boton-secundario" onClick={() => setMostrandoCrearTipo(false)}>
                Cancelar
              </button>
            </div>
          </div>
        )}

        {tipoSeleccionado && (
          <div className="config-form-campo config-form-campo-ancho config-subformulario">
            <label>
              Unidad(es) que usa este sensor — ejes: {derivarEjes(tipoSeleccionado.parametros_fisicos).join(", ")}
            </label>
            <div className="config-checkbox-grupo">
              {(tipoSeleccionado.unidades_disponibles ?? []).map((unidad) => (
                <label key={unidad} className="config-checkbox">
                  <input
                    type="checkbox"
                    checked={form.unidades_seleccionadas.includes(unidad)}
                    onChange={() => alternarUnidad(unidad)}
                  />
                  {unidad}
                </label>
              ))}
              {(tipoSeleccionado.unidades_disponibles ?? []).length === 0 && (
                <p className="config-mensaje">Este tipo todavía no tiene unidades — agrega la primera abajo.</p>
              )}
            </div>

            {esTipoVibracion(tipoSeleccionado) ? (
              <div className="config-form-acciones">
                <select value="" onChange={agregarUnidadEstandar}>
                  <option value="" disabled>Agregar unidad estándar de vibración…</option>
                  {Object.entries(UNIDADES_VIBRACION_ESTANDAR).map(([categoria, unidades]) => {
                    const pendientes = unidades.filter(
                      (u) => !(tipoSeleccionado.unidades_disponibles ?? []).includes(u)
                    )
                    if (pendientes.length === 0) return null
                    return (
                      <optgroup key={categoria} label={categoria}>
                        {pendientes.map((u) => <option key={u} value={u}>{u}</option>)}
                      </optgroup>
                    )
                  })}
                </select>
              </div>
            ) : (
              <div className="config-form-acciones">
                <input
                  value={nuevaUnidad}
                  onChange={(e) => setNuevaUnidad(e.target.value)}
                  placeholder="Agregar otra unidad a este tipo (ej: %HR)"
                />
                <button type="button" className="config-boton-secundario" onClick={agregarUnidad}>
                  Agregar unidad
                </button>
              </div>
            )}
          </div>
        )}

        {tipoSeleccionado && (
          <div className="config-form-campo config-form-campo-ancho config-subformulario">
            <label>
              Orientación de cada eje (opcional — para distinguir vibración radial de axial en el
              diagnóstico, D-051)
            </label>
            {derivarEjes(tipoSeleccionado.parametros_fisicos).map((eje) => (
              <div key={eje} className="config-form-campo">
                <label>Eje {eje}</label>
                <select
                  value={form.orientacion_ejes[eje.toLowerCase()] ?? ""}
                  onChange={(e) => cambiarOrientacionEje(eje, e.target.value)}
                >
                  {OPCIONES_ORIENTACION.map((opcion) => (
                    <option key={opcion.valor} value={opcion.valor}>{opcion.etiqueta}</option>
                  ))}
                </select>
              </div>
            ))}
          </div>
        )}

        <div className="config-form-campo">
          <label>Ubicación (opcional)</label>
          <input
            value={form.ubicacion}
            onChange={(e) => setForm({ ...form, ubicacion: e.target.value })}
            placeholder="Ej: lado acople, extremo ventilador..."
          />
        </div>

        <div className="config-form-campo">
          <label>Rodamiento que monitorea (opcional)</label>
          <select
            value={form.rodamiento_id}
            onChange={(e) => setForm({ ...form, rodamiento_id: e.target.value })}
            disabled={!form.equipo_id}
          >
            <option value="">Ninguno</option>
            {rodamientosDelEquipo.map((rodamiento) => (
              <option key={rodamiento.id} value={rodamiento.id}>
                {rodamiento.codigo}{rodamiento.ubicacion ? ` — ${rodamiento.ubicacion}` : ""}
              </option>
            ))}
          </select>
        </div>

        <div className="config-form-campo">
          <label>Estado</label>
          <select value={form.estado} onChange={(e) => setForm({ ...form, estado: e.target.value })}>
            <option value="activo">Activo</option>
            <option value="inactivo">Inactivo</option>
          </select>
        </div>

        <div className="config-form-acciones">
          <button type="submit" className="config-boton-primario">
            {editandoId ? "Guardar cambios" : "Agregar sensor"}
          </button>
          {editandoId && (
            <button type="button" className="config-boton-secundario" onClick={limpiarForm}>
              Cancelar
            </button>
          )}
        </div>

        {mensaje && <p className="config-error">{mensaje}</p>}
      </form>

      {cargando && <p className="config-mensaje">Cargando…</p>}
      {error && <p className="config-error">{error}</p>}

      <table className="config-tabla">
        <thead>
          <tr>
            <th>Código</th>
            <th>Equipo</th>
            <th>Familia</th>
            <th>Tipo</th>
            <th>Ubicación</th>
            <th>Rodamiento</th>
            <th>Unidad(es)</th>
            <th>Ejes</th>
            <th>Orientación</th>
            <th>Estado</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          {items.map((sensor) => (
            <tr key={sensor.id}>
              <td>{sensor.codigo ?? "—"}</td>
              <td>{sensor.equipo_nombre}</td>
              <td>{sensor.familia ?? "—"}</td>
              <td>{sensor.tipo}</td>
              <td>{sensor.ubicacion ?? "—"}</td>
              <td>{sensor.rodamiento_codigo ?? "—"}</td>
              <td>{(sensor.unidades ?? []).join(", ") || "—"}</td>
              <td>{(sensor.ejes ?? []).join(", ") || "—"}</td>
              <td>{formatearOrientacion(sensor.orientacion_ejes)}</td>
              <td>{sensor.estado}</td>
              <td className="config-tabla-acciones">
                <button type="button" onClick={() => editar(sensor)}>Editar</button>
                <button type="button" onClick={() => eliminar(sensor)}>Eliminar</button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

/* ========================================================== */
/* RODAMIENTOS                                                  */
/* ========================================================== */

const FORM_RODAMIENTO_VACIO = {
  equipo_id: "",
  ubicacion: "",
  modelo: "",
  numero_elementos_rodantes: "",
  diametro_elemento_mm: "",
  diametro_paso_mm: "",
  angulo_contacto_grados: "",
}

function SeccionRodamientos() {
  const { items, cargando, error, recargar } = useColeccion("/api/rodamientos")
  const { items: equipos } = useColeccion("/api/equipos")

  const [editandoId, setEditandoId] = useState(null)
  const [form, setForm] = useState(FORM_RODAMIENTO_VACIO)
  const [mensaje, setMensaje] = useState("")

  function limpiarForm() {
    setForm(FORM_RODAMIENTO_VACIO)
    setEditandoId(null)
  }

  function editar(rodamiento) {
    setEditandoId(rodamiento.id)
    setForm({
      equipo_id: String(rodamiento.equipo_id),
      ubicacion: rodamiento.ubicacion ?? "",
      modelo: rodamiento.modelo ?? "",
      numero_elementos_rodantes: rodamiento.numero_elementos_rodantes ?? "",
      diametro_elemento_mm: rodamiento.diametro_elemento_mm ?? "",
      diametro_paso_mm: rodamiento.diametro_paso_mm ?? "",
      angulo_contacto_grados: rodamiento.angulo_contacto_grados ?? "",
    })
  }

  async function guardar(evento) {
    evento.preventDefault()
    setMensaje("")

    if (!form.equipo_id) {
      setMensaje("Selecciona el equipo al que pertenece este rodamiento.")
      return
    }

    const cuerpo = {
      equipo_id: Number(form.equipo_id),
      ubicacion: form.ubicacion.trim() === "" ? null : form.ubicacion.trim(),
      modelo: form.modelo.trim() === "" ? null : form.modelo.trim(),
      numero_elementos_rodantes: form.numero_elementos_rodantes === "" ? null : Number(form.numero_elementos_rodantes),
      diametro_elemento_mm: form.diametro_elemento_mm === "" ? null : Number(form.diametro_elemento_mm),
      diametro_paso_mm: form.diametro_paso_mm === "" ? null : Number(form.diametro_paso_mm),
      angulo_contacto_grados: form.angulo_contacto_grados === "" ? null : Number(form.angulo_contacto_grados),
    }

    try {
      if (editandoId) {
        await enviarJSON(`${URL_BASE}/api/rodamientos/${editandoId}`, "PUT", cuerpo)
      } else {
        await enviarJSON(`${URL_BASE}/api/rodamientos`, "POST", cuerpo)
      }
      limpiarForm()
      recargar()
    } catch (err) {
      setMensaje(err.message)
    }
  }

  async function eliminar(rodamiento) {
    if (!window.confirm(`¿Estás seguro que deseas eliminar el rodamiento "${rodamiento.codigo}" de "${rodamiento.equipo_nombre}"?`)) {
      return
    }
    await apiFetch(`${URL_BASE}/api/rodamientos/${rodamiento.id}`, { method: "DELETE" })
    recargar()
  }

  return (
    <div className="config-seccion">
      <p className="config-nota">
        La geometría es opcional: se completa cuando se conoce la ficha técnica del
        rodamiento. Sin ella no se pueden calcular sus frecuencias de falla
        (BPFO/BPFI/BSF/FTF) — eso es un paso posterior a este catálogo.
      </p>

      <form className="config-form" onSubmit={guardar}>
        <div className="config-form-campo">
          <label>Equipo</label>
          <select
            value={form.equipo_id}
            onChange={(e) => setForm({ ...form, equipo_id: e.target.value })}
            required
          >
            <option value="" disabled>Selecciona un equipo</option>
            {equipos.map((equipo) => (
              <option key={equipo.id} value={equipo.id}>{equipo.nombre}</option>
            ))}
          </select>
        </div>

        <div className="config-form-campo">
          <label>Ubicación (opcional)</label>
          <input
            value={form.ubicacion}
            onChange={(e) => setForm({ ...form, ubicacion: e.target.value })}
            placeholder="Ej: lado acople, lado ventilador..."
          />
        </div>

        <div className="config-form-campo">
          <label>Modelo (opcional)</label>
          <input
            value={form.modelo}
            onChange={(e) => setForm({ ...form, modelo: e.target.value })}
            placeholder="Ej: SKF 6205-2RS"
          />
        </div>

        <div className="config-form-campo">
          <label>N° de elementos rodantes (opcional)</label>
          <input
            type="number"
            step="1"
            value={form.numero_elementos_rodantes}
            onChange={(e) => setForm({ ...form, numero_elementos_rodantes: e.target.value })}
          />
        </div>

        <div className="config-form-campo">
          <label>Diámetro del elemento (mm, opcional)</label>
          <input
            type="number"
            step="0.01"
            value={form.diametro_elemento_mm}
            onChange={(e) => setForm({ ...form, diametro_elemento_mm: e.target.value })}
          />
        </div>

        <div className="config-form-campo">
          <label>Diámetro de paso (mm, opcional)</label>
          <input
            type="number"
            step="0.01"
            value={form.diametro_paso_mm}
            onChange={(e) => setForm({ ...form, diametro_paso_mm: e.target.value })}
          />
        </div>

        <div className="config-form-campo">
          <label>Ángulo de contacto (grados, opcional)</label>
          <input
            type="number"
            step="0.1"
            value={form.angulo_contacto_grados}
            onChange={(e) => setForm({ ...form, angulo_contacto_grados: e.target.value })}
          />
        </div>

        <div className="config-form-acciones">
          <button type="submit" className="config-boton-primario">
            {editandoId ? "Guardar cambios" : "Agregar rodamiento"}
          </button>
          {editandoId && (
            <button type="button" className="config-boton-secundario" onClick={limpiarForm}>
              Cancelar
            </button>
          )}
        </div>

        {mensaje && <p className="config-error">{mensaje}</p>}
      </form>

      {cargando && <p className="config-mensaje">Cargando…</p>}
      {error && <p className="config-error">{error}</p>}

      <table className="config-tabla">
        <thead>
          <tr>
            <th>Código</th>
            <th>Equipo</th>
            <th>Ubicación</th>
            <th>Modelo</th>
            <th>Geometría</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          {items.map((rodamiento) => (
            <tr key={rodamiento.id}>
              <td>{rodamiento.codigo}</td>
              <td>{rodamiento.equipo_nombre}</td>
              <td>{rodamiento.ubicacion ?? "—"}</td>
              <td>{rodamiento.modelo ?? "—"}</td>
              <td>{rodamiento.geometria_completa ? "Completa" : "Incompleta"}</td>
              <td className="config-tabla-acciones">
                <button type="button" onClick={() => editar(rodamiento)}>Editar</button>
                <button type="button" onClick={() => eliminar(rodamiento)}>Eliminar</button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

/* ========================================================== */
/* MODELOS DE APRENDIZAJE                                       */
/* ========================================================== */

function SeccionModelos() {
  const { items, cargando, error, recargar } = useColeccion("/api/modelos-ml")
  const [editandoId, setEditandoId] = useState(null)
  const [form, setForm] = useState({ nombre: "", tipo: "", version: "0.1", estado: "planificado", descripcion: "" })
  const [mensaje, setMensaje] = useState("")

  function limpiarForm() {
    setForm({ nombre: "", tipo: "", version: "0.1", estado: "planificado", descripcion: "" })
    setEditandoId(null)
  }

  function editar(modelo) {
    setEditandoId(modelo.id)
    setForm({
      nombre: modelo.nombre,
      tipo: modelo.tipo,
      version: modelo.version,
      estado: modelo.estado,
      descripcion: modelo.descripcion ?? "",
    })
  }

  async function guardar(evento) {
    evento.preventDefault()
    setMensaje("")

    try {
      if (editandoId) {
        await enviarJSON(`${URL_BASE}/api/modelos-ml/${editandoId}`, "PUT", form)
      } else {
        await enviarJSON(`${URL_BASE}/api/modelos-ml`, "POST", form)
      }
      limpiarForm()
      recargar()
    } catch (err) {
      setMensaje(err.message)
    }
  }

  async function eliminar(modelo) {
    if (!window.confirm(`¿Estás seguro que deseas eliminar el modelo "${modelo.nombre}"?`)) {
      return
    }
    await apiFetch(`${URL_BASE}/api/modelos-ml/${modelo.id}`, { method: "DELETE" })
    recargar()
  }

  return (
    <div className="config-seccion">
      <p className="config-nota">
        Este catálogo solo registra metadata de modelos (no entrena ni ejecuta
        inferencia todavía — ver Fase 9 del roadmap).
      </p>

      <form className="config-form" onSubmit={guardar}>
        <div className="config-form-campo">
          <label>Nombre</label>
          <input
            value={form.nombre}
            onChange={(e) => setForm({ ...form, nombre: e.target.value })}
            required
          />
        </div>

        <div className="config-form-campo">
          <label>Tipo</label>
          <input
            value={form.tipo}
            onChange={(e) => setForm({ ...form, tipo: e.target.value })}
            placeholder="autoencoder, clasificador_fallas..."
            required
          />
        </div>

        <div className="config-form-campo">
          <label>Versión</label>
          <input
            value={form.version}
            onChange={(e) => setForm({ ...form, version: e.target.value })}
          />
        </div>

        <div className="config-form-campo">
          <label>Estado</label>
          <select value={form.estado} onChange={(e) => setForm({ ...form, estado: e.target.value })}>
            <option value="planificado">Planificado</option>
            <option value="entrenando">Entrenando</option>
            <option value="activo">Activo</option>
            <option value="obsoleto">Obsoleto</option>
          </select>
        </div>

        <div className="config-form-campo config-form-campo-ancho">
          <label>Descripción</label>
          <textarea
            value={form.descripcion}
            onChange={(e) => setForm({ ...form, descripcion: e.target.value })}
            rows={2}
          />
        </div>

        <div className="config-form-acciones">
          <button type="submit" className="config-boton-primario">
            {editandoId ? "Guardar cambios" : "Agregar modelo"}
          </button>
          {editandoId && (
            <button type="button" className="config-boton-secundario" onClick={limpiarForm}>
              Cancelar
            </button>
          )}
        </div>

        {mensaje && <p className="config-error">{mensaje}</p>}
      </form>

      {cargando && <p className="config-mensaje">Cargando…</p>}
      {error && <p className="config-error">{error}</p>}

      <table className="config-tabla">
        <thead>
          <tr>
            <th>Nombre</th>
            <th>Tipo</th>
            <th>Versión</th>
            <th>Estado</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          {items.map((modelo) => (
            <tr key={modelo.id}>
              <td>{modelo.nombre}</td>
              <td>{modelo.tipo}</td>
              <td>{modelo.version}</td>
              <td>{modelo.estado}</td>
              <td className="config-tabla-acciones">
                <button type="button" onClick={() => editar(modelo)}>Editar</button>
                <button type="button" onClick={() => eliminar(modelo)}>Eliminar</button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

/* ========================================================== */
/* NOTIFICACIONES (D-054/D-055)                                 */
/* ========================================================== */

const ETIQUETA_CANAL = { correo: "Correo", telegram: "Telegram" }

function textoCredencialesConfiguradas(canal, estadoCanal) {
  if (canal !== "telegram") return "credenciales configuradas."
  if (estadoCanal.bot_usuario) {
    return `credenciales configuradas — el token corresponde al bot ${estadoCanal.bot_usuario}. Las personas deben escribirle /start a ese bot.`
  }
  if (estadoCanal.bot_error) {
    return `hay un token en .env, pero Telegram no lo aceptó (${estadoCanal.bot_error}). Revisa que sea el token completo y vigente.`
  }
  return "credenciales configuradas."
}

function formatearFechaUTC(texto) {
  if (!texto) return ""
  return new Date(`${texto}Z`).toLocaleString("es-CL")
}

function SeccionNotificaciones() {
  const { items: destinatarios, cargando, error, recargar } = useColeccion("/api/notificaciones/destinatarios")
  const { items: historial, recargar: recargarHistorial } = useColeccion("/api/notificaciones?limite=15")
  const [estado, setEstado] = useState(null)
  const [form, setForm] = useState({ nombre: "", canal: "correo", direccion: "" })
  const [mensaje, setMensaje] = useState("")
  const [resultadoPrueba, setResultadoPrueba] = useState([])
  const [chats, setChats] = useState(null)
  const [errorChats, setErrorChats] = useState("")
  const [buscandoChats, setBuscandoChats] = useState(false)
  const [cambiandoInterruptor, setCambiandoInterruptor] = useState(false)

  useEffect(() => {
    apiFetch(`${URL_BASE}/api/notificaciones/estado`)
      .then((respuesta) => (respuesta.ok ? respuesta.json() : null))
      .then(setEstado)
      .catch(() => setEstado(null))
  }, [])

  // Interruptor general: desactivar pide confirmación (apaga todos los avisos de una vez); activar no.
  async function alternarInterruptor() {
    const activar = !estado.habilitado
    if (
      !activar &&
      !window.confirm(
        "¿Estás seguro de que deseas desactivar TODAS las notificaciones (correo y Telegram)?\n\n" +
          "Mientras estén desactivadas, el sistema no avisará de ninguna alerta, aunque se detecte una falla " +
          "grave, y tampoco enviará mensajes de prueba."
      )
    ) {
      return
    }

    setMensaje("")
    setCambiandoInterruptor(true)
    try {
      const nuevoEstado = await enviarJSON(`${URL_BASE}/api/notificaciones/interruptor`, "PUT", { habilitado: activar })
      setEstado((actual) => ({ ...actual, ...nuevoEstado }))
    } catch (err) {
      setMensaje(err.message)
    } finally {
      setCambiandoInterruptor(false)
    }
  }

  async function agregar(evento) {
    evento.preventDefault()
    setMensaje("")
    try {
      await enviarJSON(`${URL_BASE}/api/notificaciones/destinatarios`, "POST", form)
      setForm({ nombre: "", canal: form.canal, direccion: "" })
      recargar()
      if (form.canal === "telegram" && chats !== null) buscarChats()
    } catch (err) {
      setMensaje(err.message)
    }
  }

  async function alternarActivo(destinatario) {
    setMensaje("")
    try {
      await enviarJSON(`${URL_BASE}/api/notificaciones/destinatarios/${destinatario.id}`, "PUT", {
        nombre: destinatario.nombre,
        direccion: destinatario.direccion,
        activo: !destinatario.activo,
      })
      recargar()
    } catch (err) {
      setMensaje(err.message)
    }
  }

  async function eliminar(destinatario) {
    if (!window.confirm(`¿Dejar de enviar alertas a "${destinatario.nombre}" (${destinatario.direccion})?`)) {
      return
    }
    await apiFetch(`${URL_BASE}/api/notificaciones/destinatarios/${destinatario.id}`, { method: "DELETE" })
    recargar()
  }

  async function probar(destinatario) {
    setMensaje("")
    setResultadoPrueba([])
    try {
      const ruta = destinatario
        ? `/api/notificaciones/destinatarios/${destinatario.id}/prueba`
        : "/api/notificaciones/prueba"
      const resultados = await enviarJSON(`${URL_BASE}${ruta}`, "POST", {})
      setResultadoPrueba(resultados)
      recargarHistorial()
    } catch (err) {
      setMensaje(err.message)
    }
  }

  async function buscarChats() {
    setBuscandoChats(true)
    setErrorChats("")
    try {
      const respuesta = await apiFetch(`${URL_BASE}/api/notificaciones/telegram/chats`)
      const datos = await respuesta.json().catch(() => null)
      if (!respuesta.ok) throw new Error(datos?.detail ?? "No fue posible consultar Telegram")
      setChats(datos)
    } catch (err) {
      setChats(null)
      setErrorChats(err.message)
    } finally {
      setBuscandoChats(false)
    }
  }

  function usarChat(chat) {
    setForm({ nombre: chat.nombre.replace(/\s*\(@.*\)$/, ""), canal: "telegram", direccion: chat.chat_id })
  }

  const esTelegram = form.canal === "telegram"

  return (
    <div className="config-seccion">
      <p className="config-nota">
        Aquí defines a quién se le envían las alertas. Cuando se carga una medición y el sistema detecta un hallazgo
        grave, avisa a cada destinatario activo (una sola vez por hallazgo, salvo que empeore). Las credenciales del
        servidor de correo y del bot de Telegram no se configuran aquí: van en el archivo <code>.env</code>.
      </p>

      {estado && (
        <div className={`interruptor-notificaciones ${estado.habilitado ? "" : "interruptor-notificaciones-apagado"}`}>
          <label className="interruptor">
            <input
              type="checkbox"
              role="switch"
              checked={estado.habilitado}
              onChange={alternarInterruptor}
              disabled={cambiandoInterruptor}
              aria-label="Activar o desactivar todas las notificaciones"
            />
            <span className="interruptor-pista" aria-hidden="true">
              <span className="interruptor-perilla" />
            </span>
          </label>

          <div>
            <strong>{estado.habilitado ? "Notificaciones activadas" : "Notificaciones desactivadas"}</strong>
            <p>
              {estado.habilitado
                ? "El sistema avisa por correo y Telegram a los destinatarios activos."
                : "El sistema no envía ningún aviso ni mensaje de prueba, aunque se detecte una falla grave."}{" "}
              {estado.origen === "interruptor"
                ? `Cambiado${estado.cambiado_por ? ` por ${estado.cambiado_por}` : ""} el ${formatearFechaUTC(estado.cambiado_en)}`
                : "Estado inicial tomado de config/notificaciones.yaml."}
            </p>
          </div>
        </div>
      )}

      {estado && (
        <div className="config-nota">
          {["correo", "telegram"].map((canal) => (
            <p key={canal}>
              <strong>{ETIQUETA_CANAL[canal]}:</strong>{" "}
              {estado[canal].configurado
                ? textoCredencialesConfiguradas(canal, estado[canal])
                : `sin credenciales — faltan en .env: ${estado[canal].variables_faltantes.join(", ")}.`}
            </p>
          ))}
        </div>
      )}

      <form className="config-form" onSubmit={agregar}>
        <div className="config-form-campo">
          <label>Canal</label>
          <select
            value={form.canal}
            onChange={(e) => {
              setForm({ ...form, canal: e.target.value, direccion: "" })
              setMensaje("")
            }}
          >
            <option value="correo">Correo electrónico</option>
            <option value="telegram">Telegram</option>
          </select>
        </div>

        <div className="config-form-campo">
          <label>Nombre</label>
          <input
            value={form.nombre}
            onChange={(e) => setForm({ ...form, nombre: e.target.value })}
            placeholder="Ej. Jefe de mantención"
            required
          />
        </div>

        <div className="config-form-campo">
          <label>{esTelegram ? "Chat ID de Telegram" : "Correo electrónico"}</label>
          <input
            type={esTelegram ? "text" : "email"}
            value={form.direccion}
            onChange={(e) => setForm({ ...form, direccion: e.target.value })}
            placeholder={esTelegram ? "Ej. 123456789 (negativo si es un grupo)" : "persona@empresa.cl"}
            required
          />
        </div>

        <div className="config-form-acciones">
          <button type="submit" className="config-boton-primario">Agregar destinatario</button>
          {esTelegram && (
            <button type="button" className="config-boton-secundario" onClick={buscarChats} disabled={buscandoChats}>
              {buscandoChats ? "Buscando…" : "Buscar quién le escribió al bot"}
            </button>
          )}
        </div>

        {mensaje && <p className="config-error">{mensaje}</p>}
      </form>

      {esTelegram && (
        <div className="config-nota">
          <p>
            Para agregar a alguien sin buscar su chat id: pídele que abra el bot de Telegram y le escriba{" "}
            <code>/start</code>; luego pulsa «Buscar quién le escribió al bot» y elige su nombre. Para un grupo,
            agrega el bot al grupo y escribe cualquier mensaje. Telegram solo conserva esos mensajes unas 24 horas.
          </p>
          {errorChats && <p className="config-error">{errorChats}</p>}
          {chats && chats.length === 0 && (
            <p>
              Nadie le ha escrito {estado?.telegram?.bot_usuario ? `a ${estado.telegram.bot_usuario}` : "al bot"} en
              las últimas 24 horas. Comprueba que el chat donde escribiste /start sea con ese bot (no con BotFather)
              y vuelve a buscar.
            </p>
          )}
          {chats && chats.length > 0 && (
            <table className="config-tabla">
              <thead>
                <tr>
                  <th>Nombre</th>
                  <th>Tipo</th>
                  <th>Chat ID</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {chats.map((chat) => (
                  <tr key={chat.chat_id}>
                    <td>{chat.nombre}</td>
                    <td>{chat.tipo === "private" ? "Persona" : chat.tipo}</td>
                    <td>{chat.chat_id}</td>
                    <td className="config-tabla-acciones">
                      {chat.ya_agregado ? (
                        <span>Ya agregado</span>
                      ) : (
                        <button type="button" onClick={() => usarChat(chat)}>Usar este chat</button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}

      {cargando && <p className="config-mensaje">Cargando…</p>}
      {error && <p className="config-error">{error}</p>}

      <table className="config-tabla">
        <thead>
          <tr>
            <th>Nombre</th>
            <th>Canal</th>
            <th>Destino</th>
            <th>Recibe alertas</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          {destinatarios.length === 0 && !cargando && (
            <tr>
              <td colSpan={5}>Todavía no hay destinatarios. Agrega el primero arriba.</td>
            </tr>
          )}
          {destinatarios.map((destinatario) => {
            const esDeEnv = destinatario.origen === "env"
            return (
              <tr key={destinatario.id ?? `env-${destinatario.canal}-${destinatario.direccion}`}>
                <td>{destinatario.nombre}</td>
                <td>{ETIQUETA_CANAL[destinatario.canal]}</td>
                <td>{destinatario.direccion}</td>
                <td>
                  {esDeEnv ? (
                    "Sí (se cambia en .env)"
                  ) : (
                    <input
                      type="checkbox"
                      checked={destinatario.activo}
                      onChange={() => alternarActivo(destinatario)}
                      aria-label={`Recibe alertas: ${destinatario.nombre}`}
                    />
                  )}
                </td>
                <td className="config-tabla-acciones">
                  {!esDeEnv && (
                    <>
                      <button type="button" onClick={() => probar(destinatario)}>Enviar prueba</button>
                      <button type="button" onClick={() => eliminar(destinatario)}>Eliminar</button>
                    </>
                  )}
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>

      <div className="config-form-acciones">
        <button type="button" className="config-boton-secundario" onClick={() => probar(null)}>
          Enviar prueba a todos los activos
        </button>
      </div>

      {resultadoPrueba.length > 0 && (
        <div className="config-nota">
          {resultadoPrueba.map((r, indice) => (
            <p key={indice}>
              {r.canal === "todos" ? (
                <strong>Mensaje de prueba:</strong>
              ) : (
                <strong>{ETIQUETA_CANAL[r.canal]} → {r.nombre} ({r.direccion}):</strong>
              )}{" "}
              {r.resultado}
            </p>
          ))}
        </div>
      )}

      <h3>Avisos recientes</h3>
      <table className="config-tabla">
        <thead>
          <tr>
            <th>Fecha</th>
            <th>Equipo</th>
            <th>Canal</th>
            <th>Destinatario</th>
            <th>Estado</th>
          </tr>
        </thead>
        <tbody>
          {historial.length === 0 && (
            <tr>
              <td colSpan={5}>Todavía no se ha enviado ningún aviso.</td>
            </tr>
          )}
          {historial.map((aviso) => (
            <tr key={aviso.id}>
              <td>{formatearFechaUTC(aviso.fecha_envio)}</td>
              <td>{aviso.equipo_nombre}</td>
              <td>{ETIQUETA_CANAL[aviso.canal] ?? aviso.canal}</td>
              <td>{aviso.destinatario ?? "—"}</td>
              <td title={aviso.detalle ?? ""}>{aviso.estado === "enviada" ? "Enviada" : `Fallida: ${aviso.detalle ?? ""}`}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

/* ========================================================== */
/* PAGINA PRINCIPAL                                             */
/* ========================================================== */

const PESTANAS = [
  { id: "usuarios", nombre: "Usuarios" },
  { id: "equipos", nombre: "Equipos" },
  { id: "sensores", nombre: "Sensores" },
  { id: "rodamientos", nombre: "Rodamientos" },
  { id: "modelos", nombre: "Modelos de Aprendizaje" },
  { id: "notificaciones", nombre: "Notificaciones" },
]

function Configuracion({ sesion, onCerrarSesion, onIrAResumen, onIrAReportes, onIrALaboratorio, onSeleccionarEquipo }) {
  const [pestanaActiva, setPestanaActiva] = useState("usuarios")

  const iniciales = sesion.usuario.nombre
    .split(" ")
    .map((parte) => parte[0])
    .slice(0, 2)
    .join("")
    .toUpperCase()

  return (
    <div className="app-shell">
      <Sidebar
        vistaActiva="configuracion"
        onIrAResumen={onIrAResumen}
        onIrAConfiguracion={() => {}}
        onIrAReportes={onIrAReportes}
        onIrALaboratorio={onIrALaboratorio}
        equipoActivoId={null}
        onSeleccionarEquipo={onSeleccionarEquipo}
      />

      <div className="main-area">
        <header className="topbar">
          <p className="topbar-equipo">Configuración</p>

          <div className="topbar-user">
            <div className="usuario-avatar">{iniciales}</div>

            <div className="usuario-info">
              <strong>{sesion.usuario.nombre}</strong>
              <small>
                {sesion.usuario.rol === "administrador"
                  ? "Administrador"
                  : sesion.usuario.rol}
              </small>
            </div>

            <button type="button" className="boton-salir" onClick={onCerrarSesion}>
              SALIR
            </button>
          </div>
        </header>

        <main className="dashboard-content">
          <nav className="pestanas">
            {PESTANAS.map((pestana) => (
              <button
                key={pestana.id}
                type="button"
                className={`pestana ${pestanaActiva === pestana.id ? "activa" : ""}`}
                onClick={() => setPestanaActiva(pestana.id)}
              >
                {pestana.nombre}
              </button>
            ))}
          </nav>

          <section className="tarjeta">
            {pestanaActiva === "usuarios" && <SeccionUsuarios />}
            {pestanaActiva === "equipos" && <SeccionEquipos />}
            {pestanaActiva === "sensores" && <SeccionSensores />}
            {pestanaActiva === "rodamientos" && <SeccionRodamientos />}
            {pestanaActiva === "modelos" && <SeccionModelos />}
            {pestanaActiva === "notificaciones" && <SeccionNotificaciones />}
          </section>
        </main>
      </div>
    </div>
  )
}

export default Configuracion
