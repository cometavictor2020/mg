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
  const [form, setForm] = useState({ nombre: "", tipo: "", planta: "", estado: "normal", potencia_kw: "" })
  const [mensaje, setMensaje] = useState("")

  function limpiarForm() {
    setForm({ nombre: "", tipo: "", planta: "", estado: "normal", potencia_kw: "" })
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
    })
  }

  async function guardar(evento) {
    evento.preventDefault()
    setMensaje("")

    const cuerpo = {
      ...form,
      potencia_kw: form.potencia_kw === "" ? null : Number(form.potencia_kw),
      planta: form.planta === "" ? null : form.planta,
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

function SeccionSensores() {
  const { items, cargando, error, recargar } = useColeccion("/api/sensores")
  const { items: equipos } = useColeccion("/api/equipos")
  const [editandoId, setEditandoId] = useState(null)
  const [form, setForm] = useState({ equipo_id: "", tipo: "", estado: "activo" })
  const [mensaje, setMensaje] = useState("")

  function limpiarForm() {
    setForm({ equipo_id: "", tipo: "", estado: "activo" })
    setEditandoId(null)
  }

  function editar(sensor) {
    setEditandoId(sensor.id)
    setForm({ equipo_id: String(sensor.equipo_id), tipo: sensor.tipo ?? "", estado: sensor.estado })
  }

  async function guardar(evento) {
    evento.preventDefault()
    setMensaje("")

    if (!form.equipo_id || !form.tipo.trim()) {
      setMensaje("Completa el equipo y el tipo de sensor antes de guardar.")
      return
    }

    const cuerpo = { ...form, equipo_id: Number(form.equipo_id) }

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
    if (!window.confirm(`¿Estás seguro que deseas eliminar el sensor "${sensor.tipo}" de "${sensor.equipo_nombre}"?`)) {
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
          <label>Tipo de sensor</label>
          <input
            value={form.tipo}
            onChange={(e) => setForm({ ...form, tipo: e.target.value })}
            placeholder="Ej: Acelerómetro triaxial"
            required
          />
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
            <th>Equipo</th>
            <th>Tipo</th>
            <th>Estado</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          {items.map((sensor) => (
            <tr key={sensor.id}>
              <td>{sensor.equipo_nombre}</td>
              <td>{sensor.tipo}</td>
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
/* PAGINA PRINCIPAL                                             */
/* ========================================================== */

const PESTANAS = [
  { id: "usuarios", nombre: "Usuarios" },
  { id: "equipos", nombre: "Equipos" },
  { id: "sensores", nombre: "Sensores" },
  { id: "modelos", nombre: "Modelos de Aprendizaje" },
]

function Configuracion({ sesion, onCerrarSesion, onIrAResumen, onSeleccionarEquipo }) {
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
            {pestanaActiva === "modelos" && <SeccionModelos />}
          </section>
        </main>
      </div>
    </div>
  )
}

export default Configuracion
