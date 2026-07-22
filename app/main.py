from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database import cliente_mongo, verificar_conexion
from app.routers.agente import router as agente_router
from app.routers.conversaciones import router as conversaciones_router
from app.routers.documentos import router as documentos_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    verificar_conexion()
    print("Conexión con MongoDB establecida")

    yield

    cliente_mongo.close()
    print("Conexión con MongoDB cerrada")


app = FastAPI(
    title="Asistente IA",
    description="API de práctica para IA Engineer",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(conversaciones_router)
app.include_router(documentos_router)
app.include_router(agente_router)


@app.get("/")
def inicio():
    return {"mensaje": "Asistente IA funcionando"}


@app.get("/health")
def health():
    verificar_conexion()

    return {
        "estado": "ok",
        "api": "activa",
        "mongodb": "conectado",
    }
