import os

from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv()

MONGO_USUARIO = os.getenv("MONGO_USUARIO")
MONGO_PASSWORD = os.getenv("MONGO_PASSWORD")
MONGO_HOST = os.getenv("MONGO_HOST", "localhost")
MONGO_PUERTO = os.getenv("MONGO_PUERTO", "27017")
MONGO_BASE_DATOS = os.getenv("MONGO_BASE_DATOS", "ia_asistente")

MONGO_URI = (
    f"mongodb://{MONGO_USUARIO}:{MONGO_PASSWORD}"
    f"@{MONGO_HOST}:{MONGO_PUERTO}/?authSource=admin"
)

cliente_mongo = MongoClient(MONGO_URI)
base_datos = cliente_mongo[MONGO_BASE_DATOS]


def verificar_conexion() -> bool:
    cliente_mongo.admin.command("ping")
    return True