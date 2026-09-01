import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
// import './index.css'
// Design System del Analizador de Vibraciones
import "./styles/variables.css"
import './styles/global.css'
import "./styles/layout.css"
import "./styles/tarjetas.css"
import "./styles/pestanas.css"
import "./styles/login.css"
import "./styles/resumen.css"
import App from './App.jsx'

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <App />
  </StrictMode>,
)