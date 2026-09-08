"""Excepciones personalizadas del proyecto."""

class ExcepcionBase(Exception):
    """Excepción base con código de error y detalles."""

    def __init__(self, mensaje: str, codigo: str = "ERROR_INTERNO", detalles: dict = None):
        self.mensaje = mensaje
        self.codigo = codigo
        self.detalles = detalles or {}
        super().__init__(mensaje)


class ExcepcionNoEncontrado(ExcepcionBase):
    """Recurso no encontrado (404)."""

    def __init__(self, recurso: str, identificador: str):
        super().__init__(
            mensaje=f"{recurso} '{identificador}' no encontrado",
            codigo="NO_ENCONTRADO",
            detalles={"recurso": recurso, "id": identificador},
        )


class ExcepcionValidacion(ExcepcionBase):
    """Error de validación de datos (422)."""

    def __init__(self, mensaje: str, campo: str = None, valor: any = None):
        super().__init__(
            mensaje=mensaje,
            codigo="VALIDACION_FALLIDA",
            detalles={"campo": campo, "valor": str(valor) if valor else None},
        )


class ExcepcionGrafo(ExcepcionBase):
    """Error en operaciones del grafo."""

    def __init__(self, mensaje: str, operacion: str = None):
        super().__init__(
            mensaje=mensaje,
            codigo="ERROR_GRAFO",
            detalles={"operacion": operacion},
        )


class ExcepcionAgente(ExcepcionBase):
    """Error en operaciones del agente."""

    def __init__(self, mensaje: str, estado: str = None):
        super().__init__(
            mensaje=mensaje,
            codigo="ERROR_AGENTE",
            detalles={"estado": estado},
        )


class ExcepcionBusqueda(ExcepcionBase):
    """Error en algoritmos de búsqueda."""

    def __init__(self, mensaje: str, algoritmo: str = None):
        super().__init__(
            mensaje=mensaje,
            codigo="ERROR_BUSQUEDA",
            detalles={"algoritmo": algoritmo},
        )