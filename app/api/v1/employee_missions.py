import os
import uuid
from typing import List, Optional
from datetime import date, datetime, timedelta
from decimal import Decimal
import json

from fastapi import APIRouter, Depends, HTTPException, status, Request, UploadFile, File, Query
from sqlalchemy.orm import Session
from sqlalchemy import text

from ...core.database import get_db_financiero, get_db_rrhh
from ...core.exceptions import BusinessException, ValidationException
from ...api.deps import get_current_employee
from ...models.mission import Mision as MisionModel, EstadoFlujo, Adjunto
from ...schemas.mission import *
from ...models.enums import TipoMision, TipoDocumento

# Esquemas específicos para empleados
from pydantic import BaseModel, Field, validator

# --- Configuración de Archivos ---
UPLOAD_DIR = "uploads/missions"
ALLOWED_EXTENSIONS = {".pdf", ".doc", ".docx", ".xls", ".xlsx", ".png", ".jpg", ".jpeg"}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB

os.makedirs(UPLOAD_DIR, exist_ok=True)

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

def get_tarifas_dinamicas(db_financiero: Session) -> dict:
    """Obtiene las tarifas dinámicas del sistema usando exactamente la misma lógica que el endpoint /tarifas"""
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
        
        # Calcular tarifas por comida basadas en porcentajes específicos por categoría
        def calcular_tarifas_comidas(tarifa_base, categoria):
            # Mapear categorías a las claves de configuración
            categoria_mapping = {
                "TITULAR": "TITULAR_NACIONAL",
                "OTROS SERVIDORES PÚBLICOS": "OTROS_SERVIDORES_NACIONAL", 
                "OTRAS PERSONAS": "OTRAS_PERSONAS_NACIONAL"
            }
            
            categoria_key = categoria_mapping.get(categoria, "TITULAR_NACIONAL")
            
            return {
                "DESAYUNO": round(tarifa_base * (configs.get(f'PORCENTAJE_DESAYUNO_{categoria_key}', 20) / 100), 2),
                "ALMUERZO": round(tarifa_base * (configs.get(f'PORCENTAJE_ALMUERZO_{categoria_key}', 30) / 100), 2),
                "CENA": round(tarifa_base * (configs.get(f'PORCENTAJE_CENA_{categoria_key}', 30) / 100), 2)
            }
        
        # Construir estructura de tarifas usando exactamente la misma lógica que el endpoint /tarifas
        tarifas_nacionales = {
            "TITULAR": {
                **calcular_tarifas_comidas(configs.get('TARIFA_VIATICO_TITULAR_NACIONAL', 30.00), "TITULAR"),
                "HOSPEDAJE": configs.get('TARIFA_HOSPEDAJE_TITULAR_NACIONAL', 99.00)
            },
            "OTROS SERVIDORES PÚBLICOS": {
                **calcular_tarifas_comidas(configs.get('TARIFA_VIATICO_OTROS_SERVIDORES_NACIONAL', 20.00), "OTROS SERVIDORES PÚBLICOS"),
                "HOSPEDAJE": configs.get('TARIFA_HOSPEDAJE_OTROS_SERVIDORES_NACIONAL', 84.00)
            },
            "OTRAS PERSONAS": {
                **calcular_tarifas_comidas(configs.get('TARIFA_VIATICO_OTRAS_PERSONAS_NACIONAL', 20.00), "OTRAS PERSONAS"),
                "HOSPEDAJE": configs.get('TARIFA_HOSPEDAJE_OTRAS_PERSONAS_NACIONAL', 84.00)
            }
        }
        
        print(f"DEBUG: Tarifas calculadas: {tarifas_nacionales}")
        
        return tarifas_nacionales
    except Exception as e:
        print(f"Error obteniendo tarifas dinámicas: {e}")
        # Fallback a tarifas por defecto
        return {
            "TITULAR": {
                "DESAYUNO": 6.00,
                "ALMUERZO": 10.00,
                "CENA": 10.00,
                "HOSPEDAJE": 99.00
            },
            "OTROS SERVIDORES PÚBLICOS": {
                "DESAYUNO": 4.00,
                "ALMUERZO": 6.00,
                "CENA": 6.00,
                "HOSPEDAJE": 84.00
            },
            "OTRAS PERSONAS": {
                "DESAYUNO": 4.00,
                "ALMUERZO": 6.00,
                "CENA": 6.00,
                "HOSPEDAJE": 84.00
            }
        }

def convert_si_no_to_amount(valor: str, categoria: str, concepto: str, db_financiero: Session = None) -> Decimal:
    if valor.upper() != 'SI':
        return Decimal("0.00")
    
    # Obtener tarifas dinámicas del sistema usando la misma lógica que el endpoint /tarifas
    if db_financiero:
        try:
            tarifas = get_tarifas_dinamicas(db_financiero)
            
            # Mapear las categorías del frontend a las categorías del sistema
            categoria_mapping = {
                "TITULAR": "TITULAR",
                "OTROS SERVIDORES PUBLICOS": "OTROS SERVIDORES PÚBLICOS",  # Sin tilde -> Con tilde
                "OTRAS PERSONAS": "OTRAS PERSONAS"
            }
            
            categoria_sistema = categoria_mapping.get(categoria, categoria)
            tarifa = tarifas.get(categoria_sistema, {}).get(concepto.upper(), 0.00)
            
            
            return Decimal(str(tarifa))
        except Exception as e:
            print(f"Error obteniendo tarifas dinámicas, usando fallback: {e}")
    
    # Fallback a tarifas hardcodeadas (solo para compatibilidad)
    tarifas_fallback = {
        'TITULAR': {
            'DESAYUNO': Decimal("6.00"),
            'ALMUERZO': Decimal("10.00"),
            'CENA': Decimal("10.00"),
            'HOSPEDAJE': Decimal("99.00")
        },
        'OTROS SERVIDORES PUBLICOS': {
            'DESAYUNO': Decimal("4.00"),
            'ALMUERZO': Decimal("6.00"),
            'CENA': Decimal("6.00"),
            'HOSPEDAJE': Decimal("84.00")
        },
        'OTRAS PERSONAS': {
            'DESAYUNO': Decimal("4.00"),
            'ALMUERZO': Decimal("6.00"),
            'CENA': Decimal("6.00"),
            'HOSPEDAJE': Decimal("84.00")
        }
    }
    
    return tarifas_fallback.get(categoria, {}).get(concepto.upper(), Decimal("0.00"))

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
        categoria_str = str(request.categoria).replace('_', ' ') if request.categoria else 'TITULAR'
        for vp in request.viaticosParciales:
            monto_desayuno = convert_si_no_to_amount(vp.desayuno, categoria_str, 'DESAYUNO', db_financiero)
            monto_almuerzo = convert_si_no_to_amount(vp.almuerzo, categoria_str, 'ALMUERZO', db_financiero)
            monto_cena = convert_si_no_to_amount(vp.cena, categoria_str, 'CENA', db_financiero)
            monto_hospedaje = convert_si_no_to_amount(vp.hospedaje, categoria_str, 'HOSPEDAJE', db_financiero)
            
            print(f"DEBUG: Montos calculados para {vp.fecha}: desayuno={monto_desayuno}, almuerzo={monto_almuerzo}, cena={monto_cena}, hospedaje={monto_hospedaje}")
            
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
        
        # Calcular monto total con logging detallado
        print(f"DEBUG: Calculando total para misión {mision.id_mision}")
        
        # Verificar viáticos completos
        vc_result = db_financiero.execute(text("""
            SELECT SUM(cantidad_dias * monto_por_dia) as total_vc
            FROM items_viaticos_completos 
            WHERE id_mision = :id_mision
        """), {"id_mision": mision.id_mision})
        total_vc = vc_result.fetchone().total_vc or 0
        print(f"DEBUG: Total viáticos completos: {total_vc}")
        
        # Verificar viáticos parciales
        vp_result = db_financiero.execute(text("""
            SELECT SUM(monto_desayuno + monto_almuerzo + monto_cena + monto_hospedaje) as total_vp
            FROM items_viaticos 
            WHERE id_mision = :id_mision
        """), {"id_mision": mision.id_mision})
        total_vp = vp_result.fetchone().total_vp or 0
        print(f"DEBUG: Total viáticos parciales: {total_vp}")
        
        # Verificar transporte
        t_result = db_financiero.execute(text("""
            SELECT SUM(monto) as total_t
            FROM items_transporte 
            WHERE id_mision = :id_mision
        """), {"id_mision": mision.id_mision})
        total_t = t_result.fetchone().total_t or 0
        print(f"DEBUG: Total transporte: {total_t}")
        
        # Calcular total
        monto_total = Decimal(str(total_vc + total_vp + total_t))
        print(f"DEBUG: Total final: {monto_total}")
        
        # Actualizar monto total
        mision.monto_total_calculado = monto_total
        mision.requiere_refrendo_cgr = monto_total >= Decimal("1000.00")
        
        # Obtener IP real del usuario
        client_ip = get_client_ip(http_request)
        
        # Registrar en historial
        db_financiero.execute(text("""
            INSERT INTO historial_flujo 
            (id_mision, id_usuario_accion, id_estado_nuevo, tipo_accion, comentarios, ip_usuario, datos_adicionales) 
            VALUES (:id_mision, :id_usuario, :estado, :accion, :comentario, :ip, :datos_adicionales)
        """), {
            "id_mision": mision.id_mision,
            "id_usuario": None,  # NULL para empleados externos al módulo financiero
            "estado": 11,
            "accion": "CREAR",
            "comentario": f"Solicitud de viáticos creada desde portal de empleados por {cedula}",
            "ip": client_ip,
            "datos_adicionales": json.dumps({
                "usuario_cedula": cedula,
                "usuario_nombre": current_employee.get('apenom', 'Empleado'),
                "origen": "portal_empleados"
            })
        })
        
        db_financiero.commit()
        
        # Crear notificación en la base de datos para el jefe inmediato
        try:
            from app.services.notifaction_service import NotificationService
            notification_service = NotificationService(db_financiero)
            
            # Obtener el jefe inmediato del empleado
            jefe_personal_id = get_jefe_inmediato_personal_id(personal_id, db_rrhh)
            
            if jefe_personal_id:
                print(f"🔔 Creando notificación para jefe {jefe_personal_id}")
                notification = notification_service.create_mission_created_notification(
                    mission_id=mision.id_mision,
                    jefe_personal_id=jefe_personal_id,
                    numero_solicitud=numero_solicitud
                )
                print(f"✅ Notificación creada exitosamente: {notification.notificacion_id}")
            else:
                print("⚠️ No se pudo obtener el jefe inmediato, no se crea notificación")
        except Exception as e:
            print(f"❌ Error creating notification: {str(e)}")
            import traceback
            traceback.print_exc()
        
        # Enviar notificación al jefe inmediato
        try:
            from app.services.email_service import EmailService
            email_service = EmailService(db_financiero)
            
            # Preparar datos para el email
            email_data = {
                'numero_solicitud': numero_solicitud,
                'tipo': 'Viáticos',
                'solicitante': current_employee.get('apenom', 'Empleado'),
                'departamento': 'Departamento del Solicitante',  # TODO: Obtener nombre del departamento
                'fecha': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'monto': f"${float(monto_total):,.2f}",
                'objetivo': request.objetivo
            }
            
            # Enviar notificación al jefe inmediato en background
            import asyncio
            asyncio.create_task(email_service.send_new_request_notification(
                mision.id_mision, email_data, db_rrhh
            ))
                
        except Exception as e:
            # Log del error pero no fallar la operación principal
            print(f"Error enviando notificación al jefe inmediato: {str(e)}")
        
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
            (id_mision, id_usuario_accion, id_estado_nuevo, tipo_accion, comentarios, ip_usuario, datos_adicionales) 
            VALUES (:id_mision, :id_usuario, :estado, :accion, :comentario, :ip, :datos_adicionales)
        """), {
            "id_mision": mision.id_mision,
            "id_usuario": None,  # NULL para empleados externos al módulo financiero
            "estado": 11,
            "accion": "CREAR",
            "comentario": f"Solicitud de caja menuda creada desde portal de empleados por {cedula}",
            "ip": client_ip,
            "datos_adicionales": json.dumps({
                "usuario_cedula": cedula,
                "usuario_nombre": current_employee.get('apenom', 'Empleado'),
                "origen": "portal_empleados"
            })
        })
        
        db_financiero.commit()
        
        # Enviar notificación al jefe inmediato
        try:
            from app.services.email_service import EmailService
            email_service = EmailService(db_financiero)
            
            # Preparar datos para el email
            email_data = {
                'numero_solicitud': numero_solicitud,
                'tipo': 'Caja Menuda',
                'solicitante': current_employee.get('apenom', 'Empleado'),
                'departamento': 'Departamento del Solicitante',  # TODO: Obtener nombre del departamento
                'fecha': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'monto': f"${float(monto_total):,.2f}",
                'objetivo': request.trabajo_a_realizar
            }
            
            # Enviar notificación al jefe inmediato en background
            import asyncio
            asyncio.create_task(email_service.send_new_request_notification(
                mision.id_mision, email_data, db_rrhh
            ))
                
        except Exception as e:
            # Log del error pero no fallar la operación principal
            print(f"Error enviando notificación al jefe inmediato: {str(e)}")
        
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
        
        # Calcular tarifas por comida basadas en porcentajes específicos por categoría
        def calcular_tarifas_comidas(tarifa_base, categoria):
            # Mapear categorías a las claves de configuración
            categoria_mapping = {
                "TITULAR": "TITULAR_NACIONAL",
                "OTROS SERVIDORES PÚBLICOS": "OTROS_SERVIDORES_NACIONAL", 
                "OTRAS PERSONAS": "OTRAS_PERSONAS_NACIONAL"
            }
            
            categoria_key = categoria_mapping.get(categoria, "TITULAR_NACIONAL")
            
            return {
                "DESAYUNO": round(tarifa_base * (configs.get(f'PORCENTAJE_DESAYUNO_{categoria_key}', 20) / 100), 2),
                "ALMUERZO": round(tarifa_base * (configs.get(f'PORCENTAJE_ALMUERZO_{categoria_key}', 30) / 100), 2),
                "CENA": round(tarifa_base * (configs.get(f'PORCENTAJE_CENA_{categoria_key}', 30) / 100), 2)
            }
        
        # Construir estructura de tarifas
        tarifas = {
            "tarifas_nacionales": {
                "TITULAR": {
                    **calcular_tarifas_comidas(configs.get('TARIFA_VIATICO_TITULAR_NACIONAL', 30.00), "TITULAR"),
                    "HOSPEDAJE": configs.get('TARIFA_HOSPEDAJE_TITULAR_NACIONAL', 99.00)
                },
                "OTROS SERVIDORES PÚBLICOS": {
                    **calcular_tarifas_comidas(configs.get('TARIFA_VIATICO_OTROS_SERVIDORES_NACIONAL', 20.00), "OTROS SERVIDORES PÚBLICOS"),
                    "HOSPEDAJE": configs.get('TARIFA_HOSPEDAJE_OTROS_SERVIDORES_NACIONAL', 84.00)
                },
                "OTRAS PERSONAS": {
                    **calcular_tarifas_comidas(configs.get('TARIFA_VIATICO_OTRAS_PERSONAS_NACIONAL', 20.00), "OTRAS PERSONAS"),
                    "HOSPEDAJE": configs.get('TARIFA_HOSPEDAJE_OTRAS_PERSONAS_NACIONAL', 84.00)
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
            db_financiero.execute(text("""
                DELETE FROM items_viaticos WHERE id_mision = :id_mision
            """), {"id_mision": mission_id})
            
            # Insertar nuevos
            for vp in request.viaticosParciales:
                monto_desayuno = convert_si_no_to_amount(vp.desayuno, mision.categoria_beneficiario, 'DESAYUNO', db_financiero)
                monto_almuerzo = convert_si_no_to_amount(vp.almuerzo, mision.categoria_beneficiario, 'ALMUERZO', db_financiero)
                monto_cena = convert_si_no_to_amount(vp.cena, mision.categoria_beneficiario, 'CENA', db_financiero)
                monto_hospedaje = convert_si_no_to_amount(vp.hospedaje, mision.categoria_beneficiario, 'HOSPEDAJE', db_financiero)
                
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
            (id_mision, id_usuario_accion, id_estado_anterior, id_estado_nuevo, tipo_accion, comentarios, ip_usuario, datos_adicionales) 
            VALUES (:id_mision, :id_usuario, :estado_anterior, :estado_nuevo, :accion, :comentario, :ip, :datos_adicionales)
        """), {
            "id_mision": mission_id,
            "id_usuario": None,  # NULL para empleados externos al módulo financiero
            "estado_anterior": mision.id_estado_flujo,
            "estado_nuevo": mision.id_estado_flujo,
            "accion": "ACTUALIZAR",
            "comentario": f"Solicitud de viáticos actualizada desde portal de empleados por {cedula}",
            "ip": client_ip,
            "datos_adicionales": json.dumps({
                "usuario_cedula": cedula,
                "usuario_nombre": current_employee.get('apenom', 'Empleado'),
                "origen": "portal_empleados"
            })
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
            (id_mision, id_usuario_accion, id_estado_anterior, id_estado_nuevo, tipo_accion, comentarios, ip_usuario, datos_adicionales) 
            VALUES (:id_mision, :id_usuario, :estado_anterior, :estado_nuevo, :accion, :comentario, :ip, :datos_adicionales)
        """), {
            "id_mision": mission_id,
            "id_usuario": None,  # NULL para empleados externos al módulo financiero
            "estado_anterior": estado_anterior,  # ✅ Estado anterior real
            "estado_nuevo": 11,  # ✅ PENDIENTE_JEFE
            "accion": "ACTUALIZAR",
            "comentario": f"Solicitud de caja menuda actualizada desde portal de empleados por {cedula} - Enviada para aprobación",
            "ip": client_ip,
            "datos_adicionales": json.dumps({
                "usuario_cedula": cedula,
                "usuario_nombre": current_employee.get('apenom', 'Empleado'),
                "origen": "portal_empleados"
            })
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
        # Buscar la misión sin filtrar por empleado actual
        mision = db_financiero.query(MisionModel).filter(
            MisionModel.id_mision == mission_id
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
        
        # ✅ OBTENER INFORMACIÓN DEL BENEFICIARIO DESDE RRHH
        beneficiario_info = None
        if mision.beneficiario_personal_id:
            beneficiario_result = db_rrhh.execute(text("""
                SELECT personal_id, apenom, ficha, cedula, codcargo, nomposicion_id,
                       codnivel1, codnivel2
                FROM aitsa_rrhh.nompersonal 
                WHERE personal_id = :personal_id AND estado != 'De Baja'
            """), {"personal_id": mision.beneficiario_personal_id})
            
            beneficiario_row = beneficiario_result.fetchone()
            if beneficiario_row:
                beneficiario_info = {
                    "personal_id": beneficiario_row.personal_id,
                    "nombre": beneficiario_row.apenom,
                    "ficha": beneficiario_row.ficha,
                    "cedula": beneficiario_row.cedula,
                    "cargo": beneficiario_row.codcargo,
                    "posicion_id": beneficiario_row.nomposicion_id,
                    "nivel1": beneficiario_row.codnivel1,
                    "nivel2": beneficiario_row.codnivel2
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
            "requiere_refrendo_cgr": mision.requiere_refrendo_cgr,
            "numero_gestion_cobro": mision.numero_gestion_cobro,
            "observaciones_especiales": mision.observaciones_especiales,
            
            # ✅ AGREGAR INFORMACIÓN DE DEPARTAMENTO Y VICEPRESIDENCIA
            "departamento": departamento_info,
            "vicepresidencia": vicepresidencia_info,
            
            # ✅ AGREGAR INFORMACIÓN DEL BENEFICIARIO
            "beneficiario": beneficiario_info,
            
            "estado_flujo": {
                "id_estado_flujo": mision.estado_flujo.id_estado_flujo,
                "nombre_estado": mision.estado_flujo.nombre_estado,
                "descripcion": mision.estado_flujo.descripcion
            } if mision.estado_flujo else None,
            "can_edit": mision.id_estado_flujo in [11, 8],  # PENDIENTE_JEFE, DEVUELTO_CORRECCION
            "created_at": mision.created_at.isoformat() if mision.created_at else None,
            "updated_at": mision.updated_at.isoformat() if mision.updated_at else None,
            
            # Campos para tracking de estado del cheque (solo para Viáticos)
            "cheque_confeccionado": mision.cheque_confeccionado or False,
            "cheque_firmado": mision.cheque_firmado or False
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
        
        # Obtener archivos adjuntos
        adjuntos_result = db_financiero.execute(text("""
            SELECT id_adjunto, nombre_archivo, nombre_original, url_almacenamiento,
                   tipo_mime, tamano_bytes, tipo_documento, fecha_carga
            FROM adjuntos 
            WHERE id_mision = :id_mision
            ORDER BY fecha_carga DESC
        """), {"id_mision": mission_id})
        
        adjuntos = []
        for row in adjuntos_result.fetchall():
            adjuntos.append({
                "id_adjunto": row.id_adjunto,
                "nombre_archivo": row.nombre_archivo,
                "nombre_original": row.nombre_original,
                "url_almacenamiento": row.url_almacenamiento,
                "tipo_mime": row.tipo_mime,
                "tamano_bytes": row.tamano_bytes,
                "tipo_documento": row.tipo_documento,
                "fecha_carga": row.fecha_carga.isoformat() if row.fecha_carga else None
            })
        
        mission_data["adjuntos"] = adjuntos
        
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

@router.get("/public/{mission_id}", summary="Obtener detalles completos de una solicitud (sin validaciones)")
async def get_mission_details_public(
    mission_id: int,
    db_financiero: Session = Depends(get_db_financiero),
    db_rrhh: Session = Depends(get_db_rrhh)
):
    """
    Obtiene los detalles COMPLETOS de una solicitud específica con todos sus items.
    SIN VALIDACIONES DE PERMISOS - Acceso público a la información de la misión.
    """
    try:
        # Buscar la misión directamente sin validaciones de propiedad
        mision = db_financiero.query(MisionModel).filter(
            MisionModel.id_mision == mission_id
        ).first()
        
        if not mision:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Solicitud no encontrada"
            )
        
        # OBTENER NOMBRES DE VICEPRESIDENCIA Y DEPARTAMENTO
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
        
        # Obtener información del beneficiario desde RRHH
        beneficiario_info = None
        if mision.beneficiario_personal_id:
            beneficiario_result = db_rrhh.execute(text("""
                SELECT personal_id, apenom, ficha, cedula, codcargo, nomposicion_id,
                       codnivel1, codnivel2
                FROM aitsa_rrhh.nompersonal 
                WHERE personal_id = :personal_id AND estado != 'De Baja'
            """), {"personal_id": mision.beneficiario_personal_id})
            
            beneficiario_row = beneficiario_result.fetchone()
            if beneficiario_row:
                beneficiario_info = {
                    "personal_id": beneficiario_row.personal_id,
                    "nombre": beneficiario_row.apenom,
                    "ficha": beneficiario_row.ficha,
                    "cedula": beneficiario_row.cedula,
                    "cargo": beneficiario_row.codcargo,
                    "posicion_id": beneficiario_row.nomposicion_id,
                    "nivel1": beneficiario_row.codnivel1,
                    "nivel2": beneficiario_row.codnivel2
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
            "requiere_refrendo_cgr": mision.requiere_refrendo_cgr,
            "numero_gestion_cobro": mision.numero_gestion_cobro,
            "observaciones_especiales": mision.observaciones_especiales,
            
            # INFORMACIÓN DE DEPARTAMENTO Y VICEPRESIDENCIA
            "departamento": departamento_info,
            "vicepresidencia": vicepresidencia_info,
            
            # INFORMACIÓN DEL BENEFICIARIO
            "beneficiario": beneficiario_info,
            
            "estado_flujo": {
                "id_estado_flujo": mision.estado_flujo.id_estado_flujo,
                "nombre_estado": mision.estado_flujo.nombre_estado,
                "descripcion": mision.estado_flujo.descripcion
            } if mision.estado_flujo else None,
            "created_at": mision.created_at.isoformat() if mision.created_at else None,
            "updated_at": mision.updated_at.isoformat() if mision.updated_at else None,
            
            # Campos para tracking de estado del cheque (solo para Viáticos)
            "cheque_confeccionado": mision.cheque_confeccionado or False,
            "cheque_firmado": mision.cheque_firmado or False
        }
        
        # DETALLES ESPECÍFICOS SEGÚN EL TIPO
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
                    "monto": float(row.monto)
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
        
        # Obtener partidas presupuestarias de la misión
        partidas_result = db_financiero.execute(text("""
            SELECT id_partida_mision, codigo_partida, monto
            FROM mision_partidas_presupuestarias 
            WHERE id_mision = :id_mision
            ORDER BY id_partida_mision
        """), {"id_mision": mission_id})
        
        partidas_presupuestarias = []
        for row in partidas_result.fetchall():
            partidas_presupuestarias.append({
                "id_partida_mision": row.id_partida_mision,
                "codigo_partida": row.codigo_partida,
                "monto": float(row.monto)
            })
        
        # Obtener historial de la misión
        historial_result = db_financiero.execute(text("""
            SELECT hf.id_historial, hf.id_usuario_accion, hf.id_estado_anterior, 
                   hf.id_estado_nuevo, hf.tipo_accion, hf.comentarios, hf.datos_adicionales,
                   hf.ip_usuario, hf.fecha_accion, hf.observacion,
                   u.login_username,
                   ef_anterior.nombre_estado as estado_anterior_nombre,
                   ef_nuevo.nombre_estado as estado_nuevo_nombre
            FROM historial_flujo hf
            LEFT JOIN usuarios u ON hf.id_usuario_accion = u.id_usuario
            LEFT JOIN estados_flujo ef_anterior ON hf.id_estado_anterior = ef_anterior.id_estado_flujo
            LEFT JOIN estados_flujo ef_nuevo ON hf.id_estado_nuevo = ef_nuevo.id_estado_flujo
            WHERE hf.id_mision = :id_mision
            ORDER BY hf.fecha_accion DESC
        """), {"id_mision": mission_id})
        
        historial = []
        for row in historial_result.fetchall():
            historial.append({
                "id_historial": row.id_historial,
                "id_usuario_accion": row.id_usuario_accion,
                "id_estado_anterior": row.id_estado_anterior,
                "id_estado_nuevo": row.id_estado_nuevo,
                "tipo_accion": row.tipo_accion,
                "comentarios": row.comentarios,
                "datos_adicionales": row.datos_adicionales,
                "ip_usuario": row.ip_usuario,
                "fecha_accion": row.fecha_accion.isoformat() if row.fecha_accion else None,
                "observacion": row.observacion,
                "usuario": {
                    "login_username": row.login_username
                },
                "estado_anterior": row.estado_anterior_nombre,
                "estado_nuevo": row.estado_nuevo_nombre
            })
        
        mission_data["historial"] = historial
        mission_data["partidas_presupuestarias"] = partidas_presupuestarias
        
        # Obtener archivos adjuntos
        adjuntos_result = db_financiero.execute(text("""
            SELECT id_adjunto, nombre_archivo, nombre_original, url_almacenamiento,
                   tipo_mime, tamano_bytes, tipo_documento, fecha_carga
            FROM adjuntos 
            WHERE id_mision = :id_mision
            ORDER BY fecha_carga DESC
        """), {"id_mision": mission_id})
        
        adjuntos = []
        for row in adjuntos_result.fetchall():
            adjuntos.append({
                "id_adjunto": row.id_adjunto,
                "nombre_archivo": row.nombre_archivo,
                "nombre_original": row.nombre_original,
                "url_almacenamiento": row.url_almacenamiento,
                "tipo_mime": row.tipo_mime,
                "tamano_bytes": row.tamano_bytes,
                "tipo_documento": row.tipo_documento,
                "fecha_carga": row.fecha_carga.isoformat() if row.fecha_carga else None
            })
        
        mission_data["adjuntos"] = adjuntos
        
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

@router.post("/validate-viaticos-rango", summary="Validar viáticos en rango de fechas")
async def validate_viaticos_rango(
    request: ViaticoValidationRequest,
    db_financiero: Session = Depends(get_db_financiero),
    db_rrhh: Session = Depends(get_db_rrhh),
    current_employee: dict = Depends(get_current_employee)
):
    """
    Verificar si el usuario ya tiene viáticos registrados en el rango de fechas solicitado.
    
    **Características:**
    - Permite viáticos en el mismo día si las horas son diferentes
    - Excluye misiones rechazadas o canceladas
    - Valida conflictos de horas cuando se proporcionan
    
    **Parámetros:**
    - fecha_inicio: Fecha de inicio del rango
    - fecha_fin: Fecha de fin del rango  
    - hora_inicio: Hora de inicio (opcional, formato HH:MM)
    - hora_fin: Hora de fin (opcional, formato HH:MM)
    
    **Respuesta:**
    - tiene_viaticos_en_rango: true si hay conflictos, false si no hay conflictos
    - mensaje: Descripción del resultado
    - detalles: Información detallada de viáticos encontrados
    """
    try:
        personal_id = current_employee["personal_id"]
        
        # Validar que las fechas sean coherentes
        if request.fecha_inicio > request.fecha_fin:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="La fecha de inicio no puede ser posterior a la fecha de fin"
            )
        
        # Obtener el usuario_id del empleado
        usuario_id = get_usuario_for_employee(personal_id, db_financiero)
        
        # Construir la consulta optimizada para verificar viáticos en el rango
        # Primero obtener las misiones que se solapan (sin duplicados)
        base_query = """
            SELECT DISTINCT m.id_mision, m.fecha_salida, m.fecha_retorno, 
                   TIME(m.fecha_salida) as hora_salida, TIME(m.fecha_retorno) as hora_retorno
            FROM misiones m
            WHERE m.beneficiario_personal_id = :personal_id
            AND m.id_estado_flujo NOT IN (4, 5)  -- Excluir estados rechazados o cancelados
            AND (DATE(m.fecha_salida) <= :fecha_fin AND DATE(m.fecha_retorno) >= :fecha_inicio)
            ORDER BY m.fecha_salida DESC
        """
        
        params = {
            "personal_id": personal_id,
            "fecha_inicio": request.fecha_inicio,
            "fecha_fin": request.fecha_fin
        }
        
        result = db_financiero.execute(text(base_query), params)
        viaticos_existentes = result.fetchall()
        
        print(f"DEBUG: Rango solicitado: {request.fecha_inicio} a {request.fecha_fin}")
        print(f"DEBUG: Hora inicio recibida: '{request.hora_inicio}' (tipo: {type(request.hora_inicio)})")
        print(f"DEBUG: Hora fin recibida: '{request.hora_fin}' (tipo: {type(request.hora_fin)})")
        print(f"DEBUG: Viáticos encontrados en DB: {len(viaticos_existentes)}")
        
        # Inicializar variables
        detalles = []
        conflictos_detectados = []
        
        # LÓGICA CON VALIDACIÓN DE HORAS: Si se proporcionan horas, validar horas; si no, solo fechas
        if viaticos_existentes:
            print(f"DEBUG: Se encontraron {len(viaticos_existentes)} viáticos existentes")
            
            # Verificar si se proporcionaron horas válidas
            horas_proporcionadas = (request.hora_inicio and request.hora_inicio.strip() and 
                                  request.hora_fin and request.hora_fin.strip())
            print(f"DEBUG: ¿Se proporcionaron horas? {horas_proporcionadas}")
            
            for viatico in viaticos_existentes:
                print(f"DEBUG: Procesando viático {viatico.id_mision}")
                print(f"DEBUG: Viático existente: {viatico.fecha_salida} a {viatico.fecha_retorno}")
                print(f"DEBUG: Solicitud: {request.fecha_inicio} {request.hora_inicio or ''} a {request.fecha_fin} {request.hora_fin or ''}")
                
                # Extraer fechas para comparación
                fecha_salida_existente = viatico.fecha_salida.date() if viatico.fecha_salida else None
                fecha_retorno_existente = viatico.fecha_retorno.date() if viatico.fecha_retorno else None
                
                # Verificar si hay solapamiento de fechas
                fechas_se_solapan = not (request.fecha_fin < fecha_salida_existente or request.fecha_inicio > fecha_retorno_existente)
                print(f"DEBUG: ¿Hay solapamiento de fechas? {fechas_se_solapan}")
                
                hay_conflicto = False
                motivo_conflicto = ""
                
                if fechas_se_solapan:
                    if horas_proporcionadas:
                        # Si hay horas, validar solapamiento de horas
                        print(f"DEBUG: Validando solapamiento de horas...")
                        
                        from datetime import datetime, timedelta
                        
                        # Iterar día por día en el rango solicitado
                        fecha_actual = request.fecha_inicio
                        while fecha_actual <= request.fecha_fin:
                            # Verificar si este día está dentro del rango del viático existente
                            if fecha_salida_existente <= fecha_actual <= fecha_retorno_existente:
                                print(f"DEBUG: Verificando día {fecha_actual}")
                                
                                # Determinar las horas del viático existente para este día
                                if fecha_actual == fecha_salida_existente and fecha_actual == fecha_retorno_existente:
                                    # Mismo día de inicio y fin
                                    viatico_hora_inicio = viatico.fecha_salida.time()
                                    viatico_hora_fin = viatico.fecha_retorno.time()
                                elif fecha_actual == fecha_salida_existente:
                                    # Día de inicio del viático
                                    viatico_hora_inicio = viatico.fecha_salida.time()
                                    viatico_hora_fin = datetime.strptime('23:59', '%H:%M').time()
                                elif fecha_actual == fecha_retorno_existente:
                                    # Día de fin del viático
                                    viatico_hora_inicio = datetime.strptime('00:00', '%H:%M').time()
                                    viatico_hora_fin = viatico.fecha_retorno.time()
                                else:
                                    # Día intermedio - todo el día ocupado
                                    viatico_hora_inicio = datetime.strptime('00:00', '%H:%M').time()
                                    viatico_hora_fin = datetime.strptime('23:59', '%H:%M').time()
                                
                                # Determinar las horas de la solicitud para este día
                                if fecha_actual == request.fecha_inicio and fecha_actual == request.fecha_fin:
                                    # Mismo día de inicio y fin de solicitud
                                    solicitud_hora_inicio = datetime.strptime(request.hora_inicio, '%H:%M').time()
                                    solicitud_hora_fin = datetime.strptime(request.hora_fin, '%H:%M').time()
                                elif fecha_actual == request.fecha_inicio:
                                    # Día de inicio de solicitud
                                    solicitud_hora_inicio = datetime.strptime(request.hora_inicio, '%H:%M').time()
                                    solicitud_hora_fin = datetime.strptime('23:59', '%H:%M').time()
                                elif fecha_actual == request.fecha_fin:
                                    # Día de fin de solicitud
                                    solicitud_hora_inicio = datetime.strptime('00:00', '%H:%M').time()
                                    solicitud_hora_fin = datetime.strptime(request.hora_fin, '%H:%M').time()
                                else:
                                    # Día intermedio de solicitud
                                    solicitud_hora_inicio = datetime.strptime('00:00', '%H:%M').time()
                                    solicitud_hora_fin = datetime.strptime('23:59', '%H:%M').time()
                                
                                print(f"DEBUG: Día {fecha_actual} - Viático: {viatico_hora_inicio} a {viatico_hora_fin}")
                                print(f"DEBUG: Día {fecha_actual} - Solicitud: {solicitud_hora_inicio} a {solicitud_hora_fin}")
                                
                                # Verificar solapamiento de horas en este día
                                hay_solapamiento_horas = not (solicitud_hora_fin <= viatico_hora_inicio or solicitud_hora_inicio >= viatico_hora_fin)
                                print(f"DEBUG: ¿Solapamiento de horas en {fecha_actual}? {hay_solapamiento_horas}")
                                
                                if hay_solapamiento_horas:
                                    hay_conflicto = True
                                    motivo_conflicto = f"Solapamiento de horas detectado el {fecha_actual}"
                                    print(f"DEBUG: ¡CONFLICTO DE HORAS DETECTADO en {fecha_actual}!")
                                    break
                            
                            fecha_actual += timedelta(days=1)
                    else:
                        # Si NO hay horas, cualquier solapamiento de fechas es conflicto
                        hay_conflicto = True
                        motivo_conflicto = "Solapamiento de fechas detectado (sin horas específicas)"
                        print(f"DEBUG: ¡CONFLICTO DE FECHAS DETECTADO!")
                
                if hay_conflicto:
                    conflictos_detectados.append({
                        "id_mision": viatico.id_mision,
                        "fecha_salida": viatico.fecha_salida.isoformat() if viatico.fecha_salida else None,
                        "fecha_retorno": viatico.fecha_retorno.isoformat() if viatico.fecha_retorno else None,
                        "motivo": motivo_conflicto
                    })
                    print(f"DEBUG: ¡CONFLICTO FINAL DETECTADO! Misión {viatico.id_mision}: {motivo_conflicto}")
                else:
                    print(f"DEBUG: No hay conflicto con misión {viatico.id_mision}")
                
                # Agregar a detalles independientemente del conflicto
                detalles.append({
                    "id_mision": viatico.id_mision,
                    "fecha_salida": viatico.fecha_salida.isoformat() if viatico.fecha_salida else None,
                    "fecha_retorno": viatico.fecha_retorno.isoformat() if viatico.fecha_retorno else None,
                    "hora_salida": str(viatico.hora_salida) if viatico.hora_salida else None,
                    "hora_retorno": str(viatico.hora_retorno) if viatico.hora_retorno else None
                })
        
        # Determinar resultado final
        tiene_viaticos = len(conflictos_detectados) > 0
        
        if tiene_viaticos:
            mensaje = f"Ya tienes {len(conflictos_detectados)} viático(s) registrado(s) que se solapan con el rango solicitado ({request.fecha_inicio} a {request.fecha_fin})."
        else:
            mensaje = "No hay conflictos de viáticos en el rango de fechas solicitado."
        
        print(f"DEBUG: Resultado final - tiene_viaticos: {tiene_viaticos}")
        print(f"DEBUG: Conflictos detectados: {len(conflictos_detectados)}")
        
        return ViaticoValidationResponse(
            tiene_viaticos_en_rango=tiene_viaticos,
            mensaje=mensaje,
            detalles={
                "viaticos_existentes": detalles,
                "conflictos_detectados": conflictos_detectados
            }
        )
        
    except Exception as e:
        print(f"Error validando viáticos en rango: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error validando viáticos: {str(e)}"
        )

@router.post("/validate-viaticos-dia", summary="Validar viáticos en día específico")
async def validate_viaticos_dia(
    request: ViaticoDiaValidationRequest,
    db_financiero: Session = Depends(get_db_financiero),
    db_rrhh: Session = Depends(get_db_rrhh),
    current_employee: dict = Depends(get_current_employee)
):
    """
    Verificar si ya tiene desayuno, almuerzo, cena o hospedaje registrado para ese día específico.
    
    **Características:**
    - Verifica cada servicio por separado (desayuno, almuerzo, cena, hospedaje)
    - Excluye misiones rechazadas o canceladas
    - Proporciona detalles completos de los viáticos del día
    
    **Parámetros:**
    - fecha: Fecha específica a validar (formato YYYY-MM-DD)
    
    **Respuesta:**
    - tiene_desayuno: true si tiene desayuno registrado
    - tiene_almuerzo: true si tiene almuerzo registrado
    - tiene_cena: true si tiene cena registrada
    - tiene_hospedaje: true si tiene hospedaje registrado
    - mensaje: Descripción del resultado
    - detalles: Información detallada de viáticos del día
    """
    try:
        personal_id = current_employee["personal_id"]
        
        # Obtener el usuario_id del empleado
        usuario_id = get_usuario_for_employee(personal_id, db_financiero)
        
        # Consultar viáticos para el día específico (optimizada)
        query = """
            SELECT iv.fecha, iv.monto_desayuno, iv.monto_almuerzo, iv.monto_cena, iv.monto_hospedaje,
                   m.id_mision, m.numero_solicitud
            FROM items_viaticos iv
            INNER JOIN misiones m ON iv.id_mision = m.id_mision
            WHERE m.beneficiario_personal_id = :personal_id
            AND iv.fecha = :fecha
            AND m.id_estado_flujo NOT IN (4, 5)  -- Excluir estados rechazados o cancelados
            ORDER BY m.id_mision DESC
        """
        
        result = db_financiero.execute(text(query), {
            "personal_id": personal_id,
            "fecha": request.fecha
        })
        
        viaticos_dia = result.fetchall()
        
        # Inicializar variables
        tiene_desayuno = False
        tiene_almuerzo = False
        tiene_cena = False
        tiene_hospedaje = False
        detalles = []
        
        # Verificar cada viático del día
        for viatico in viaticos_dia:
            if viatico.monto_desayuno and viatico.monto_desayuno > 0:
                tiene_desayuno = True
            if viatico.monto_almuerzo and viatico.monto_almuerzo > 0:
                tiene_almuerzo = True
            if viatico.monto_cena and viatico.monto_cena > 0:
                tiene_cena = True
            if viatico.monto_hospedaje and viatico.monto_hospedaje > 0:
                tiene_hospedaje = True
            
            detalles.append({
                "id_mision": viatico.id_mision,
                "numero_solicitud": viatico.numero_solicitud,
                "fecha": viatico.fecha.isoformat(),
                "monto_desayuno": float(viatico.monto_desayuno) if viatico.monto_desayuno else 0,
                "monto_almuerzo": float(viatico.monto_almuerzo) if viatico.monto_almuerzo else 0,
                "monto_cena": float(viatico.monto_cena) if viatico.monto_cena else 0,
                "monto_hospedaje": float(viatico.monto_hospedaje) if viatico.monto_hospedaje else 0
            })
        
        # Construir mensaje
        servicios_registrados = []
        if tiene_desayuno:
            servicios_registrados.append("desayuno")
        if tiene_almuerzo:
            servicios_registrados.append("almuerzo")
        if tiene_cena:
            servicios_registrados.append("cena")
        if tiene_hospedaje:
            servicios_registrados.append("hospedaje")
        
        if servicios_registrados:
            mensaje = f"Ya tiene registrado: {', '.join(servicios_registrados)} para el {request.fecha}"
        else:
            mensaje = f"No tiene viáticos registrados para el {request.fecha}"
        
        return ViaticoDiaValidationResponse(
            tiene_desayuno=tiene_desayuno,
            tiene_almuerzo=tiene_almuerzo,
            tiene_cena=tiene_cena,
            tiene_hospedaje=tiene_hospedaje,
            mensaje=mensaje,
            detalles={
                "viaticos_dia": detalles,
                "servicios_registrados": servicios_registrados
            }
        )
        
    except Exception as e:
        print(f"Error validando viáticos por día: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error validando viáticos por día: {str(e)}"
        )


def get_jefe_inmediato_personal_id(beneficiary_personal_id: int, db_rrhh: Session) -> Optional[int]:
    """
    Obtiene el personal_id del jefe inmediato del beneficiario
    
    Args:
        beneficiary_personal_id: personal_id del beneficiario/solicitante
        db_rrhh: Sesión de la base de datos RRHH
        
    Returns:
        int: personal_id del jefe inmediato o None si no se encuentra
    """
    try:
        # Obtener el departamento del empleado
        dept_query = text("""
            SELECT IdDepartamento 
            FROM nompersonal 
            WHERE personal_id = :personal_id
        """)
        
        dept_result = db_rrhh.execute(dept_query, {"personal_id": beneficiary_personal_id})
        dept_row = dept_result.fetchone()
        
        if not dept_row or not dept_row[0]:
            print(f"No se encontró departamento para personal_id {beneficiary_personal_id}")
            return None
        
        departamento_id = dept_row[0]
        print(f"Departamento encontrado: {departamento_id}")
        
        # Obtener el jefe inmediato del departamento (orden_aprobador = 1)
        jefe_query = text("""
            SELECT np.personal_id, np.apenom
            FROM nompersonal np
            JOIN departamento_aprobadores_maestros dam ON dam.cedula_aprobador = np.cedula
            WHERE dam.id_departamento = :departamento_id
              AND dam.orden_aprobador = 1
              AND np.estado != 'De Baja'
        """)
        
        jefe_result = db_rrhh.execute(jefe_query, {"departamento_id": departamento_id})
        jefe_row = jefe_result.fetchone()
        
        if jefe_row and jefe_row[0]:
            print(f"Jefe inmediato encontrado: {jefe_row[1]} (personal_id: {jefe_row[0]})")
            return jefe_row[0]
        
        print(f"No se encontró jefe inmediato para departamento {departamento_id}")
        return None
        
    except Exception as e:
        print(f"Error obteniendo jefe inmediato: {str(e)}")
        return None


# --- Endpoint para adjuntar archivos ---

@router.post("/{mission_id}/attachments", summary="Subir archivos adjuntos a una solicitud")
async def upload_attachments_employee(
    mission_id: int,
    files: List[UploadFile] = File(..., description="Lista de archivos a subir (máximo 10 en total por solicitud)"),
    tipo_documento: TipoDocumento = Query(TipoDocumento.OTRO),
    db_financiero: Session = Depends(get_db_financiero),
    db_rrhh: Session = Depends(get_db_rrhh),
    current_employee: dict = Depends(get_current_employee)
):
    """
    Sube uno o varios archivos y los asocia a una solicitud existente del empleado.
    
    **Restricciones:**
    - Máximo 10 archivos por solicitud (contando los existentes)
    - Cada archivo máximo 10MB
    - Solo el empleado que creó la solicitud puede adjuntar archivos
    - Tipos permitidos: pdf, doc, docx, xls, xlsx, png, jpg, jpeg
    """
    # Obtener personal_id del empleado
    cedula = current_employee.get("cedula")
    if not cedula:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No se pudo identificar la cédula del empleado"
        )
    
    personal_id = get_employee_personal_id(cedula, db_rrhh)
    
    # Verificar que la misión existe y pertenece al empleado
    mission = db_financiero.query(MisionModel).filter(
        MisionModel.id_mision == mission_id
    ).first()
    
    if not mission:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Solicitud no encontrada")
    
    # Verificar que el empleado es el beneficiario/creador de la solicitud
    if mission.beneficiario_personal_id != personal_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Solo el empleado que creó la solicitud puede adjuntar archivos."
        )
    
    # Contar archivos existentes
    archivos_existentes = db_financiero.query(Adjunto).filter(
        Adjunto.id_mision == mission_id
    ).count()
    
    # Validar que no se exceda el límite de 10 archivos
    if archivos_existentes >= 10:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"La solicitud ya tiene el máximo de 10 archivos permitidos."
        )
    
    if archivos_existentes + len(files) > 10:
        archivos_disponibles = 10 - archivos_existentes
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Solo puede subir {archivos_disponibles} archivo(s) más. La solicitud ya tiene {archivos_existentes} archivo(s)."
        )
    
    if not files:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Debe proporcionar al menos un archivo."
        )
    
    uploaded_attachments = []
    
    for file in files:
        # Validar que el archivo tenga nombre
        if not file.filename:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Uno de los archivos no tiene nombre válido."
            )
        
        # Validar extensión
        file_extension = os.path.splitext(file.filename)[1].lower()
        if file_extension not in ALLOWED_EXTENSIONS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Tipo de archivo no permitido: {file.filename}. Extensiones permitidas: {', '.join(ALLOWED_EXTENSIONS)}"
            )
        
        # Leer contenido
        contents = await file.read()
        
        # Validar tamaño
        if len(contents) > MAX_FILE_SIZE:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Archivo demasiado grande: {file.filename}. Tamaño máximo: 10MB."
            )
        
        # Generar nombre único y guardar
        unique_filename = f"{mission_id}_{uuid.uuid4()}{file_extension}"
        file_path = os.path.join(UPLOAD_DIR, unique_filename)
        
        with open(file_path, "wb") as buffer:
            buffer.write(contents)
        
        # Obtener usuario para auditoría
        id_usuario = get_usuario_for_employee(personal_id, db_financiero)
        
        # Crear registro en base de datos
        attachment = Adjunto(
            id_mision=mission_id,
            nombre_archivo=unique_filename,
            nombre_original=file.filename,
            url_almacenamiento=f"/uploads/missions/{unique_filename}",
            tipo_mime=file.content_type or "application/octet-stream",
            tamano_bytes=len(contents),
            tipo_documento=tipo_documento,
            id_usuario_subio=id_usuario
        )
        db_financiero.add(attachment)
        uploaded_attachments.append({
            "id_adjunto": attachment.id_adjunto,
            "nombre_original": file.filename,
            "url": f"/uploads/missions/{unique_filename}",
            "tamano_bytes": len(contents)
        })
    
    db_financiero.commit()
    
    return {
        "success": True,
        "message": f"{len(uploaded_attachments)} archivo(s) subido(s) exitosamente.",
        "archivos_subidos": len(uploaded_attachments),
        "archivos_totales": archivos_existentes + len(uploaded_attachments),
        "adjuntos": uploaded_attachments
    }