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
    ultimaMedicion: "Hace 12 segundos",

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
    ultimaMedicion: "Hace 25 segundos",

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
    ultimaMedicion: "Hace 18 segundos",

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
    ultimaMedicion: "Hace 31 segundos",

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
    ultimaMedicion: "Hace 42 segundos",

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
    descripcionEstado: "Inactivo",
    ubicacion: "Área de carga",
    ultimaMedicion: "Sin datos recientes",

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
