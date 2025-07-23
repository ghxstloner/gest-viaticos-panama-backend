from enum import Enum


class TipoMision(str, Enum):
    VIATICOS = "VIATICOS"
    CAJA_MENUDA = "CAJA_MENUDA"


class TipoFlujo(str, Enum):
    VIATICOS = "VIATICOS"
    CAJA_MENUDA = "CAJA_MENUDA"
    AMBOS = "AMBOS"


class TipoAccion(str, Enum):
    APROBAR = "APROBAR"
    RECHAZAR = "RECHAZAR"
    DEVOLVER = "DEVOLVER"
    SUBSANAR = "SUBSANAR"
    CREAR = "CREAR"
    MODIFICAR = "MODIFICAR"


class TipoDato(str, Enum):
    STRING = "STRING"
    NUMBER = "NUMBER"
    BOOLEAN = "BOOLEAN"
    JSON = "JSON"


class EstadoGestion(str, Enum):
    PENDIENTE = "PENDIENTE"
    EN_PROCESO = "EN_PROCESO"
    COMPLETADA = "COMPLETADA"
    ANULADA = "ANULADA"


class TipoDocumento(str, Enum):
    SOLICITUD = "SOLICITUD"
    COMPROBANTE = "COMPROBANTE"
    FACTURA = "FACTURA"
    OTRO = "OTRO"


class EstadoSubsanacion(str, Enum):
    PENDIENTE = "PENDIENTE"
    COMPLETADA = "COMPLETADA"
    VENCIDA = "VENCIDA"


class TipoTransporte(str, Enum):
    AEREO = "AÉREO"
    ACUATICO = "ACUÁTICO"
    MARITIMO = "MARÍTIMO"
    TERRESTRE = "TERRESTRE"


class CategoriaBeneficiario(str, Enum):
    TITULAR = "TITULAR"
    OTROS_SERVIDORES_PUBLICOS = "OTROS_SERVIDORES_PUBLICOS"
    OTRAS_PERSONAS = "OTRAS_PERSONAS"


class TipoViaje(str, Enum):
    NACIONAL = "NACIONAL"
    INTERNACIONAL = "INTERNACIONAL"


class TipoFirma(str, Enum):
    SOLICITANTE = "SOLICITANTE"
    JEFE = "JEFE"
    DIRECTOR = "DIRECTOR"
    FISCAL = "FISCAL"


class SmtpSecurity(str, Enum):
    NONE = "none"
    TLS = "tls"
    SSL = "ssl"