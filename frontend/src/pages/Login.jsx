import { useState } from "react"

function Login({ onLoginExitoso }) {
  const [email, setEmail] = useState("")
  const [password, setPassword] = useState("")
  const [error, setError] = useState("")
  const [cargando, setCargando] = useState(false)

  async function manejarSubmit(evento) {
    evento.preventDefault()
    setError("")
    setCargando(true)

    try {
      const respuesta = await fetch("http://127.0.0.1:8000/api/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password }),
      })

      if (!respuesta.ok) {
        throw new Error("Correo electrónico o contraseña incorrectos")
      }

      const datos = await respuesta.json()
      onLoginExitoso(datos)
    } catch (err) {
      setError(err.message)
    } finally {
      setCargando(false)
    }
  }

  return (
    <div className="login-shell">
      <section className="login-panel-izquierdo">
        <div>
          <div className="login-marca">
            <svg
              className="login-logo-icon"
              width="32"
              height="32"
              viewBox="0 0 32 32"
              fill="none"
            >
              <rect width="32" height="32" rx="4" fill="#00c9a7" fillOpacity="0.12" />
              <circle cx="16" cy="16" r="6" stroke="#00c9a7" strokeWidth="1.5" fill="none" />
              <circle cx="16" cy="16" r="2.5" fill="#00c9a7" />
              <path
                d="M16 4v4M16 24v4M4 16h4M24 16h4"
                stroke="#00c9a7"
                strokeWidth="1.5"
                strokeLinecap="round"
              />
              <path
                d="M8.22 8.22l2.83 2.83M20.95 20.95l2.83 2.83M23.78 8.22l-2.83 2.83M11.05 20.95l-2.83 2.83"
                stroke="#00c9a7"
                strokeWidth="1"
                strokeLinecap="round"
                opacity="0.5"
              />
            </svg>
            <span className="login-marca-nombre">MotorGuardian</span>
          </div>

          <div className="login-contenido-izquierdo">
            <p className="login-etiqueta">MANTENIMIENTO PREDICTIVO</p>

            <h1>
              Monitoreo industrial
              <br />
              en tiempo real.
            </h1>

            <p className="login-descripcion">
              Análisis continuo de vibraciones, FFT espectral y predicción de
              fallas mediante IA — para motores eléctricos y maquinaria
              industrial crítica.
            </p>
          </div>
        </div>

        <div className="login-stats">
          <div className="login-stat">
            <span>Sensores activos</span>
            <strong>24</strong>
          </div>

          <div className="login-stat">
            <span>Motores monitoreados</span>
            <strong>8</strong>
          </div>

          <div className="login-stat">
            <span>Alertas resueltas (30d)</span>
            <strong>47</strong>
          </div>
        </div>
      </section>

      <section className="login-panel-derecho">
        <form className="login-formulario" onSubmit={manejarSubmit}>
          <h2>Iniciar sesión</h2>
          <p className="login-subtitulo">
            Accede al panel de control de tu planta
          </p>

          <label className="login-campo">
            <span>CORREO ELECTRÓNICO</span>
            <input
              type="email"
              placeholder="usuario@empresa.cl"
              value={email}
              onChange={(evento) => setEmail(evento.target.value)}
              required
            />
          </label>

          <label className="login-campo">
            <span>CONTRASEÑA</span>
            <input
              type="password"
              placeholder="••••••••"
              value={password}
              onChange={(evento) => setPassword(evento.target.value)}
              required
            />
          </label>

          {error && <p className="login-error">{error}</p>}

          <button type="submit" className="login-boton" disabled={cargando}>
            {cargando ? "Ingresando..." : "Ingresar al sistema"}
          </button>

          <hr className="login-separador" />

          <p className="login-demo">Demo: admin@motorguardian.io / mg2024</p>
        </form>
      </section>
    </div>
  )
}

export default Login
