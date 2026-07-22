import { useEffect, useRef, useState } from 'react'
import './App.css'

const API_URL = 'http://127.0.0.1:8000/agente/consultar'
const API_CARGA_URL = 'http://127.0.0.1:8000/documentos/cargar'

function App() {
  const [usuario, setUsuario] = useState('alejandro')
  const [documentoId, setDocumentoId] = useState('')
  const [conversacionId, setConversacionId] = useState(null)
  const [pregunta, setPregunta] = useState('')
  const [mensajes, setMensajes] = useState([])
  const [enviando, setEnviando] = useState(false)
  const [archivoPdf, setArchivoPdf] = useState(null)
  const [subiendoPdf, setSubiendoPdf] = useState(false)
  const [estadoPdf, setEstadoPdf] = useState(null)
  const finChatRef = useRef(null)
  const archivoRef = useRef(null)

  useEffect(() => {
    finChatRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [mensajes, enviando])

  const enviarPregunta = async (event) => {
    event.preventDefault()
    const texto = pregunta.trim()

    if (!texto || !usuario.trim() || enviando) return

    setMensajes((actuales) => [
      ...actuales,
      { rol: 'usuario', texto },
    ])
    setPregunta('')
    setEnviando(true)

    const cuerpo = {
      usuario: usuario.trim(),
      pregunta: texto,
    }

    if (documentoId.trim()) cuerpo.documento_id = documentoId.trim()
    if (conversacionId) cuerpo.conversacion_id = conversacionId

    try {
      const respuesta = await fetch(API_URL, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(cuerpo),
      })

      const datos = await respuesta.json().catch(() => ({}))

      if (!respuesta.ok) {
        throw new Error(datos.detail || 'No se pudo obtener una respuesta')
      }

      setConversacionId(datos.conversacion_id)
      setMensajes((actuales) => [
        ...actuales,
        {
          rol: 'asistente',
          texto: datos.respuesta,
          herramienta: datos.herramienta_utilizada,
          fuente: datos.fuente,
        },
      ])
    } catch (error) {
      setMensajes((actuales) => [
        ...actuales,
        {
          rol: 'error',
          texto: `${error.message}. Verificá que FastAPI esté activo en el puerto 8000.`,
        },
      ])
    } finally {
      setEnviando(false)
    }
  }

  const subirPdf = async () => {
    if (!archivoPdf || subiendoPdf) return

    const formulario = new FormData()
    formulario.append('archivo', archivoPdf)
    setSubiendoPdf(true)
    setEstadoPdf(null)

    try {
      const respuesta = await fetch(API_CARGA_URL, {
        method: 'POST',
        body: formulario,
      })
      const datos = await respuesta.json().catch(() => ({}))

      if (!respuesta.ok) {
        throw new Error(datos.detail || 'No se pudo cargar el PDF')
      }

      const idGenerado = datos.documento_id
      if (!idGenerado) {
        throw new Error('El backend no devolvió el documento_id')
      }

      setDocumentoId(idGenerado)
      setEstadoPdf({ tipo: 'exito', texto: 'PDF cargado. Ya podés hacer preguntas.' })
    } catch (error) {
      setEstadoPdf({ tipo: 'error', texto: error.message })
    } finally {
      setSubiendoPdf(false)
    }
  }

  const nuevaConversacion = () => {
    setConversacionId(null)
    setMensajes([])
    setPregunta('')
  }

  const cambiarArchivo = (event) => {
    const archivo = event.target.files?.[0] || null
    setArchivoPdf(archivo)
    setEstadoPdf(null)
  }

  return (
    <main className="aplicacion">
      <aside className="panel-lateral">
        <div>
          <span className="etiqueta-marca">IA ENGINEER</span>
          <h1>Asistente IA</h1>
          <p className="descripcion">
            Un agente conectado con documentos, memoria y servicios externos.
          </p>
        </div>

        <div className="configuracion">
          <label htmlFor="usuario">Usuario</label>
          <input
            id="usuario"
            value={usuario}
            onChange={(event) => setUsuario(event.target.value)}
            disabled={enviando}
          />

          <label htmlFor="documento">Documento ID <span>(opcional)</span></label>
          <input
            id="documento"
            value={documentoId}
            onChange={(event) => setDocumentoId(event.target.value)}
            placeholder="ID del PDF en ChromaDB"
            disabled={enviando}
          />

          <div className="carga-documento">
            <input
              ref={archivoRef}
              id="archivo-pdf"
              className="input-archivo"
              type="file"
              accept="application/pdf,.pdf"
              onChange={cambiarArchivo}
              disabled={subiendoPdf || enviando}
            />
            <button
              type="button"
              className="selector-archivo"
              onClick={() => archivoRef.current?.click()}
              disabled={subiendoPdf || enviando}
            >
              {archivoPdf ? archivoPdf.name : 'Seleccionar PDF'}
            </button>
            <button
              type="button"
              className="boton-cargar"
              onClick={subirPdf}
              disabled={!archivoPdf || subiendoPdf || enviando}
            >
              {subiendoPdf ? 'Procesando PDF...' : 'Subir documento'}
            </button>
            {estadoPdf && (
              <p className={`estado-pdf ${estadoPdf.tipo}`}>{estadoPdf.texto}</p>
            )}
          </div>
        </div>

        <div className="estado-conversacion">
          <span>Conversación</span>
          <strong>{conversacionId ? 'Activa' : 'Nueva'}</strong>
          {conversacionId && <code title={conversacionId}>{conversacionId}</code>}
        </div>

        <button className="boton-secundario" onClick={nuevaConversacion} disabled={enviando}>
          + Nueva conversación
        </button>
      </aside>

      <section className="chat">
        <header className="cabecera-chat">
          <div>
            <span className="punto-estado" />
            Agente disponible
          </div>
          <span>FastAPI + Ollama</span>
        </header>

        <div className="mensajes" aria-live="polite">
          {mensajes.length === 0 && (
            <div className="bienvenida">
              <div className="icono-bienvenida">✦</div>
              <h2>¿En qué puedo ayudarte?</h2>
              <p>
                Preguntá sobre un documento, una conversación anterior, un país
                o cualquier tema general.
              </p>
            </div>
          )}

          {mensajes.map((mensaje, indice) => (
            <article className={`mensaje ${mensaje.rol}`} key={`${mensaje.rol}-${indice}`}>
              <span className="autor">
                {mensaje.rol === 'usuario' ? 'Vos' : mensaje.rol === 'error' ? 'Error' : 'Asistente'}
              </span>
              <div className="burbuja">{mensaje.texto}</div>
              {mensaje.herramienta && (
                <div className="metadatos">
                  <span>{mensaje.herramienta}</span>
                  {mensaje.fuente && <span>Fuente: {mensaje.fuente}</span>}
                </div>
              )}
            </article>
          ))}

          {enviando && (
            <article className="mensaje asistente">
              <span className="autor">Asistente</span>
              <div className="burbuja escribiendo"><i /><i /><i /></div>
            </article>
          )}
          <div ref={finChatRef} />
        </div>

        <form className="formulario" onSubmit={enviarPregunta}>
          <textarea
            value={pregunta}
            onChange={(event) => setPregunta(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === 'Enter' && !event.shiftKey) {
                event.preventDefault()
                enviarPregunta(event)
              }
            }}
            placeholder="Escribí tu pregunta..."
            rows="1"
            disabled={enviando}
          />
          <button type="submit" disabled={!pregunta.trim() || !usuario.trim() || enviando}>
            Enviar
          </button>
          <small>Enter para enviar · Shift + Enter para una nueva línea</small>
        </form>
      </section>
    </main>
  )
}

export default App
