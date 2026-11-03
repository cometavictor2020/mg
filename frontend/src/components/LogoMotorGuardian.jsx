// Ícono de MotorGuardian (brújula/radar). Compartido por Login y Sidebar para
// que la marca se vea igual en toda la aplicación.
export default function LogoMotorGuardian({ tamano = 32, className = "" }) {
  return (
    <svg
      className={className}
      width={tamano}
      height={tamano}
      viewBox="0 0 32 32"
      fill="none"
      aria-hidden="true"
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
  )
}
