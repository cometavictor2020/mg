// Interruptor "Redactar con IA" de los reportes (Reportes y Laboratorio). Si el backend informa que la IA no esta
// lista, queda deshabilitado y muestra el motivo.
function InterruptorIA({ estadoIA, activado, onCambio, deshabilitado = false, sujeto = "del equipo y de la planta" }) {
  if (!estadoIA) return null

  const encendido = activado && estadoIA.listo

  return (
    <div className={`interruptor-notificaciones ${encendido ? "" : "interruptor-ia-apagado"}`}>
      <label className="interruptor">
        <input
          type="checkbox"
          role="switch"
          checked={encendido}
          onChange={(e) => onCambio(e.target.checked)}
          disabled={!estadoIA.listo || deshabilitado}
          aria-label="Redactar el reporte con IA"
        />
        <span className="interruptor-pista" aria-hidden="true">
          <span className="interruptor-perilla" />
        </span>
      </label>

      <div>
        <strong>{encendido ? "Redactar con IA: sí" : "Redactar con IA: no"}</strong>
        <p>
          {estadoIA.listo
            ? `Agrega una página «Resumen redactado por IA» al reporte (modelo ${estadoIA.modelo}). Se envían a OpenAI los resultados del diagnóstico, sin las señales${
                estadoIA.enviar_nombres ? "" : ` ni los nombres ${sujeto}`
              }. La IA no cambia el diagnóstico ni las cifras.`
            : `No disponible: ${estadoIA.motivo}`}
        </p>
      </div>
    </div>
  )
}

export default InterruptorIA
