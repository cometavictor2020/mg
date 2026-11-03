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
 * Espectro de envolvente (con BPFO/BPFI/BSF/FTF marcados) +, en un
 * <details> colapsado por defecto, la señal cruda con su envolvente
 * superpuesta (D-042). Compartido entre Reportes.jsx y
 * AnalizadorVibraciones.jsx (D-043) - mismo dato, dos lugares donde
 * verlo: al generar un reporte, o directamente en el detalle del
 * equipo sin tener que generar uno.
 */
function GraficoEnvolvente({ grafico }) {
  return (
    <div className="reporte-grafico-rodamiento">
      <p className="config-mensaje">
        Espectro de envolvente (demodulación de Hilbert) — eje {grafico.eje.toUpperCase()}
      </p>

      <p className="config-mensaje">
        El cursor se acerca al valor exacto pero, con tantos puntos comprimidos en pocos
        píxeles, no siempre puede detenerse justo en el pico — por eso cada frecuencia de
        falla va etiquetada arriba, con su valor exacto, sin depender del cursor.
      </p>

      <div style={{ width: "100%", height: "280px" }}>
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={grafico.espectro_envolvente} margin={{ top: 40, right: 16, bottom: 5, left: 0 }}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis
              dataKey="frecuencia"
              type="number"
              label={{ value: "Frecuencia [Hz]", position: "insideBottom", offset: -5 }}
            />
            <YAxis label={{ value: "Amplitud", angle: -90, position: "insideLeft" }} />
            <Tooltip formatter={(valor) => Number(valor).toFixed(4)} labelFormatter={(valor) => `${valor} Hz`} />
            <Line
              type="linear"
              dataKey="amplitud"
              name="Envolvente"
              stroke="#14b8a6"
              dot={false}
              strokeWidth={1.6}
              isAnimationActive={false}
            />
            {Object.entries(grafico.frecuencias_falla)
              .sort(([, a], [, b]) => a - b)
              .map(([nombre, frecuencia], indice) => (
                <ReferenceLine
                  key={nombre}
                  x={frecuencia}
                  stroke="#94a3b8"
                  strokeDasharray="4 4"
                  label={{
                    value: `${nombre} ${frecuencia.toFixed(1)} Hz`,
                    position: "top",
                    // Alternado en dos alturas: si dos frecuencias quedan
                    // muy juntas (ej. BSF y BPFO), sus etiquetas no se
                    // superponen al estar en filas distintas.
                    offset: indice % 2 === 0 ? 8 : 22,
                    fontSize: 10,
                    fill: "#475569",
                  }}
                />
              ))}
          </LineChart>
        </ResponsiveContainer>
      </div>

      <details className="reporte-limitaciones">
        <summary>
          Ver también señal filtrada + envolvente
          {grafico.banda_demodulacion_hz &&
            ` (banda ${(grafico.banda_demodulacion_hz[0] / 1000).toFixed(1)}–${(grafico.banda_demodulacion_hz[1] / 1000).toFixed(1)} kHz, primeros ${Math.round((grafico.señal_tiempo?.at(-1)?.t ?? 0) * 1000)} ms)`}
        </summary>

        <div style={{ width: "100%", height: "260px", marginTop: "10px" }}>
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={grafico.señal_tiempo}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis
                dataKey="t"
                type="number"
                label={{ value: "Tiempo [s]", position: "insideBottom", offset: -5 }}
              />
              <YAxis label={{ value: "Amplitud", angle: -90, position: "insideLeft" }} />
              <Tooltip />
              <Legend />
              <Line
                type="monotone"
                dataKey="senal"
                name="Señal filtrada"
                stroke="#94a3b8"
                dot={false}
                strokeWidth={1}
                isAnimationActive={false}
              />
              <Line
                type="monotone"
                dataKey="envolvente"
                name="Envolvente (Hilbert)"
                stroke="#ef4444"
                dot={false}
                strokeWidth={1.8}
                isAnimationActive={false}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </details>
    </div>
  )
}

export default GraficoEnvolvente
