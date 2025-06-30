# app/utils/init_db.py

from sqlalchemy.orm import Session
from app.core.database import engine_financiero
from app.models.base import Base
from app.models.user import Rol, Usuario
from app.models.mission import EstadoFlujo, TransicionFlujo
from app.models.enums import TipoFlujo, TipoAccion
from passlib.context import CryptContext
import json

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def create_tables():
    """Crear todas las tablas en la base de datos"""
    Base.metadata.create_all(bind=engine_financiero)
    print("✅ Tablas creadas exitosamente")

def init_roles(db: Session):
    """Crear roles básicos del sistema SIRCEL"""
    
    roles_data = [
        {
            "id_rol": 1,
            "nombre_rol": "Solicitante",
            "descripcion": "Empleado que solicita viáticos",
            "permisos_json": {
                "solicitudes": {"crear": True, "ver": True, "editar": True, "eliminar": True},
                "informes": {"crear": True, "ver": True, "presentar": True},
                "perfil": {"ver": True, "editar": True}
            }
        },
        {
            "id_rol": 2,
            "nombre_rol": "Jefe Inmediato",
            "descripcion": "Supervisor que aprueba solicitudes",
            "permisos_json": {
                "aprobaciones": {"ver": True, "aprobar": True, "rechazar": True, "devolver": True},
                "solicitudes": {"ver": True, "comentar": True}
            }
        },
        {
            "id_rol": 3,
            "nombre_rol": "Analista Tesorería",
            "descripcion": "Personal de tesorería que gestiona pagos",
            "permisos_json": {
                "gestion_solicitudes": {"ver": True, "procesar": True},
                "gestion_pagos": {"ver": True, "generar_cobro": True, "pagar": True},
                "gestiones_cobro": {"crear": True, "ver": True, "editar": True}
            }
        },
        {
            "id_rol": 4,
            "nombre_rol": "Analista Presupuesto",
            "descripcion": "Personal que asigna partidas presupuestarias",
            "permisos_json": {
                "procesos_contables": {"ver": True, "asignar_partida": True},
                "presupuesto": {"ver": True, "validar": True, "aprobar": True}
            }
        },
        {
            "id_rol": 5,
            "nombre_rol": "Analista Contabilidad",
            "descripcion": "Personal que registra asientos contables",
            "permisos_json": {
                "procesos_contables": {"ver": True, "registro_contable": True},
                "contabilidad": {"ver": True, "registrar": True, "aprobar": True}
            }
        },
        {
            "id_rol": 6,
            "nombre_rol": "Custodio Caja Menuda",
            "descripcion": "Responsable de pagos en efectivo",
            "permisos_json": {
                "gestion_pagos": {"ver": True, "pago_efectivo": True},
                "caja_menuda": {"ver": True, "gestionar": True, "reintegros": True}
            }
        },
        {
            "id_rol": 7,
            "nombre_rol": "Director Finanzas",
            "descripcion": "Director que autoriza con firma electrónica",
            "permisos_json": {
                "gestion_solicitudes": {"ver": True, "aprobar": True},
                "firma_electronica": {"autorizar": True},
                "reportes": {"ver": True, "exportar": True, "avanzados": True}
            }
        },
        {
            "id_rol": 8,
            "nombre_rol": "Fiscalizador CGR",
            "descripcion": "Fiscalizador de Contraloría para refrendo",
            "permisos_json": {
                "fiscalizacion": {"ver": True, "refrendar": True, "subsanar": True},
                "refrendo": {"aprobar": True, "rechazar": True},
                "auditoria": {"ver": True, "completa": True}
            }
        },
        {
            "id_rol": 9,
            "nombre_rol": "Administrador Sistema",
            "descripcion": "Administrador con acceso completo",
            "permisos_json": {
                "administracion": {"ver": True, "usuarios": True, "roles": True, "configuracion": True},
                "sistema": {"configurar": True, "mantener": True, "backup": True},
                "reportes": {"ver": True, "exportar": True, "todos": True}
            }
        }
    ]
    
    for role_data in roles_data:
        existing_role = db.query(Rol).filter(Rol.nombre_rol == role_data["nombre_rol"]).first()
        if not existing_role:
            role = Rol(**role_data)
            db.add(role)
    
    db.commit()
    print("✅ Roles creados exitosamente")

def init_estados_flujo(db: Session):
    """Crear estados del flujo de trabajo SIRCEL"""
    
    estados_data = [
        # Estados iniciales
        {"id_estado_flujo": 1, "nombre_estado": "BORRADOR", "descripcion": "Solicitud en preparación", "es_estado_final": False, "requiere_comentario": False, "orden_flujo": 1, "tipo_flujo": TipoFlujo.AMBOS},
        {"id_estado_flujo": 2, "nombre_estado": "PENDIENTE_JEFE", "descripcion": "Esperando aprobación del jefe inmediato", "es_estado_final": False, "requiere_comentario": False, "orden_flujo": 2, "tipo_flujo": TipoFlujo.AMBOS},
        
        # Estados específicos de VIATICOS (Flujo largo)
        {"id_estado_flujo": 3, "nombre_estado": "PENDIENTE_TESORERIA", "descripcion": "En revisión por Tesorería", "es_estado_final": False, "requiere_comentario": False, "orden_flujo": 3, "tipo_flujo": TipoFlujo.VIATICOS},
        {"id_estado_flujo": 4, "nombre_estado": "PENDIENTE_PRESUPUESTO", "descripcion": "Esperando asignación de partida presupuestaria", "es_estado_final": False, "requiere_comentario": False, "orden_flujo": 4, "tipo_flujo": TipoFlujo.VIATICOS},
        {"id_estado_flujo": 5, "nombre_estado": "PENDIENTE_CONTABILIDAD", "descripcion": "Esperando registro contable", "es_estado_final": False, "requiere_comentario": False, "orden_flujo": 5, "tipo_flujo": TipoFlujo.VIATICOS},
        {"id_estado_flujo": 6, "nombre_estado": "PENDIENTE_DIRECTOR_FINANZAS", "descripcion": "Esperando firma del Director de Finanzas", "es_estado_final": False, "requiere_comentario": False, "orden_flujo": 6, "tipo_flujo": TipoFlujo.VIATICOS},
        {"id_estado_flujo": 7, "nombre_estado": "PENDIENTE_REFRENDO_CGR", "descripcion": "Esperando refrendo de Contraloría", "es_estado_final": False, "requiere_comentario": False, "orden_flujo": 7, "tipo_flujo": TipoFlujo.VIATICOS},
        
        # Estados específicos de CAJA_MENUDA (Flujo corto)
        {"id_estado_flujo": 8, "nombre_estado": "PENDIENTE_CUSTODIO", "descripcion": "Esperando pago por Custodio de Caja Menuda", "es_estado_final": False, "requiere_comentario": False, "orden_flujo": 3, "tipo_flujo": TipoFlujo.CAJA_MENUDA},
        
        # Estados finales
        {"id_estado_flujo": 9, "nombre_estado": "APROBADA", "descripcion": "Solicitud aprobada, lista para pago", "es_estado_final": False, "requiere_comentario": False, "orden_flujo": 8, "tipo_flujo": TipoFlujo.AMBOS},
        {"id_estado_flujo": 10, "nombre_estado": "PAGADA", "descripcion": "Pago realizado", "es_estado_final": True, "requiere_comentario": False, "orden_flujo": 9, "tipo_flujo": TipoFlujo.AMBOS},
        {"id_estado_flujo": 11, "nombre_estado": "COMPLETADA", "descripcion": "Misión completada con informe presentado", "es_estado_final": True, "requiere_comentario": False, "orden_flujo": 10, "tipo_flujo": TipoFlujo.AMBOS},
        
        # Estados de rechazo/devolución
        {"id_estado_flujo": 12, "nombre_estado": "RECHAZADA", "descripcion": "Solicitud rechazada", "es_estado_final": True, "requiere_comentario": True, "orden_flujo": None, "tipo_flujo": TipoFlujo.AMBOS},
        {"id_estado_flujo": 13, "nombre_estado": "DEVUELTA_SUBSANACION", "descripcion": "Devuelta para subsanación", "es_estado_final": False, "requiere_comentario": True, "orden_flujo": None, "tipo_flujo": TipoFlujo.AMBOS},
        {"id_estado_flujo": 14, "nombre_estado": "ANULADA", "descripcion": "Solicitud anulada", "es_estado_final": True, "requiere_comentario": True, "orden_flujo": None, "tipo_flujo": TipoFlujo.AMBOS},
    ]
    
    for estado_data in estados_data:
        existing_estado = db.query(EstadoFlujo).filter(EstadoFlujo.nombre_estado == estado_data["nombre_estado"]).first()
        if not existing_estado:
            estado = EstadoFlujo(**estado_data)
            db.add(estado)
    
    db.commit()
    print("✅ Estados de flujo creados exitosamente")

def init_transiciones_flujo(db: Session):
    """Crear matriz de transiciones válidas para el flujo SIRCEL"""
    
    # Transiciones válidas según los flujos de SIRCEL
    transiciones_data = [
        # FLUJO COMÚN: Solicitud inicial
        {"id_estado_origen": 1, "id_estado_destino": 2, "id_rol_autorizado": 1, "tipo_accion": TipoAccion.APROBAR},  # Solicitante envía borrador
        
        # FLUJO COMÚN: Jefe Inmediato
        {"id_estado_origen": 2, "id_estado_destino": 3, "id_rol_autorizado": 2, "tipo_accion": TipoAccion.APROBAR},  # Jefe aprueba a Tesorería (VIATICOS)
        {"id_estado_origen": 2, "id_estado_destino": 8, "id_rol_autorizado": 2, "tipo_accion": TipoAccion.APROBAR},  # Jefe aprueba a Custodio (CAJA_MENUDA)
        {"id_estado_origen": 2, "id_estado_destino": 12, "id_rol_autorizado": 2, "tipo_accion": TipoAccion.RECHAZAR}, # Jefe rechaza
        {"id_estado_origen": 2, "id_estado_destino": 13, "id_rol_autorizado": 2, "tipo_accion": TipoAccion.DEVOLVER}, # Jefe devuelve
        
        # FLUJO VIATICOS: Tesorería genera gestión de cobro
        {"id_estado_origen": 3, "id_estado_destino": 4, "id_rol_autorizado": 3, "tipo_accion": TipoAccion.APROBAR},  # Tesorería a Presupuesto
        {"id_estado_origen": 3, "id_estado_destino": 12, "id_rol_autorizado": 3, "tipo_accion": TipoAccion.RECHAZAR}, # Tesorería rechaza
        {"id_estado_origen": 3, "id_estado_destino": 13, "id_rol_autorizado": 3, "tipo_accion": TipoAccion.DEVOLVER}, # Tesorería devuelve
        
        # FLUJO VIATICOS: Presupuesto asigna partida
        {"id_estado_origen": 4, "id_estado_destino": 5, "id_rol_autorizado": 4, "tipo_accion": TipoAccion.APROBAR},  # Presupuesto a Contabilidad
        {"id_estado_origen": 4, "id_estado_destino": 12, "id_rol_autorizado": 4, "tipo_accion": TipoAccion.RECHAZAR}, # Presupuesto rechaza
        {"id_estado_origen": 4, "id_estado_destino": 13, "id_rol_autorizado": 4, "tipo_accion": TipoAccion.DEVOLVER}, # Presupuesto devuelve
        
        # FLUJO VIATICOS: Contabilidad registra asiento
        {"id_estado_origen": 5, "id_estado_destino": 6, "id_rol_autorizado": 5, "tipo_accion": TipoAccion.APROBAR},  # Contabilidad a Director
        {"id_estado_origen": 5, "id_estado_destino": 12, "id_rol_autorizado": 5, "tipo_accion": TipoAccion.RECHAZAR}, # Contabilidad rechaza
        {"id_estado_origen": 5, "id_estado_destino": 13, "id_rol_autorizado": 5, "tipo_accion": TipoAccion.DEVOLVER}, # Contabilidad devuelve
        
        # FLUJO VIATICOS: Director de Finanzas firma
        {"id_estado_origen": 6, "id_estado_destino": 7, "id_rol_autorizado": 7, "tipo_accion": TipoAccion.APROBAR},  # Director a CGR
        {"id_estado_origen": 6, "id_estado_destino": 12, "id_rol_autorizado": 7, "tipo_accion": TipoAccion.RECHAZAR}, # Director rechaza
        {"id_estado_origen": 6, "id_estado_destino": 13, "id_rol_autorizado": 7, "tipo_accion": TipoAccion.DEVOLVER}, # Director devuelve
        
        # FLUJO VIATICOS: CGR refrenda
        {"id_estado_origen": 7, "id_estado_destino": 9, "id_rol_autorizado": 8, "tipo_accion": TipoAccion.APROBAR},  # CGR aprueba
        {"id_estado_origen": 7, "id_estado_destino": 12, "id_rol_autorizado": 8, "tipo_accion": TipoAccion.RECHAZAR}, # CGR rechaza
        {"id_estado_origen": 7, "id_estado_destino": 13, "id_rol_autorizado": 8, "tipo_accion": TipoAccion.SUBSANAR}, # CGR subsana
        
        # FLUJO CAJA_MENUDA: Custodio paga directamente
        {"id_estado_origen": 8, "id_estado_destino": 10, "id_rol_autorizado": 6, "tipo_accion": TipoAccion.APROBAR},  # Custodio paga
        {"id_estado_origen": 8, "id_estado_destino": 12, "id_rol_autorizado": 6, "tipo_accion": TipoAccion.RECHAZAR}, # Custodio rechaza
        {"id_estado_origen": 8, "id_estado_destino": 13, "id_rol_autorizado": 6, "tipo_accion": TipoAccion.DEVOLVER}, # Custodio devuelve
        
        # FLUJO FINAL: Tesorería realiza pago por transferencia (VIATICOS)
        {"id_estado_origen": 9, "id_estado_destino": 10, "id_rol_autorizado": 3, "tipo_accion": TipoAccion.APROBAR},  # Tesorería paga
        
        # FLUJO FINAL: Presentación de informe
        {"id_estado_origen": 10, "id_estado_destino": 11, "id_rol_autorizado": 1, "tipo_accion": TipoAccion.APROBAR}, # Solicitante presenta informe
        
        # SUBSANACIONES: Regreso después de corrección
        {"id_estado_origen": 13, "id_estado_destino": 2, "id_rol_autorizado": 1, "tipo_accion": TipoAccion.APROBAR},  # Solicitante corrige y reenvía
    ]
    
    for transicion_data in transiciones_data:
        existing_transicion = db.query(TransicionFlujo).filter(
            TransicionFlujo.id_estado_origen == transicion_data["id_estado_origen"],
            TransicionFlujo.id_estado_destino == transicion_data["id_estado_destino"],
            TransicionFlujo.id_rol_autorizado == transicion_data["id_rol_autorizado"],
            TransicionFlujo.tipo_accion == transicion_data["tipo_accion"]
        ).first()
        
        if not existing_transicion:
            transicion = TransicionFlujo(**transicion_data)
            db.add(transicion)
    
    db.commit()
    print("✅ Transiciones de flujo creadas exitosamente")

def init_admin_user(db: Session):
    """Crear usuario administrador por defecto"""
    
    admin_user = db.query(Usuario).filter(Usuario.login_username == "admin").first()
    if not admin_user:
        hashed_password = pwd_context.hash("admin123")
        admin_user = Usuario(
            personal_id_rrhh=1,  # ID ficticio
            login_username="admin",
            password_hash=hashed_password,
            id_rol=9,  # Administrador Sistema
            is_active=True
        )
        db.add(admin_user)
        db.commit()
        print("✅ Usuario administrador creado: admin/admin123")
    else:
        print("ℹ️  Usuario administrador ya existe")

def main():
    """Ejecutar inicialización completa de la base de datos"""
    print("🚀 Iniciando configuración de base de datos SIRCEL...")
    
    # Crear tablas
    create_tables()
    
    # Crear datos iniciales
    with Session(engine_financiero) as db:
        init_roles(db)
        init_estados_flujo(db)
        init_transiciones_flujo(db)
        init_admin_user(db)
    
    print("✅ Inicialización de base de datos completada")
    print("\n📋 Credenciales por defecto:")
    print("   - Administrador: admin/admin123")
    print("\n🔄 Estados de flujo configurados:")
    print("   - VIATICOS: 10 pasos (incluye CGR)")
    print("   - CAJA_MENUDA: 4 pasos (flujo rápido)")
    print("\n👥 Roles configurados: 9 roles según SIRCEL")

if __name__ == "__main__":
    main() 