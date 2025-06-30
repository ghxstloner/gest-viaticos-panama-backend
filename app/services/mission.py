from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import text, and_, or_, func, extract, desc
from decimal import Decimal
from datetime import datetime, date, timedelta
from ..models.mission import (
    Mision, EstadoFlujo, HistorialFlujo, TransicionFlujo, 
    GestionCobro, Subsanacion, ItemViatico, ItemTransporte, Adjunto
)
from ..models.user import Usuario
from ..models.configuration import ConfiguracionSistema
from ..models.enums import TipoMision, TipoAccion, EstadoGestion, EstadoSubsanacion
from ..schemas.mission import (
    MisionCreate, MisionUpdate, MisionApprovalRequest, 
    MisionRejectionRequest, WebhookMisionAprobada, MisionDetail,
    MisionListResponse, SubsanacionResponse, GestionCobroCreate
)
from fastapi import HTTPException, status
from ..core.exceptions import (
    BusinessException, WorkflowException, ValidationException, 
    PermissionException, MissionException
)


class MissionService:
    def __init__(self, db: Session):
        self.db = db

    def create_mission(self, mission_data: MisionCreate, usuario_id: int) -> Mision:
        """Crear nueva misión aplicando reglas de negocio de SIRCEL"""
        
        # Validaciones de negocio
        self._validate_mission_dates(mission_data.fecha_salida, mission_data.fecha_retorno)
        
        if mission_data.tipo_mision == TipoMision.VIATICOS:
            self._validate_viaticos_timing(mission_data.fecha_salida)
        
        # Obtener estado inicial
        estado_inicial = self.db.query(EstadoFlujo).filter(
            EstadoFlujo.nombre_estado == "PENDIENTE_REVISION_TESORERIA"
        ).first()
        
        if not estado_inicial:
            raise BusinessException("No se encontró el estado inicial del flujo")
        
        # Crear misión
        mision = Mision(
            solicitud_caso_id_rrhh=self._generate_case_id(),
            tipo_mision=mission_data.tipo_mision,
            beneficiario_personal_id=mission_data.beneficiario_personal_id,
            objetivo_mision=mission_data.objetivo_mision,
            destino_mision=mission_data.destino_mision,
            fecha_salida=mission_data.fecha_salida,
            fecha_retorno=mission_data.fecha_retorno,
            monto_total_calculado=Decimal("0.00"),
            id_estado_flujo=estado_inicial.id_estado_flujo,
            requiere_refrendo_cgr=False,
            observaciones_especiales=mission_data.observaciones_especiales,
            fecha_limite_presentacion=mission_data.fecha_salida - timedelta(days=10)
        )
        
        self.db.add(mision)
        self.db.flush()
        
        # Crear ítems de viáticos
        total_viaticos = Decimal("0.00")
        if hasattr(mission_data, 'items_viaticos') and mission_data.items_viaticos:
            for item_data in mission_data.items_viaticos:
                item = ItemViatico(
                    id_mision=mision.id_mision,
                    fecha=item_data.fecha,
                    monto_desayuno=Decimal(str(item_data.monto_desayuno)),
                    monto_almuerzo=Decimal(str(item_data.monto_almuerzo)),
                    monto_cena=Decimal(str(item_data.monto_cena)),
                    monto_hospedaje=Decimal(str(item_data.monto_hospedaje)),
                    observaciones=item_data.observaciones
                )
                total_viaticos += (item.monto_desayuno + item.monto_almuerzo + 
                                 item.monto_cena + item.monto_hospedaje)
                self.db.add(item)
        
        # Crear ítems de transporte
        total_transporte = Decimal("0.00")
        if hasattr(mission_data, 'items_transporte') and mission_data.items_transporte:
            for item_data in mission_data.items_transporte:
                item = ItemTransporte(
                    id_mision=mision.id_mision,
                    fecha=item_data.fecha,
                    tipo=item_data.tipo,
                    origen=item_data.origen,
                    destino=item_data.destino,
                    monto=Decimal(str(item_data.monto)),
                    observaciones=item_data.observaciones
                )
                total_transporte += item.monto
                self.db.add(item)
        
        # Para CAJA_MENUDA, usar monto directo
        if mission_data.tipo_mision == TipoMision.CAJA_MENUDA:
            mision.monto_total_calculado = Decimal(str(mission_data.monto_solicitado))
        else:
            mision.monto_total_calculado = total_viaticos + total_transporte
        
        # Determinar si requiere refrendo CGR
        config_monto_cgr = self._get_config_value("MONTO_REFRENDO_CGR", "1000.00")
        mision.requiere_refrendo_cgr = mision.monto_total_calculado >= Decimal(config_monto_cgr)
        
        # Crear registro en historial
        historial = HistorialFlujo(
            id_mision=mision.id_mision,
            id_usuario_accion=usuario_id,
            id_estado_anterior=None,
            id_estado_nuevo=estado_inicial.id_estado_flujo,
            tipo_accion=TipoAccion.CREAR,
            comentarios="Solicitud creada",
            ip_usuario="0.0.0.0"  # TODO: Obtener IP real
        )
        self.db.add(historial)
        
        self.db.commit()
        self.db.refresh(mision)
        
        return mision
    
    def get_missions(self, user: Usuario, **filters) -> Dict[str, Any]:
        """Obtener misiones según rol del usuario"""
        
        query = self.db.query(Mision).options(
            joinedload(Mision.estado_flujo),
            joinedload(Mision.items_viaticos),
            joinedload(Mision.items_transporte)
        )
        
        # Filtrar según rol
        if user.id_rol == 1:  # Solicitante
            query = query.filter(Mision.beneficiario_personal_id == user.personal_id_rrhh)
        elif user.id_rol in [2, 3, 4, 5, 6, 7, 8]:  # Staff financiero
            # Pueden ver todas las solicitudes en su área de responsabilidad
            pass
        elif user.id_rol == 9:  # Admin
            # Pueden ver todas
            pass
        
        # Aplicar filtros adicionales
        if filters.get('estado_id'):
            query = query.filter(Mision.id_estado_flujo == filters['estado_id'])
        
        if filters.get('tipo_mision'):
            query = query.filter(Mision.tipo_mision == filters['tipo_mision'])
        
        if filters.get('fecha_desde'):
            query = query.filter(Mision.fecha_salida >= filters['fecha_desde'])
        
        if filters.get('fecha_hasta'):
            query = query.filter(Mision.fecha_retorno <= filters['fecha_hasta'])
        
        # Paginación
        skip = filters.get('skip', 0)
        limit = filters.get('limit', 100)
        
        total = query.count()
        items = query.order_by(desc(Mision.created_at)).offset(skip).limit(limit).all()
        
        return {
            "items": items,
            "total": total,
            "page": (skip // limit) + 1,
            "size": limit,
            "pages": (total + limit - 1) // limit
        }
    
    def process_workflow_action(self, mission_id: int, user: Usuario, action: str, 
                              comentarios: str = None) -> Mision:
        """Procesar acción del flujo de trabajo"""
        
        mision = self.db.query(Mision).options(
            joinedload(Mision.estado_flujo)
        ).filter(Mision.id_mision == mission_id).first()
        
        if not mision:
            raise BusinessException("Misión no encontrada")
        
        # Validar que el usuario puede realizar esta acción
        self._validate_workflow_permission(mision, user, action)
        
        # Determinar nuevo estado según el flujo
        nuevo_estado = self._determine_next_state(mision, action, user.id_rol)
        
        if not nuevo_estado:
            raise BusinessException("Acción no válida para el estado actual")
        
        # Actualizar estado
        estado_anterior = mision.id_estado_flujo
        mision.id_estado_flujo = nuevo_estado.id_estado_flujo
        
        # Generar gestión de cobro si es necesario
        if (nuevo_estado.nombre_estado == "PENDIENTE_ASIGNACION_PRESUPUESTO" and
            user.id_rol == 3):  # Tesorería
            self._generate_gestion_cobro(mision, user.id_usuario)
        
        # Crear registro en historial
        historial = HistorialFlujo(
            id_mision=mision.id_mision,
            id_usuario_accion=user.id_usuario,
            id_estado_anterior=estado_anterior,
            id_estado_nuevo=nuevo_estado.id_estado_flujo,
            tipo_accion=TipoAccion(action.upper()),
            comentarios=comentarios,
            ip_usuario="0.0.0.0"
        )
        self.db.add(historial)
        
        self.db.commit()
        self.db.refresh(mision)
        
        return mision
    
    def calculate_viaticos(self, fecha_salida: date, fecha_retorno: date, destino: str) -> Dict[str, Any]:
        """Calcular montos de viáticos según tarifas oficiales"""
        
        # Tarifas base según destino
        tarifas = self._get_tarifas_by_destino(destino)
        
        # Calcular días
        dias = (fecha_retorno - fecha_salida).days + 1
        
        # Generar desglose por día
        desglose = []
        fecha_actual = fecha_salida
        total = Decimal("0.00")
        
        for i in range(dias):
            es_ultimo_dia = (i == dias - 1)
            
            dia_viatico = {
                "fecha": fecha_actual.isoformat(),
                "monto_desayuno": tarifas["desayuno"],
                "monto_almuerzo": tarifas["almuerzo"], 
                "monto_cena": tarifas["cena"],
                "monto_hospedaje": Decimal("0.00") if es_ultimo_dia else tarifas["hospedaje"]
            }
            
            total_dia = (dia_viatico["monto_desayuno"] + dia_viatico["monto_almuerzo"] + 
                        dia_viatico["monto_cena"] + dia_viatico["monto_hospedaje"])
            
            dia_viatico["total_dia"] = total_dia
            total += total_dia
            
            desglose.append(dia_viatico)
            fecha_actual += timedelta(days=1)
        
        return {
            "monto_total": float(total),
            "dias": dias,
            "desglose": desglose,
            "tarifas_aplicadas": tarifas
        }
    
    def _validate_mission_dates(self, fecha_salida: datetime, fecha_retorno: datetime):
        """Validar fechas de la misión"""
        if fecha_retorno < fecha_salida:
            raise BusinessException("La fecha de retorno no puede ser anterior a la fecha de salida")
        
        if fecha_salida.date() < date.today():
            raise BusinessException("La fecha de salida no puede ser en el pasado")
    
    def _validate_viaticos_timing(self, fecha_salida: datetime):
        """Validar que los viáticos se soliciten con anticipación"""
        dias_limite = int(self._get_config_value("DIAS_LIMITE_PRESENTACION", "10"))
        fecha_limite = date.today() + timedelta(days=dias_limite)
        
        if fecha_salida.date() < fecha_limite:
            raise BusinessException(f"Los viáticos deben solicitarse al menos {dias_limite} días antes")
    
    def _generate_case_id(self) -> int:
        """Generar ID único para el caso en RRHH"""
        return int(datetime.now().timestamp() * 1000) % 999999999
    
    def _get_config_value(self, clave: str, default: str) -> str:
        """Obtener valor de configuración"""
        # TODO: Implementar consulta a configuraciones_sistema
        config_values = {
            "MONTO_REFRENDO_CGR": "1000.00",
            "DIAS_LIMITE_PRESENTACION": "10",
            "LIMITE_EFECTIVO_VIATICOS": "200.00"
        }
        return config_values.get(clave, default)
    
    def _validate_workflow_permission(self, mision: Mision, user: Usuario, action: str):
        """Validar que el usuario puede realizar la acción"""
        estado_actual = mision.estado_flujo.nombre_estado
        rol = user.id_rol
        
        # Matriz de permisos por estado y rol
        permisos = {
            "PENDIENTE_REVISION_TESORERIA": [3],  # Solo tesorería
            "PENDIENTE_ASIGNACION_PRESUPUESTO": [5],  # Solo presupuesto
            "PENDIENTE_CONTABILIDAD": [6],  # Solo contabilidad
            "PENDIENTE_APROBACION_FINANZAS": [7],  # Solo director finanzas
            "PENDIENTE_REFRENDO_CGR": [8],  # Solo CGR
            "APROBADO_PARA_PAGO": [3, 4],  # Tesorería o caja menuda
        }
        
        if estado_actual in permisos and rol not in permisos[estado_actual]:
            raise BusinessException("No tiene permisos para realizar esta acción")
    
    def _determine_next_state(self, mision: Mision, action: str, rol_id: int) -> Optional[EstadoFlujo]:
        """Determinar siguiente estado según la acción y el rol"""
        estado_actual = mision.estado_flujo.nombre_estado
        
        # Matriz de transiciones
        transiciones = {
            "PENDIENTE_REVISION_TESORERIA": {
                "APROBAR": {
                    TipoMision.VIATICOS: "PENDIENTE_ASIGNACION_PRESUPUESTO",
                    TipoMision.CAJA_MENUDA: "APROBADO_PARA_PAGO"
                },
                "RECHAZAR": "RECHAZADO",
                "DEVOLVER": "DEVUELTO_CORRECCION"
            },
            "PENDIENTE_ASIGNACION_PRESUPUESTO": {
                "APROBAR": "PENDIENTE_CONTABILIDAD",
                "RECHAZAR": "RECHAZADO",
                "DEVOLVER": "DEVUELTO_CORRECCION"
            },
            "PENDIENTE_CONTABILIDAD": {
                "APROBAR": "PENDIENTE_APROBACION_FINANZAS",
                "RECHAZAR": "RECHAZADO",
                "DEVOLVER": "DEVUELTO_CORRECCION"
            },
            "PENDIENTE_APROBACION_FINANZAS": {
                "APROBAR": "PENDIENTE_REFRENDO_CGR" if mision.requiere_refrendo_cgr else "APROBADO_PARA_PAGO",
                "RECHAZAR": "RECHAZADO",
                "DEVOLVER": "DEVUELTO_CORRECCION"
            },
            "PENDIENTE_REFRENDO_CGR": {
                "APROBAR": "APROBADO_PARA_PAGO",
                "RECHAZAR": "RECHAZADO",
                "SUBSANAR": "DEVUELTO_CORRECCION"
            },
            "APROBADO_PARA_PAGO": {
                "PAGAR": "PAGADO"
            }
        }
        
        if estado_actual not in transiciones:
            return None
        
        if action not in transiciones[estado_actual]:
            return None
        
        siguiente = transiciones[estado_actual][action]
        
        # Para viáticos, usar el resultado según tipo
        if isinstance(siguiente, dict):
            siguiente = siguiente.get(mision.tipo_mision)
        
        return self.db.query(EstadoFlujo).filter(
            EstadoFlujo.nombre_estado == siguiente
        ).first()
    
    def _generate_gestion_cobro(self, mision: Mision, usuario_id: int):
        """Generar gestión de cobro para viáticos"""
        numero_gestion = f"GC-{mision.id_mision:06d}-{datetime.now().year}"
        
        gestion = GestionCobro(
            id_mision=mision.id_mision,
            numero_gestion=numero_gestion,
            id_usuario_genero=usuario_id,
            monto_autorizado=mision.monto_total_calculado,
            observaciones=f"Gestión generada automáticamente para misión {mision.id_mision}",
            estado=EstadoGestion.PENDIENTE
        )
        
        self.db.add(gestion)
        mision.numero_gestion_cobro = numero_gestion
    
    def _get_tarifas_by_destino(self, destino: str) -> Dict[str, Decimal]:
        """Obtener tarifas oficiales según destino"""
        # Tarifas base para Panamá
        if "panamá" in destino.lower() or "panama" in destino.lower():
            return {
                "desayuno": Decimal("15.00"),
                "almuerzo": Decimal("20.00"),
                "cena": Decimal("25.00"),
                "hospedaje": Decimal("80.00")
            }
        # Tarifas internacionales
        else:
            return {
                "desayuno": Decimal("25.00"),
                "almuerzo": Decimal("35.00"),
                "cena": Decimal("40.00"),
                "hospedaje": Decimal("120.00")
            }

