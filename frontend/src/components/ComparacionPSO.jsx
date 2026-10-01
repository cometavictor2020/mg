import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts"

/**
 * Comparación entre el espectro de envolvente tradicional (sin
 * filtrar, el que usa el resto de la aplicación) y el optimizado por
 * PSO (D-046, ver PROYECTO.md) — banda de filtro pasa-banda encontrada
 * por el enjambre para maximizar el pico en la frecuencia objetivo.
 * No reemplaza nada existente: es una vista adicional, solo dentro de
 * Laboratorio y solo cuando el desarrollador la pide explícitamente.
 */
function ComparacionPSO({ resultado, etiquetaFrecuencia }) {
  const { frecuencia_objetivo: frecuenciaObjetivo, tradicional, pso, amplificacion } = resultado

  // Combina ambos espectros en un solo arreglo por frecuencia, para
  // graficarlos superpuestos en los mismos ejes (igual que la Fig. 7
  // del paper: varias curvas sobre el mismo rango de frecuencia).
  const mapaTradicional = new Map(tradicional.espectro.map((p) => [p.frecuencia, p.amplitud]))
  const mapaPso = new Map(pso.espectro.map((p) => [p.frecuencia, p.amplitud]))
  const frecuencias = Array.from(new Set([...mapaTradicional.keys(), ...mapaPso.keys()])).sort((a, b) => a - b)
  const datosComparados = frecuencias.map((frecuencia) => ({
    frecuencia,
    tradicional: mapaTradicional.get(frecuencia) ?? null,
    pso: mapaPso.get(frecuencia) ?? null,
  }))

  return (
    <div className="reporte-grafico-rodamiento">
      <p className="config-mensaje">
        Comparación en {etiquetaFrecuencia ?? "la frecuencia objetivo"} ({frecuenciaObjetivo.toFixed(1)} Hz):
        amplitud tradicional {tradicional.amplitud.toFixed(4)} → amplitud con PSO {pso.amplitud.toFixed(4)}
        {amplificacion !== null && ` (${amplificacion.toFixed(2)}× de amplificación)`}. Banda encontrada por
        PSO: centro {pso.frecuencia_central.toFixed(0)} Hz, ancho {pso.ancho_banda.toFixed(0)} Hz.
      </p>

      <div style={{ width: "100%", height: "300px" }}>
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={datosComparados} margin={{ top: 10, right: 16, bottom: 5, left: 0 }}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis
              dataKey="frecuencia"
              type="number"
              label={{ value: "Frecuencia [Hz]", position: "insideBottom", offset: -5 }}
            />
            <YAxis label={{ value: "Amplitud", angle: -90, position: "insideLeft" }} />
            <Tooltip formatter={(valor) => (valor === null ? "—" : Number(valor).toFixed(4))} />
            <Legend />
            <ReferenceLine x={frecuenciaObjetivo} stroke="#94a3b8" strokeDasharray="4 4" />
            <Line
              type="linear"
              dataKey="pso"
              name="Envolvente optimizada por PSO"
              stroke="#14b8a6"
              dot={false}
              strokeWidth={2.2}
              isAnimationActive={false}
              connectNulls
            />
            <Line
              type="linear"
              dataKey="tradicional"
              name="Envolvente tradicional (sin filtrar)"
              stroke="#f97316"
              dot={false}
              strokeWidth={1.4}
              strokeDasharray="5 3"
              isAnimationActive={false}
              connectNulls
            />
          </LineChart>
        </ResponsiveContainer>
      </div>

      <details className="reporte-limitaciones">
        <summary>Ver tabla comparativa</summary>
        <table className="config-tabla">
          <thead>
            <tr>
              <th>Métrica</th>
              <th>Tradicional (sin filtrar)</th>
              <th>Optimizado por PSO</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td>Frecuencia objetivo</td>
              <td colSpan={2}>{frecuenciaObjetivo.toFixed(4)} Hz</td>
            </tr>
            <tr>
              <td>Amplitud en la frecuencia objetivo</td>
              <td>{tradicional.amplitud.toFixed(6)}</td>
              <td>{pso.amplitud.toFixed(6)}</td>
            </tr>
            <tr>
              <td>Amplificación respecto a lo tradicional</td>
              <td colSpan={2}>{amplificacion !== null ? `${amplificacion.toFixed(2)}×` : "—"}</td>
            </tr>
            <tr>
              <td>Frecuencia central del filtro (Fc)</td>
              <td>—</td>
              <td>{pso.frecuencia_central.toFixed(1)} Hz</td>
            </tr>
            <tr>
              <td>Ancho de banda del filtro (W)</td>
              <td>—</td>
              <td>{pso.ancho_banda.toFixed(1)} Hz</td>
            </tr>
          </tbody>
        </table>
      </details>
    </div>
  )
}

export default ComparacionPSO
