from pydantic import BaseModel, Field


# Schema para crear una conversación
class ConversacionCrear(BaseModel):
    usuario: str = Field(min_length=1, max_length=100)
    pregunta: str = Field(min_length=1)
    respuesta: str = Field(min_length=1)


class ConsultaIACrear(BaseModel):
    usuario: str = Field(min_length=1, max_length=100)
    pregunta: str = Field(min_length=1)
    conversacion_id: str | None = None
