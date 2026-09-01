const analisisEstandar = [
  {
    id: "tiempo",
    nombre: "Vibración en el tiempo",
  },
  {
    id: "fft",
    nombre: "Espectro FFT",
  },
  {
    id: "curtosis",
    nombre: "Curtosis",
  },
  {
    id: "factor_cresta",
    nombre: "Factor de Cresta",
  },
  {
    id: "skewness",
    nombre: "Skewness",
  },
]

export const equiposDemo = [
  {
    id: "M-001",
    nombre: "Motor Bomba Principal",
    tipo: "Motor eléctrico",
    potenciaKw: 75,
    estado: "critico",
    descripcionEstado: "Estado crítico",
    ubicacion: "Planta principal",
    ubicacionDetalle: "Sala de Máquinas — Nivel 1",
    ultimaMedicion: "Hace 12 segundos",

    vibracionRms: 12.4,
    temperatura: 84,
    velNominal: 1480,
    probabilidadFalla: 87,
    diasFallaEstimada: 6,

    sensores: [
      {
        id: "SEN-001",
        nombre: "Acelerómetro triaxial",
        tipo: "vibracion",
        estado: "activo",
        ejes: ["X", "Y", "Z"],
      },
    ],

    analisisDisponibles: analisisEstandar,
  },

  {
    id: "M-002",
    nombre: "Compresor Aire N°2",
    tipo: "Compresor",
    potenciaKw: 55,
    estado: "advertencia",
    descripcionEstado: "Advertencia",
    ubicacion: "Sala de compresores",
    ubicacionDetalle: "Sala Compresores — Nivel 2",
    ultimaMedicion: "Hace 25 segundos",

    vibracionRms: 5.8,
    temperatura: 71,
    velNominal: 2960,
    probabilidadFalla: 34,
    diasFallaEstimada: 28,

    sensores: [
      {
        id: "SEN-002",
        nombre: "Acelerómetro triaxial",
        tipo: "vibracion",
        estado: "activo",
        ejes: ["X", "Y", "Z"],
      },
    ],

    analisisDisponibles: analisisEstandar,
  },

  {
    id: "M-003",
    nombre: "Motor Ventilador Torre",
    tipo: "Motor eléctrico",
    potenciaKw: 30,
    estado: "normal",
    descripcionEstado: "Normal",
    ubicacion: "Torre de enfriamiento",
    ubicacionDetalle: "Planta Exterior — Sector A",
    ultimaMedicion: "Hace 18 segundos",

    vibracionRms: 2.1,
    temperatura: 62,
    velNominal: 1450,
    probabilidadFalla: 8,
    diasFallaEstimada: null,

    sensores: [
      {
        id: "SEN-003",
        nombre: "Acelerómetro triaxial",
        tipo: "vibracion",
        estado: "activo",
        ejes: ["X", "Y", "Z"],
      },
    ],

    analisisDisponibles: analisisEstandar,
  },

  {
    id: "M-004",
    nombre: "Motor Cinta Transportadora",
    tipo: "Motor eléctrico",
    potenciaKw: 22,
    estado: "normal",
    descripcionEstado: "Normal",
    ubicacion: "Línea de transporte",
    ubicacionDetalle: "Línea de Producción — Sector B",
    ultimaMedicion: "Hace 31 segundos",

    vibracionRms: 1.8,
    temperatura: 58,
    velNominal: 960,
    probabilidadFalla: 5,
    diasFallaEstimada: null,

    sensores: [
      {
        id: "SEN-004",
        nombre: "Acelerómetro triaxial",
        tipo: "vibracion",
        estado: "activo",
        ejes: ["X", "Y", "Z"],
      },
    ],

    analisisDisponibles: analisisEstandar,
  },

  {
    id: "M-005",
    nombre: "Bomba Centrífuga N°1",
    tipo: "Bomba centrífuga",
    potenciaKw: 45,
    estado: "advertencia",
    descripcionEstado: "Advertencia",
    ubicacion: "Sala de bombas",
    ubicacionDetalle: "Sala de Máquinas — Nivel 1",
    ultimaMedicion: "Hace 42 segundos",

    vibracionRms: 6.9,
    temperatura: 76,
    velNominal: 1480,
    probabilidadFalla: 41,
    diasFallaEstimada: 19,

    sensores: [
      {
        id: "SEN-005",
        nombre: "Acelerómetro triaxial",
        tipo: "vibracion",
        estado: "activo",
        ejes: ["X", "Y", "Z"],
      },
    ],

    analisisDisponibles: analisisEstandar,
  },

  {
    id: "M-006",
    nombre: "Motor Grúa Puente",
    tipo: "Motor eléctrico",
    potenciaKw: 15,
    estado: "inactivo",
    descripcionEstado: "Fuera de línea",
    ubicacion: "Área de carga",
    ubicacionDetalle: "Nave Industrial — Altura 8m",
    ultimaMedicion: "Sin datos recientes",

    vibracionRms: null,
    temperatura: null,
    velNominal: 720,
    probabilidadFalla: null,
    diasFallaEstimada: null,

    sensores: [
      {
        id: "SEN-006",
        nombre: "Acelerómetro triaxial",
        tipo: "vibracion",
        estado: "inactivo",
        ejes: ["X", "Y", "Z"],
      },
    ],

    analisisDisponibles: analisisEstandar,
  },
]
