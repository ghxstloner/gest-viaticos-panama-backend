from typing import List, Optional
from datetime import date, datetime, timedelta
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from sqlalchemy import text

from ...core.database import get_db_financiero, get_db_rrhh
from ...core.exceptions import BusinessException, ValidationException
from ...api.deps import get_current_employee
from ...models.mission import Mision as MisionModel, EstadoFlujo
from ...schemas.mission import *

# Esquemas específicos para empleados
from pydantic import BaseModel, Field, validator
from ...models.enums import TipoMision

router = APIRouter(
    prefix="/employee/missions",
    tags=["Employee Missions"],
)

class ViaticoCompletoEmployee(BaseModel):
    cantidadDias: int = Field(..., gt=0)
    pagoPorDia: Decimal = Field(..., gt=0)

class ViaticoParcialEmployee(BaseModel):
    fecha: date
    desayuno: str  # 'SI' o 'NO'
    almuerzo: str  # 'SI' o 'NO'
    cena: str      # 'SI' o 'NO'
    hospedaje: str # 'SI' o 'NO'
    observaciones: Optional[str] = None

class TransporteDetalleEmployee(BaseModel):
    fecha: date
    tipo: str  # 'AÉREO', 'ACUÁTICO', 'MARÍTIMO', 'TERRESTRE'
    origen: str = Field(..., min_length=1)
    destino: str = Field(..., min_length=1)
    monto: Decimal = Field(..., gt=0)

class MisionExteriorEmployee(BaseModel):
    destino: str = Field(..., min_length=1)
    region: str = Field(..., min_length=1)
    fechaSalida: date
    fechaRetorno: date
    porcentaje: Decimal = Field(default=Decimal("100"), ge=0, le=100)

class TravelExpensesCreateRequest(BaseModel):
    objetivo: str = Field(..., min_length=10, max_length=1000)
    destino: str = Field(..., min_length=1, max_length=255)
    transporteOficial: str  # 'SI' o 'NO'
    fechaSalida: date
    horaSalida: str = Field(..., pattern=r'^([01]?[0-9]|2[0-3]):[0-5][0-9]$')
    fechaRetorno: date
    horaRetorno: str = Field(..., pattern=r'^([01]?[0-9]|2[0-3]):[0-5][0-9]$')
    categoria: str = Field(..., pattern=r'^(TITULAR|OTROS_SERVIDORES_PUBLICOS|OTRAS_PERSONAS)$')
    viaticosCompletos: List[ViaticoCompletoEmployee] = []
    viaticosParciales: List[ViaticoParcialEmployee] = []
    transporteDetalle: List[TransporteDetalleEmployee] = []
    misionesExterior: List[MisionExteriorEmployee] = []

    @validator('fechaRetorno')
    def validate_return_date(cls, v, values):
        if 'fechaSalida' in values and v < values['fechaSalida']:
            raise ValueError('La fecha de retorno debe ser igual o posterior a la fecha de salida')
        return v

class CajaMenudaViaticoEmployee(BaseModel):
    fecha: date
    horaDe: str = Field(..., pattern=r'^([01]?[0-9]|2[0-3]):[0-5][0-9]$')
    horaHasta: str = Field(..., pattern=r'^([01]?[0-9]|2[0-3]):[0-5][0-9]$')
    desayuno: Decimal = Field(default=Decimal("0"), ge=0)
    almuerzo: Decimal = Field(default=Decimal("0"), ge=0)
    cena: Decimal = Field(default=Decimal("0"), ge=0)
    transporte: Decimal = Field(default=Decimal("0"), ge=0)

    @validator('horaHasta')
    def validate_time_range(cls, v, values):
        if 'horaDe' in values:
            from datetime import datetime
            hora_de = datetime.strptime(values['horaDe'], '%H:%M')
            hora_hasta = datetime.strptime(v, '%H:%M')
            if hora_hasta <= hora_de:
                raise ValueError('La hora hasta debe ser mayor que la hora desde')
        return v

class PettyCashCreateRequest(BaseModel):
    trabajo_a_realizar: str = Field(..., min_length=10, max_length=500)
    para: str = Field(..., min_length=1)  # departamento
    vicepresidencia: str = Field(..., min_length=1)
    viaticosCompletos: List[CajaMenudaViaticoEmployee] = Field(..., min_items=1)

# Funciones auxiliares
def get_employee_personal_id(cedula: str, db_rrhh: Session) -> int:
    """Obtiene el personal_id del empleado desde RRHH"""
    result = db_rrhh.execute(text("""
        SELECT personal_id FROM aitsa_rrhh.nompersonal 
        WHERE cedula = :cedula AND estado != 'De Baja'
    """), {"cedula": cedula})
    
    employee_record = result.fetchone()
    if not employee_record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Empleado no encontrado en RRHH"
        )
    
    return employee_record.personal_id

def get_usuario_for_employee(personal_id: int, db_financiero: Session) -> int:
    """
    Obtiene el id_usuario asociado al empleado, o retorna un usuario especial para empleados
    """
    from ...models.user import Usuario
    
    # Buscar usuario existente asociado al empleado
    usuario = db_financiero.query(Usuario).filter(
        Usuario.personal_id_rrhh == personal_id,
        Usuario.is_active == True
    ).first()
    
    if usuario:
        return usuario.id_usuario
    
    # Si no existe, buscar un usuario especial para empleados (ej: "SISTEMA_EMPLEADOS")
    usuario_sistema = db_financiero.query(Usuario).filter(
        Usuario.login_username == "SISTEMA_EMPLEADOS",
        Usuario.is_active == True
    ).first()
    
    if usuario_sistema:
        return usuario_sistema.id_usuario
        
    # Como última opción, usar el primer usuario activo (temporal)
    usuario_fallback = db_financiero.query(Usuario).filter(
        Usuario.is_active == True
    ).first()
    
    if usuario_fallback:
        return usuario_fallback.id_usuario
        
    # Si no hay usuarios, lanzar error
    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="No se pudo determinar usuario para auditoría"
    )

def get_department_description(codigo_nivel2: str, db_rrhh: Session) -> str:
    """Obtiene la descripción del departamento"""
    result = db_rrhh.execute(text("""
        SELECT descrip FROM aitsa_rrhh.nomnivel2 WHERE codorg = :codigo
    """), {"codigo": codigo_nivel2})
    
    dept_record = result.fetchone()
    return dept_record.descrip if dept_record else codigo_nivel2

def get_system_config_value(clave: str, db: Session, default_value: str = "0") -> str:
    """Obtiene un valor de configuración del sistema"""
    result = db.execute(text("""
        SELECT valor FROM aitsa_financiero.configuraciones_sistema 
        WHERE clave = :clave
    """), {"clave": clave})
    
    config_record = result.fetchone()
    return config_record.valor if config_record else default_value

def generate_request_number(db: Session) -> str:
    """Genera el número de solicitud secuencial usando configuraciones_sistema"""
    try:
        # Obtener prefijo y consecutivo actual
        prefijo = get_system_config_value("PREFIJO_NUMERO_SOLICITUD", db, "SOL-")
        consecutivo_actual = int(get_system_config_value("CONSECUTIVO_SOLICITUD", db, "1"))
        
        # Generar número con formato de 6 dígitos
        numero_solicitud = f"{prefijo}{consecutivo_actual:06d}"
        
        # Incrementar consecutivo para la próxima solicitud
        nuevo_consecutivo = consecutivo_actual + 1
        db.execute(text("""
            UPDATE aitsa_financiero.configuraciones_sistema 
            SET valor = :nuevo_valor 
            WHERE clave = 'CONSECUTIVO_SOLICITUD'
        """), {"nuevo_valor": str(nuevo_consecutivo)})
        
        return numero_solicitud
        
    except Exception as e:
        print(f"Error generando número de solicitud: {e}")
        # Fallback en caso de error
        import time
        import random
        return f"SOL-{int(time.time())}-{random.randint(1000, 9999)}"

def get_client_ip(request: Request) -> str:
    """Obtiene la IP real del cliente"""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    
    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip
    
    return request.client.host if request.client else "127.0.0.1"

def convert_si_no_to_amount(valor: str, categoria: str, concepto: str) -> Decimal:
    """Convierte SI/NO a montos según tarifas configuradas"""
    if valor.upper() != 'SI':
        return Decimal("0.00")
    
    # Tarifas base (deberían venir de configuración)
    tarifas = {
        'TITULAR': {
            'DESAYUNO': Decimal("15.6"),
            'ALMUERZO': Decimal("31.2"),
            'CENA': Decimal("31.2"),
            'HOSPEDAJE': Decimal("80.0")
        },
        'OTROS SERVIDORES PÚBLICOS': {
            'DESAYUNO': Decimal("13.0"),
            'ALMUERZO': Decimal("26.0"),
            'CENA': Decimal("26.0"),
            'HOSPEDAJE': Decimal("65.0")
        },
        'OTRAS PERSONAS': {
            'DESAYUNO': Decimal("10.0"),
            'ALMUERZO': Decimal("20.0"),
            'CENA': Decimal("20.0"),
            'HOSPEDAJE': Decimal("50.0")
        }
    }
    
    return tarifas.get(categoria, {}).get(concepto.upper(), Decimal("0.00"))

# Endpoints
@router.post("/travel-expenses", summary="Crear solicitud de viáticos (Empleado)")
async def create_travel_expenses(
    request: TravelExpensesCreateRequest,
    http_request: Request,
    db_financiero: Session = Depends(get_db_financiero),
    db_rrhh: Session = Depends(get_db_rrhh),
    current_employee: dict = Depends(get_current_employee)
):
    """
    Crea una nueva solicitud de viáticos desde el portal de empleados.
    Replica la funcionalidad del sistema PHP original.
    """
    try:
        # Obtener personal_id del empleado
        cedula = current_employee.get("cedula")
        personal_id = get_employee_personal_id(cedula, db_rrhh)
        
        # Obtener id_usuario para auditoría
        id_usuario = get_usuario_for_employee(personal_id, db_financiero)
        
        # Generar número de solicitud
        numero_solicitud = generate_request_number(db_financiero)
        
        # Obtener días límite para presentación desde configuración
        dias_limite = int(get_system_config_value("DIAS_LIMITE_PRESENTACION", db_financiero, "10"))
        
        # Determinar tipo de viaje
        tipo_viaje = 'INTERNACIONAL' if request.misionesExterior else 'NACIONAL'
        region_exterior = request.misionesExterior[0].region if request.misionesExterior else None
        
        # Combinar fecha y hora
        fecha_salida = datetime.combine(request.fechaSalida, 
                                        datetime.strptime(request.horaSalida, '%H:%M').time())
        fecha_retorno = datetime.combine(request.fechaRetorno,
                                          datetime.strptime(request.horaRetorno, '%H:%M').time())
        
        # Calcular fecha límite de presentación
        fecha_limite_presentacion = request.fechaSalida + timedelta(days=dias_limite)
        
        # Crear misión principal
        mision = MisionModel(
            numero_solicitud=numero_solicitud,
            tipo_mision=TipoMision.VIATICOS,
            beneficiario_personal_id=personal_id,
            categoria_beneficiario=request.categoria,
            objetivo_mision=request.objetivo,
            destino_mision=request.destino,
            tipo_viaje=tipo_viaje,
            region_exterior=region_exterior,
            fecha_salida=fecha_salida,
            fecha_retorno=fecha_retorno,
            fecha_limite_presentacion=fecha_limite_presentacion,
            transporte_oficial=request.transporteOficial == 'SI',
            monto_total_calculado=Decimal("0.00"),
            requiere_refrendo_cgr=False,
            id_estado_flujo=11  # PENDIENTE_JEFE
        )
        
        db_financiero.add(mision)
        db_financiero.flush()  # Para obtener el ID
        
        # Insertar viáticos completos
        for vc in request.viaticosCompletos:
            db_financiero.execute(text("""
                INSERT INTO items_viaticos_completos 
                (id_mision, cantidad_dias, monto_por_dia) 
                VALUES (:id_mision, :cantidad_dias, :monto_por_dia)
            """), {
                "id_mision": mision.id_mision,
                "cantidad_dias": vc.cantidadDias,
                "monto_por_dia": vc.pagoPorDia
            })
        
        # Insertar viáticos parciales
        for vp in request.viaticosParciales:
            monto_desayuno = convert_si_no_to_amount(vp.desayuno, request.categoria, 'DESAYUNO')
            monto_almuerzo = convert_si_no_to_amount(vp.almuerzo, request.categoria, 'ALMUERZO')
            monto_cena = convert_si_no_to_amount(vp.cena, request.categoria, 'CENA')
            monto_hospedaje = convert_si_no_to_amount(vp.hospedaje, request.categoria, 'HOSPEDAJE')
            
            db_financiero.execute(text("""
                INSERT INTO items_viaticos 
                (id_mision, fecha, monto_desayuno, monto_almuerzo, monto_cena, monto_hospedaje, observaciones) 
                VALUES (:id_mision, :fecha, :monto_desayuno, :monto_almuerzo, :monto_cena, :monto_hospedaje, :observaciones)
            """), {
                "id_mision": mision.id_mision,
                "fecha": vp.fecha,
                "monto_desayuno": monto_desayuno,
                "monto_almuerzo": monto_almuerzo,
                "monto_cena": monto_cena,
                "monto_hospedaje": monto_hospedaje,
                "observaciones": vp.observaciones
            })
        
        # Insertar detalle de transporte
        for td in request.transporteDetalle:
            db_financiero.execute(text("""
                INSERT INTO items_transporte 
                (id_mision, fecha, tipo, origen, destino, monto) 
                VALUES (:id_mision, :fecha, :tipo, :origen, :destino, :monto)
            """), {
                "id_mision": mision.id_mision,
                "fecha": td.fecha,
                "tipo": td.tipo,
                "origen": td.origen,
                "destino": td.destino,
                "monto": td.monto
            })
        
        # Insertar misiones al exterior
        for me in request.misionesExterior:
            db_financiero.execute(text("""
                INSERT INTO items_misiones_exterior 
                (id_mision, region, destino, fecha_salida, fecha_retorno, porcentaje) 
                VALUES (:id_mision, :region, :destino, :fecha_salida, :fecha_retorno, :porcentaje)
            """), {
                "id_mision": mision.id_mision,
                "region": me.region,
                "destino": me.destino,
                "fecha_salida": me.fechaSalida,
                "fecha_retorno": me.fechaRetorno,
                "porcentaje": me.porcentaje
            })
        
        # Calcular monto total
        total_result = db_financiero.execute(text("""
            SELECT 
                COALESCE(SUM(vc.cantidad_dias * vc.monto_por_dia), 0) +
                COALESCE(SUM(vp.monto_desayuno + vp.monto_almuerzo + vp.monto_cena + vp.monto_hospedaje), 0) +
                COALESCE(SUM(t.monto), 0) as total
            FROM misiones m
            LEFT JOIN items_viaticos_completos vc ON m.id_mision = vc.id_mision
            LEFT JOIN items_viaticos vp ON m.id_mision = vp.id_mision
            LEFT JOIN items_transporte t ON m.id_mision = t.id_mision
            WHERE m.id_mision = :id_mision
        """), {"id_mision": mision.id_mision})
        
        monto_total = total_result.fetchone().total or Decimal("0.00")
        
        # Actualizar monto total
        mision.monto_total_calculado = monto_total
        mision.requiere_refrendo_cgr = monto_total >= Decimal("1000.00")
        
        # Obtener IP real del usuario
        client_ip = get_client_ip(http_request)
        
        # Registrar en historial
        db_financiero.execute(text("""
            INSERT INTO historial_flujo 
            (id_mision, id_usuario_accion, id_estado_nuevo, tipo_accion, comentarios, ip_usuario) 
            VALUES (:id_mision, :id_usuario, :estado, :accion, :comentario, :ip)
        """), {
            "id_mision": mision.id_mision,
            "id_usuario": id_usuario,
            "estado": 11,
            "accion": "CREAR",
            "comentario": f"Solicitud de viáticos creada desde portal de empleados por {cedula}",
            "ip": client_ip
        })
        
        db_financiero.commit()
        
        return {
            "success": True,
            "message": "Solicitud de viáticos creada exitosamente",
            "data": {
                "id_mision": mision.id_mision,
                "numero_solicitud": numero_solicitud,
                "monto_total": float(monto_total),
                "fecha_limite_presentacion": fecha_limite_presentacion.strftime('%Y-%m-%d')
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        db_financiero.rollback()
        print(f"Error creando solicitud de viáticos: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error interno del servidor"
        )

@router.post("/petty-cash", summary="Crear solicitud de caja menuda (Empleado)")
async def create_petty_cash(
    request: PettyCashCreateRequest,
    http_request: Request,
    db_financiero: Session = Depends(get_db_financiero),
    db_rrhh: Session = Depends(get_db_rrhh),
    current_employee: dict = Depends(get_current_employee)
):
    """
    Crea una nueva solicitud de caja menuda desde el portal de empleados.
    Replica la funcionalidad del sistema PHP original.
    """
    try:
        # Obtener límite diario desde configuración
        limite_diario = Decimal(get_system_config_value("LIMITE_EFECTIVO_VIATICOS", db_financiero, "200"))
        
        # Validar límite diario
        for viatico in request.viaticosCompletos:
            total_dia = viatico.desayuno + viatico.almuerzo + viatico.cena + viatico.transporte
            if total_dia > limite_diario:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Un viático excede el límite diario de B/. {limite_diario}"
                )
            if total_dia <= 0:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Debe ingresar al menos un monto mayor a 0 por día"
                )
        
        # Obtener personal_id del empleado
        cedula = current_employee.get("cedula")
        personal_id = get_employee_personal_id(cedula, db_rrhh)
        
        # Obtener id_usuario para auditoría
        id_usuario = get_usuario_for_employee(personal_id, db_financiero)
        
        # Obtener descripción del departamento
        destino_descripcion = get_department_description(request.para, db_rrhh)
        
        # Generar número de solicitud
        numero_solicitud = generate_request_number(db_financiero)
        
        # Obtener días límite para presentación desde configuración
        dias_limite = int(get_system_config_value("DIAS_LIMITE_PRESENTACION", db_financiero, "10"))
        
        # Para caja menuda, la fecha de salida es la fecha actual
        fecha_actual = datetime.now().date()
        fecha_limite_presentacion = fecha_actual + timedelta(days=dias_limite)
        
        # Crear misión principal
        mision = MisionModel(
            numero_solicitud=numero_solicitud,
            destino_codnivel2=int(request.para),
            tipo_mision=TipoMision.CAJA_MENUDA,
            beneficiario_personal_id=personal_id,
            categoria_beneficiario='TITULAR',  # Siempre TITULAR para caja menuda
            objetivo_mision=request.trabajo_a_realizar,
            destino_mision=destino_descripcion,
            tipo_viaje='NACIONAL',  # Siempre nacional para caja menuda
            fecha_salida=datetime.now(),  # Fecha actual
            fecha_retorno=datetime.now(),  # Fecha actual
            fecha_limite_presentacion=fecha_limite_presentacion,
            transporte_oficial=False,  # Siempre False para caja menuda
            monto_total_calculado=Decimal("0.00"),
            requiere_refrendo_cgr=False,
            id_estado_flujo=11  # PENDIENTE_JEFE
        )
        
        db_financiero.add(mision)
        db_financiero.flush()
        
        # Insertar viáticos de caja menuda
        monto_total = Decimal("0.00")
        for viatico in request.viaticosCompletos:
            db_financiero.execute(text("""
                INSERT INTO misiones_caja_menuda 
                (id_mision, fecha, hora_de, hora_hasta, desayuno, almuerzo, cena, transporte) 
                VALUES (:id_mision, :fecha, :hora_de, :hora_hasta, :desayuno, :almuerzo, :cena, :transporte)
            """), {
                "id_mision": mision.id_mision,
                "fecha": viatico.fecha,
                "hora_de": viatico.horaDe,
                "hora_hasta": viatico.horaHasta,
                "desayuno": viatico.desayuno,
                "almuerzo": viatico.almuerzo,
                "cena": viatico.cena,
                "transporte": viatico.transporte
            })
            
            monto_total += viatico.desayuno + viatico.almuerzo + viatico.cena + viatico.transporte
        
        # Actualizar monto total
        mision.monto_total_calculado = monto_total
        
        # Obtener IP real del usuario
        client_ip = get_client_ip(http_request)
        
        # Registrar en historial
        db_financiero.execute(text("""
            INSERT INTO historial_flujo 
            (id_mision, id_usuario_accion, id_estado_nuevo, tipo_accion, comentarios, ip_usuario) 
            VALUES (:id_mision, :id_usuario, :estado, :accion, :comentario, :ip)
        """), {
            "id_mision": mision.id_mision,
            "id_usuario": id_usuario,
            "estado": 11,
            "accion": "CREAR",
            "comentario": f"Solicitud de caja menuda creada desde portal de empleados por {cedula}",
            "ip": client_ip
        })
        
        db_financiero.commit()
        
        return {
            "success": True,
            "message": "Solicitud de caja menuda creada exitosamente",
            "data": {
                "id_mision": mision.id_mision,
                "numero_solicitud": numero_solicitud,
                "monto_total": float(monto_total),
                "fecha_limite_presentacion": fecha_limite_presentacion.strftime('%Y-%m-%d')
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        db_financiero.rollback()
        print(f"Error creando solicitud de caja menuda: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error interno del servidor"
        )

@router.get("/tarifas", summary="Obtener tarifas del sistema")
async def get_tarifas(db_financiero: Session = Depends(get_db_financiero)):
    """
    Obtiene las tarifas configuradas en el sistema desde la tabla configuraciones_sistema.
    """
    try:
        # Obtener todas las configuraciones relevantes
        result = db_financiero.execute(text("""
            SELECT clave, valor, tipo_dato 
            FROM configuraciones_sistema 
            WHERE clave LIKE 'TARIFA_%' 
              OR clave LIKE 'PORCENTAJE_%'
              OR clave LIKE 'INCREMENTO_%'
        """))
        
        configs = {row.clave: float(row.valor) if row.tipo_dato == 'NUMBER' else row.valor 
                   for row in result.fetchall()}
        
        # Calcular tarifas por comida basadas en porcentajes
        def calcular_tarifas_comidas(tarifa_base):
            return {
                "DESAYUNO": round(tarifa_base * (configs.get('PORCENTAJE_DESAYUNO', 20) / 100), 2),
                "ALMUERZO": round(tarifa_base * (configs.get('PORCENTAJE_ALMUERZO', 40) / 100), 2),
                "CENA": round(tarifa_base * (configs.get('PORCENTAJE_CENA', 40) / 100), 2)
            }
        
        # Construir estructura de tarifas
        tarifas = {
            "tarifas_nacionales": {
                "TITULAR": {
                    **calcular_tarifas_comidas(configs.get('TARIFA_VIATICO_TITULAR_NACIONAL', 78.00)),
                    "HOSPEDAJE": configs.get('TARIFA_HOSPEDAJE_TITULAR_NACIONAL', 80.00)
                },
                "OTROS SERVIDORES PÚBLICOS": {
                    **calcular_tarifas_comidas(configs.get('TARIFA_VIATICO_OTROS_SERVIDORES_NACIONAL', 65.00)),
                    "HOSPEDAJE": configs.get('TARIFA_HOSPEDAJE_OTROS_SERVIDORES_NACIONAL', 65.00)
                },
                "OTRAS PERSONAS": {
                    **calcular_tarifas_comidas(configs.get('TARIFA_VIATICO_OTRAS_PERSONAS_NACIONAL', 50.00)),
                    "HOSPEDAJE": configs.get('TARIFA_HOSPEDAJE_OTRAS_PERSONAS_NACIONAL', 50.00)
                }
            },
            "tarifas_exterior": {
                "TITULAR": {
                    "Europa": round(configs.get('TARIFA_VIATICO_TITULAR_NACIONAL', 78.00) * (1 + configs.get('INCREMENTO_EUROPA', 75) / 100), 2),
                    "Asia": round(configs.get('TARIFA_VIATICO_TITULAR_NACIONAL', 78.00) * (1 + configs.get('INCREMENTO_ASIA', 80) / 100), 2),
                    "Centroamérica": round(configs.get('TARIFA_VIATICO_TITULAR_NACIONAL', 78.00) * (1 + configs.get('INCREMENTO_CENTROAMERICA', 25) / 100), 2),
                    "Estados Unidos": round(configs.get('TARIFA_VIATICO_TITULAR_NACIONAL', 78.00) * (1 + configs.get('INCREMENTO_NORTEAMERICA', 50) / 100), 2),
                    "Resto de América Latina": round(configs.get('TARIFA_VIATICO_TITULAR_NACIONAL', 78.00) * (1 + configs.get('INCREMENTO_SUDAMERICA', 35) / 100), 2),
                    "Otros": round(configs.get('TARIFA_VIATICO_TITULAR_NACIONAL', 78.00) * (1 + configs.get('INCREMENTO_OTROS', 40) / 100), 2)
                },
                "OTROS SERVIDORES PÚBLICOS": {
                    "Europa": round(configs.get('TARIFA_VIATICO_OTROS_SERVIDORES_NACIONAL', 65.00) * (1 + configs.get('INCREMENTO_EUROPA', 75) / 100), 2),
                    "Asia": round(configs.get('TARIFA_VIATICO_OTROS_SERVIDORES_NACIONAL', 65.00) * (1 + configs.get('INCREMENTO_ASIA', 80) / 100), 2),
                    "Centroamérica": round(configs.get('TARIFA_VIATICO_OTROS_SERVIDORES_NACIONAL', 65.00) * (1 + configs.get('INCREMENTO_CENTROAMERICA', 25) / 100), 2),
                    "Estados Unidos": round(configs.get('TARIFA_VIATICO_OTROS_SERVIDORES_NACIONAL', 65.00) * (1 + configs.get('INCREMENTO_NORTEAMERICA', 50) / 100), 2),
                    "Resto de América Latina": round(configs.get('TARIFA_VIATICO_OTROS_SERVIDORES_NACIONAL', 65.00) * (1 + configs.get('INCREMENTO_SUDAMERICA', 35) / 100), 2),
                    "Otros": round(configs.get('TARIFA_VIATICO_OTROS_SERVIDORES_NACIONAL', 65.00) * (1 + configs.get('INCREMENTO_OTROS', 40) / 100), 2)
                },
                "OTRAS PERSONAS": {
                    "Europa": round(configs.get('TARIFA_VIATICO_OTRAS_PERSONAS_NACIONAL', 50.00) * (1 + configs.get('INCREMENTO_EUROPA', 75) / 100), 2),
                    "Asia": round(configs.get('TARIFA_VIATICO_OTRAS_PERSONAS_NACIONAL', 50.00) * (1 + configs.get('INCREMENTO_ASIA', 80) / 100), 2),
                    "Centroamérica": round(configs.get('TARIFA_VIATICO_OTRAS_PERSONAS_NACIONAL', 50.00) * (1 + configs.get('INCREMENTO_CENTROAMERICA', 25) / 100), 2),
                    "Estados Unidos": round(configs.get('TARIFA_VIATICO_OTRAS_PERSONAS_NACIONAL', 50.00) * (1 + configs.get('INCREMENTO_NORTEAMERICA', 50) / 100), 2),
                    "Resto de América Latina": round(configs.get('TARIFA_VIATICO_OTRAS_PERSONAS_NACIONAL', 50.00) * (1 + configs.get('INCREMENTO_SUDAMERICA', 35) / 100), 2),
                    "Otros": round(configs.get('TARIFA_VIATICO_OTRAS_PERSONAS_NACIONAL', 50.00) * (1 + configs.get('INCREMENTO_OTROS', 40) / 100), 2)
                }
            },
            "configuracion": {
                "hora_corte_desayuno": configs.get('HORA_CORTE_DESAYUNO', '08:00'),
                "hora_corte_almuerzo": configs.get('HORA_CORTE_ALMUERZO', '14:00'),
                "hora_corte_cena": configs.get('HORA_CORTE_CENA', '20:00'),
                "tarifa_transporte_terrestre_km": configs.get('TARIFA_TRANSPORTE_TERRESTRE_KM', 0.50),
                "tarifa_transporte_aereo_nacional": configs.get('TARIFA_TRANSPORTE_AEREO_NACIONAL', 150.00),
                "tarifa_transporte_acuatico_base": configs.get('TARIFA_TRANSPORTE_ACUATICO_BASE', 75.00)
            }
        }
        
        return {
            "success": True,
            "data": tarifas
        }
        
    except Exception as e:
        print(f"Error obteniendo tarifas: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error obteniendo tarifas del sistema"
        )

@router.get("/limits", summary="Obtener límites del sistema")
async def get_limits(db_financiero: Session = Depends(get_db_financiero)):
    """
    Obtiene los límites configurados para caja menuda.
    """
    try:
        limite_efectivo = float(get_system_config_value("LIMITE_EFECTIVO_VIATICOS", db_financiero, "200"))
        dias_limite = int(get_system_config_value("DIAS_LIMITE_PRESENTACION", db_financiero, "10"))
        
        return {
            "success": True,
            "data": {
                "limite_efectivo_diario": limite_efectivo,
                "dias_limite_presentacion": dias_limite
            }
        }
    except Exception as e:
        print(f"Error obteniendo límites: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error obteniendo límites del sistema"
        )

@router.get("/organizational-structure", summary="Obtener estructura organizacional")
async def get_organizational_structure(db_rrhh: Session = Depends(get_db_rrhh)):
    """
    Obtiene la estructura organizacional (nivel1 y nivel2) desde RRHH.
    """
    try:
        # Obtener nivel 1 (vicepresidencias)
        nivel1_result = db_rrhh.execute(text("""
            SELECT codorg, descrip 
            FROM aitsa_rrhh.nomnivel1 
            ORDER BY descrip
        """))
        
        nivel1 = [{"codorg": row.codorg, "descrip": row.descrip} for row in nivel1_result.fetchall()]
        
        # Obtener nivel 2 (departamentos)
        nivel2_result = db_rrhh.execute(text("""
            SELECT codorg, descrip, gerencia 
            FROM aitsa_rrhh.nomnivel2 
            ORDER BY descrip
        """))
        
        nivel2 = [{"codorg": row.codorg, "descrip": row.descrip, "gerencia": row.gerencia} for row in nivel2_result.fetchall()]
        
        return {
            "success": True,
            "data": {
                "nivel1": nivel1,
                "nivel2": nivel2
            }
        }
        
    except Exception as e:
        print(f"Error obteniendo estructura organizacional: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error obteniendo estructura organizacional"
        )
@router.put("/travel-expenses/{mission_id}", summary="Actualizar solicitud de viáticos")
async def update_travel_expenses(
    mission_id: int,
    request: TravelExpensesUpdateRequest,
    http_request: Request,
    db_financiero: Session = Depends(get_db_financiero),
    db_rrhh: Session = Depends(get_db_rrhh),
    current_employee: dict = Depends(get_current_employee)
):
    """
    Actualiza una solicitud de viáticos existente.
    Solo permitido en estados: BORRADOR, DEVUELTO_CORRECCION
    """
    try:
        # Obtener personal_id del empleado
        cedula = current_employee.get("cedula")
        personal_id = get_employee_personal_id(cedula, db_rrhh)
        
        # Verificar que la misión existe y pertenece al empleado
        mision = db_financiero.query(MisionModel).filter(
            MisionModel.id_mision == mission_id,
            MisionModel.beneficiario_personal_id == personal_id,
            MisionModel.tipo_mision == TipoMision.VIATICOS
        ).first()
        
        if not mision:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Solicitud de viáticos no encontrada"
            )
        
        # Verificar que está en estado editable
        estados_editables = [11, 8]  # PENDIENTE_JEFE, DEVUELTO_CORRECCION
        if mision.id_estado_flujo not in estados_editables:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Solo se pueden editar solicitudes en estado PENDIENTE_JEFE o DEVUELTO_CORRECCION"
            )
        
        # Actualizar campos básicos si se proporcionan
        if request.objetivo is not None:
            mision.objetivo_mision = request.objetivo
        if request.destino is not None:
            mision.destino_mision = request.destino
        if request.transporteOficial is not None:
            mision.transporte_oficial = request.transporteOficial == 'SI'
        if request.categoria is not None:
            mision.categoria_beneficiario = request.categoria
        
        # Actualizar fechas si se proporcionan
        if request.fechaSalida and request.horaSalida:
            mision.fecha_salida = datetime.combine(
                request.fechaSalida, 
                datetime.strptime(request.horaSalida, '%H:%M').time()
            )
        
        if request.fechaRetorno and request.horaRetorno:
            mision.fecha_retorno = datetime.combine(
                request.fechaRetorno,
                datetime.strptime(request.horaRetorno, '%H:%M').time()
            )
        
        # Actualizar viáticos completos si se proporcionan
        if request.viaticosCompletos is not None:
            # Eliminar existentes
            db_financiero.execute(text("""
                DELETE FROM items_viaticos_completos WHERE id_mision = :id_mision
            """), {"id_mision": mission_id})
            
            # Insertar nuevos
            for vc in request.viaticosCompletos:
                db_financiero.execute(text("""
                    INSERT INTO items_viaticos_completos 
                    (id_mision, cantidad_dias, monto_por_dia) 
                    VALUES (:id_mision, :cantidad_dias, :monto_por_dia)
                """), {
                    "id_mision": mission_id,
                    "cantidad_dias": vc.cantidadDias,
                    "monto_por_dia": vc.pagoPorDia
                })
        
        # Actualizar viáticos parciales si se proporcionan
        if request.viaticosParciales is not None:
            # Eliminar existentes
            db_financiero.execute(text("""
                DELETE FROM items_viaticos WHERE id_mision = :id_mision
            """), {"id_mision": mission_id})
            
            # Insertar nuevos
            for vp in request.viaticosParciales:
                monto_desayuno = convert_si_no_to_amount(vp.desayuno, mision.categoria_beneficiario, 'DESAYUNO')
                monto_almuerzo = convert_si_no_to_amount(vp.almuerzo, mision.categoria_beneficiario, 'ALMUERZO')
                monto_cena = convert_si_no_to_amount(vp.cena, mision.categoria_beneficiario, 'CENA')
                monto_hospedaje = convert_si_no_to_amount(vp.hospedaje, mision.categoria_beneficiario, 'HOSPEDAJE')
                
                db_financiero.execute(text("""
                    INSERT INTO items_viaticos 
                    (id_mision, fecha, monto_desayuno, monto_almuerzo, monto_cena, monto_hospedaje, observaciones) 
                    VALUES (:id_mision, :fecha, :monto_desayuno, :monto_almuerzo, :monto_cena, :monto_hospedaje, :observaciones)
                """), {
                    "id_mision": mission_id,
                    "fecha": vp.fecha,
                    "monto_desayuno": monto_desayuno,
                    "monto_almuerzo": monto_almuerzo,
                    "monto_cena": monto_cena,
                    "monto_hospedaje": monto_hospedaje,
                    "observaciones": vp.observaciones
                })
        
        # Actualizar transporte si se proporciona
        if request.transporteDetalle is not None:
            # Eliminar existentes
            db_financiero.execute(text("""
                DELETE FROM items_transporte WHERE id_mision = :id_mision
            """), {"id_mision": mission_id})
            
            # Insertar nuevos
            for td in request.transporteDetalle:
                db_financiero.execute(text("""
                    INSERT INTO items_transporte 
                    (id_mision, fecha, tipo, origen, destino, monto) 
                    VALUES (:id_mision, :fecha, :tipo, :origen, :destino, :monto)
                """), {
                    "id_mision": mission_id,
                    "fecha": td.fecha,
                    "tipo": td.tipo,
                    "origen": td.origen,
                    "destino": td.destino,
                    "monto": td.monto
                })
        
        # Actualizar misiones al exterior si se proporciona
        if request.misionesExterior is not None:
            # Eliminar existentes
            db_financiero.execute(text("""
                DELETE FROM items_misiones_exterior WHERE id_mision = :id_mision
            """), {"id_mision": mission_id})
            
            # Insertar nuevos
            for me in request.misionesExterior:
                db_financiero.execute(text("""
                    INSERT INTO items_misiones_exterior 
                    (id_mision, region, destino, fecha_salida, fecha_retorno, porcentaje) 
                    VALUES (:id_mision, :region, :destino, :fecha_salida, :fecha_retorno, :porcentaje)
                """), {
                    "id_mision": mission_id,
                    "region": me.region,
                    "destino": me.destino,
                    "fecha_salida": me.fechaSalida,
                    "fecha_retorno": me.fechaRetorno,
                    "porcentaje": me.porcentaje
                })
            
            # Actualizar campos de viaje internacional
            if request.misionesExterior:
                mision.tipo_viaje = 'INTERNACIONAL'
                mision.region_exterior = request.misionesExterior[0].region
        
        # Recalcular monto total
        total_result = db_financiero.execute(text("""
            SELECT 
                COALESCE(SUM(vc.cantidad_dias * vc.monto_por_dia), 0) +
                COALESCE(SUM(vp.monto_desayuno + vp.monto_almuerzo + vp.monto_cena + vp.monto_hospedaje), 0) +
                COALESCE(SUM(t.monto), 0) as total
            FROM misiones m
            LEFT JOIN items_viaticos_completos vc ON m.id_mision = vc.id_mision
            LEFT JOIN items_viaticos vp ON m.id_mision = vp.id_mision
            LEFT JOIN items_transporte t ON m.id_mision = t.id_mision
            WHERE m.id_mision = :id_mision
        """), {"id_mision": mission_id})
        
        monto_total = total_result.fetchone().total or Decimal("0.00")
        mision.monto_total_calculado = monto_total
        mision.requiere_refrendo_cgr = monto_total >= Decimal("1000.00")
        mision.id_estado_flujo = 11 
        
        # Obtener ID de usuario para auditoría
        id_usuario = get_usuario_for_employee(personal_id, db_financiero)
        client_ip = get_client_ip(http_request)
        
        # Registrar en historial
        db_financiero.execute(text("""
            INSERT INTO historial_flujo 
            (id_mision, id_usuario_accion, id_estado_anterior, id_estado_nuevo, tipo_accion, comentarios, ip_usuario) 
            VALUES (:id_mision, :id_usuario, :estado_anterior, :estado_nuevo, :accion, :comentario, :ip)
        """), {
            "id_mision": mission_id,
            "id_usuario": id_usuario,
            "estado_anterior": mision.id_estado_flujo,
            "estado_nuevo": mision.id_estado_flujo,
            "accion": "ACTUALIZAR",
            "comentario": f"Solicitud de viáticos actualizada desde portal de empleados por {cedula}",
            "ip": client_ip
        })
        
        db_financiero.commit()
        
        return {
            "success": True,
            "message": "Solicitud de viáticos actualizada exitosamente",
            "data": {
                "id_mision": mission_id,
                "monto_total": float(monto_total)
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        db_financiero.rollback()
        print(f"Error actualizando solicitud de viáticos: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error interno del servidor"
        )

@router.put("/petty-cash/{mission_id}", summary="Actualizar solicitud de caja menuda")
async def update_petty_cash(
    mission_id: int,
    request: PettyCashUpdateRequest,
    http_request: Request,
    db_financiero: Session = Depends(get_db_financiero),
    db_rrhh: Session = Depends(get_db_rrhh),
    current_employee: dict = Depends(get_current_employee)
):
    """
    Actualiza una solicitud de caja menuda existente.
    Solo permitido en estados: BORRADOR, DEVUELTO_CORRECCION
    """
    try:
        # Obtener personal_id del empleado
        cedula = current_employee.get("cedula")
        personal_id = get_employee_personal_id(cedula, db_rrhh)
        
        # Verificar que la misión existe y pertenece al empleado
        mision = db_financiero.query(MisionModel).filter(
            MisionModel.id_mision == mission_id,
            MisionModel.beneficiario_personal_id == personal_id,
            MisionModel.tipo_mision == TipoMision.CAJA_MENUDA
        ).first()
        
        if not mision:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Solicitud de caja menuda no encontrada"
            )
        
        # Verificar que está en estado editable
        estados_editables = [11, 8]  # PENDIENTE_JEFE, DEVUELTO_CORRECCION
        if mision.id_estado_flujo not in estados_editables:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Solo se pueden editar solicitudes en estado PENDIENTE_JEFE o DEVUELTO_CORRECCION"
            )
        
        # ✅ GUARDAR ESTADO ANTERIOR ANTES DE CAMBIAR
        estado_anterior = mision.id_estado_flujo
        
        # Actualizar campos básicos si se proporcionan
        if request.trabajo_a_realizar is not None:
            mision.objetivo_mision = request.trabajo_a_realizar
        
        if request.para is not None:
            mision.destino_codnivel2 = int(request.para)
            # Actualizar descripción del destino
            destino_descripcion = get_department_description(request.para, db_rrhh)
            mision.destino_mision = destino_descripcion
        
        # Actualizar viáticos de caja menuda si se proporcionan
        if request.viaticosCompletos is not None:
            # Obtener límite diario
            limite_diario = Decimal(get_system_config_value("LIMITE_EFECTIVO_VIATICOS", db_financiero, "200"))
            
            # Validar límites
            for viatico in request.viaticosCompletos:
                total_dia = viatico.desayuno + viatico.almuerzo + viatico.cena + viatico.transporte
                if total_dia > limite_diario:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Un viático excede el límite diario de B/. {limite_diario}"
                    )
                if total_dia <= 0:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Debe ingresar al menos un monto mayor a 0 por día"
                    )
            
            # Eliminar viáticos existentes
            db_financiero.execute(text("""
                DELETE FROM misiones_caja_menuda WHERE id_mision = :id_mision
            """), {"id_mision": mission_id})
            
            # Insertar nuevos viáticos
            monto_total = Decimal("0.00")
            for viatico in request.viaticosCompletos:
                db_financiero.execute(text("""
                    INSERT INTO misiones_caja_menuda 
                    (id_mision, fecha, hora_de, hora_hasta, desayuno, almuerzo, cena, transporte) 
                    VALUES (:id_mision, :fecha, :hora_de, :hora_hasta, :desayuno, :almuerzo, :cena, :transporte)
                """), {
                    "id_mision": mission_id,
                    "fecha": viatico.fecha,
                    "hora_de": viatico.horaDe,
                    "hora_hasta": viatico.horaHasta,
                    "desayuno": viatico.desayuno,
                    "almuerzo": viatico.almuerzo,
                    "cena": viatico.cena,
                    "transporte": viatico.transporte
                })
                
                monto_total += viatico.desayuno + viatico.almuerzo + viatico.cena + viatico.transporte
            
            # Actualizar monto total
            mision.monto_total_calculado = monto_total
        
        # ✅ CAMBIAR ESTADO A PENDIENTE_JEFE DESPUÉS DE EDITAR
        mision.id_estado_flujo = 11  # PENDIENTE_JEFE
        
        # Obtener ID de usuario para auditoría
        id_usuario = get_usuario_for_employee(personal_id, db_financiero)
        client_ip = get_client_ip(http_request)
        
        # ✅ REGISTRAR EN HISTORIAL CON CAMBIO DE ESTADO
        db_financiero.execute(text("""
            INSERT INTO historial_flujo 
            (id_mision, id_usuario_accion, id_estado_anterior, id_estado_nuevo, tipo_accion, comentarios, ip_usuario) 
            VALUES (:id_mision, :id_usuario, :estado_anterior, :estado_nuevo, :accion, :comentario, :ip)
        """), {
            "id_mision": mission_id,
            "id_usuario": id_usuario,
            "estado_anterior": estado_anterior,  # ✅ Estado anterior real
            "estado_nuevo": 11,  # ✅ PENDIENTE_JEFE
            "accion": "ACTUALIZAR",
            "comentario": f"Solicitud de caja menuda actualizada desde portal de empleados por {cedula} - Enviada para aprobación",
            "ip": client_ip
        })
        
        db_financiero.commit()
        
        return {
            "success": True,
            "message": "Solicitud de caja menuda actualizada y enviada para aprobación",
            "data": {
                "id_mision": mission_id,
                "monto_total": float(mision.monto_total_calculado),
                "estado": "PENDIENTE_JEFE"  # ✅ Informar nuevo estado
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        db_financiero.rollback()
        print(f"Error actualizando solicitud de caja menuda: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error interno del servidor"
        )

@router.get("/{mission_id}", summary="Obtener detalles completos de una solicitud")
async def get_mission_details(
    mission_id: int,
    db_financiero: Session = Depends(get_db_financiero),
    db_rrhh: Session = Depends(get_db_rrhh),
    current_employee: dict = Depends(get_current_employee)
):
    """
    Obtiene los detalles COMPLETOS de una solicitud específica con todos sus items.
    """
    try:
        # Obtener personal_id del empleado
        cedula = current_employee.get("cedula")
        personal_id = get_employee_personal_id(cedula, db_rrhh)
        
        # Buscar la misión
        mision = db_financiero.query(MisionModel).filter(
            MisionModel.id_mision == mission_id,
            MisionModel.beneficiario_personal_id == personal_id
        ).first()
        
        if not mision:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Solicitud no encontrada"
            )
        
        # ✅ OBTENER NOMBRES DE VICEPRESIDENCIA Y DEPARTAMENTO
        departamento_info = None
        vicepresidencia_info = None
        
        if mision.destino_codnivel2:
            # Obtener información del departamento (nivel2)
            dept_result = db_rrhh.execute(text("""
                SELECT n2.codorg, n2.descrip as dept_name, n2.gerencia,
                       n1.codorg as vice_codigo, n1.descrip as vice_name
                FROM aitsa_rrhh.nomnivel2 n2
                LEFT JOIN aitsa_rrhh.nomnivel1 n1 ON n2.gerencia = n1.codorg
                WHERE n2.codorg = :codigo
            """), {"codigo": str(mision.destino_codnivel2)})
            
            dept_row = dept_result.fetchone()
            if dept_row:
                departamento_info = {
                    "codigo": dept_row.codorg,
                    "nombre": dept_row.dept_name,
                    "gerencia": dept_row.gerencia
                }
                if dept_row.vice_codigo and dept_row.vice_name:
                    vicepresidencia_info = {
                        "codigo": dept_row.vice_codigo,
                        "nombre": dept_row.vice_name
                    }
        
        # Datos básicos de la misión
        mission_data = {
            "id_mision": mision.id_mision,
            "numero_solicitud": mision.numero_solicitud,
            "tipo_mision": str(mision.tipo_mision),
            "objetivo_mision": mision.objetivo_mision,
            "destino_mision": mision.destino_mision,
            "categoria_beneficiario": str(mision.categoria_beneficiario) if mision.categoria_beneficiario else None,
            "tipo_viaje": str(mision.tipo_viaje) if mision.tipo_viaje else None,
            "region_exterior": mision.region_exterior,
            "fecha_salida": mision.fecha_salida.isoformat() if mision.fecha_salida else None,
            "fecha_retorno": mision.fecha_retorno.isoformat() if mision.fecha_retorno else None,
            "transporte_oficial": mision.transporte_oficial,
            "monto_total_calculado": float(mision.monto_total_calculado),
            "monto_aprobado": float(mision.monto_aprobado) if mision.monto_aprobado else None,
            "fecha_limite_presentacion": mision.fecha_limite_presentacion.isoformat() if mision.fecha_limite_presentacion else None,
            
            # ✅ AGREGAR INFORMACIÓN DE DEPARTAMENTO Y VICEPRESIDENCIA
            "departamento": departamento_info,
            "vicepresidencia": vicepresidencia_info,
            
            "estado_flujo": {
                "id_estado_flujo": mision.estado_flujo.id_estado_flujo,
                "nombre_estado": mision.estado_flujo.nombre_estado,
                "descripcion": mision.estado_flujo.descripcion
            } if mision.estado_flujo else None,
            "can_edit": mision.id_estado_flujo in [11, 8],  # PENDIENTE_JEFE, DEVUELTO_CORRECCION
            "created_at": mision.created_at.isoformat() if mision.created_at else None,
            "updated_at": mision.updated_at.isoformat() if mision.updated_at else None
        }
        
        # DETALLES ESPECÍFICOS SEGÚN EL TIPO (igual que antes)
        if mision.tipo_mision == TipoMision.VIATICOS:
            # Obtener viáticos completos
            viaticos_completos_result = db_financiero.execute(text("""
                SELECT cantidad_dias, monto_por_dia
                FROM items_viaticos_completos 
                WHERE id_mision = :id_mision
                ORDER BY id_item_viatico_completo
            """), {"id_mision": mission_id})
            
            viaticos_completos = []
            for row in viaticos_completos_result.fetchall():
                viaticos_completos.append({
                    "cantidadDias": row.cantidad_dias,
                    "pagoPorDia": float(row.monto_por_dia)
                })
            
            # Obtener viáticos parciales
            viaticos_parciales_result = db_financiero.execute(text("""
                SELECT fecha, monto_desayuno, monto_almuerzo, monto_cena, monto_hospedaje
                FROM items_viaticos 
                WHERE id_mision = :id_mision
                ORDER BY fecha
            """), {"id_mision": mission_id})
            
            viaticos_parciales = []
            for row in viaticos_parciales_result.fetchall():
                viaticos_parciales.append({
                    "fecha": row.fecha.isoformat(),
                    "desayuno": "SI" if row.monto_desayuno > 0 else "NO",
                    "almuerzo": "SI" if row.monto_almuerzo > 0 else "NO", 
                    "cena": "SI" if row.monto_cena > 0 else "NO",
                    "hospedaje": "SI" if row.monto_hospedaje > 0 else "NO",
                    "monto_desayuno": float(row.monto_desayuno),
                    "monto_almuerzo": float(row.monto_almuerzo),
                    "monto_cena": float(row.monto_cena),
                    "monto_hospedaje": float(row.monto_hospedaje)
                })
            
            # Obtener transporte
            transporte_result = db_financiero.execute(text("""
                SELECT fecha, tipo, origen, destino, monto
                FROM items_transporte 
                WHERE id_mision = :id_mision
                ORDER BY fecha
            """), {"id_mision": mission_id})
            
            transporte_detalle = []
            for row in transporte_result.fetchall():
                transporte_detalle.append({
                    "fecha": row.fecha.isoformat(),
                    "tipo": row.tipo,
                    "origen": row.origen,
                    "destino": row.destino,
                    "monto": float(row.monto),
                })
            
            # Obtener misiones al exterior
            exterior_result = db_financiero.execute(text("""
                SELECT region, destino, fecha_salida, fecha_retorno, porcentaje
                FROM items_misiones_exterior 
                WHERE id_mision = :id_mision
                ORDER BY fecha_salida
            """), {"id_mision": mission_id})
            
            misiones_exterior = []
            for row in exterior_result.fetchall():
                misiones_exterior.append({
                    "region": row.region,
                    "destino": row.destino,
                    "fechaSalida": row.fecha_salida.isoformat(),
                    "fechaRetorno": row.fecha_retorno.isoformat(),
                    "porcentaje": float(row.porcentaje)
                })
            
            # Agregar detalles de viáticos
            mission_data["detalles"] = {
                "viaticosCompletos": viaticos_completos,
                "viaticosParciales": viaticos_parciales,
                "transporteDetalle": transporte_detalle,
                "misionesExterior": misiones_exterior
            }
            
        elif mision.tipo_mision == TipoMision.CAJA_MENUDA:
            # Obtener viáticos de caja menuda
            caja_menuda_result = db_financiero.execute(text("""
                SELECT fecha, hora_de, hora_hasta, desayuno, almuerzo, cena, transporte
                FROM misiones_caja_menuda 
                WHERE id_mision = :id_mision
                ORDER BY fecha, hora_de
            """), {"id_mision": mission_id})
            
            viaticos_caja_menuda = []
            for row in caja_menuda_result.fetchall():
                viaticos_caja_menuda.append({
                    "fecha": row.fecha.isoformat(),
                    "horaDe": row.hora_de,
                    "horaHasta": row.hora_hasta,
                    "desayuno": float(row.desayuno),
                    "almuerzo": float(row.almuerzo),
                    "cena": float(row.cena),
                    "transporte": float(row.transporte)
                })
            
            # Agregar detalles de caja menuda
            mission_data["detalles"] = {
                "viaticosCompletos": viaticos_caja_menuda,
                "destino_codnivel2": mision.destino_codnivel2
            }
        
        return {
            "success": True,
            "data": mission_data
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error obteniendo detalles de misión: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error obteniendo detalles: {str(e)}"
        )