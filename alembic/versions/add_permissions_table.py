"""add_permissions_table

Revision ID: add_permissions_table
Revises: bc964be15d45
Create Date: 2024-01-09 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'add_permissions_table'
down_revision = 'bc964be15d45'
branch_labels = None
depends_on = None

# Lista de permisos base del sistema
BASE_PERMISSIONS = [
    # Permisos de empleado (estáticos)
    ("dashboard.ver", "Ver Dashboard", "Permite ver el dashboard", "dashboard", "ver", True),
    ("misiones.ver_propias", "Ver Misiones Propias", "Permite ver las misiones propias", "misiones", "ver_propias", True),
    ("misiones.crear", "Crear Misiones", "Permite crear nuevas misiones", "misiones", "crear", True),
    
    # Permisos administrativos
    ("roles.ver", "Ver Roles", "Permite ver roles", "roles", "ver", False),
    ("roles.crear", "Crear Roles", "Permite crear roles", "roles", "crear", False),
    ("roles.editar", "Editar Roles", "Permite editar roles", "roles", "editar", False),
    ("roles.eliminar", "Eliminar Roles", "Permite eliminar roles", "roles", "eliminar", False),
    
    ("sistema.mantener", "Mantener Sistema", "Permite realizar mantenimiento del sistema", "sistema", "mantener", False),
    ("sistema.configurar", "Configurar Sistema", "Permite configurar el sistema", "sistema", "configurar", False),
    
    ("misiones.ver", "Ver Todas las Misiones", "Permite ver todas las misiones", "misiones", "ver", False),
    ("misiones.editar", "Editar Misiones", "Permite editar misiones", "misiones", "editar", False),
    ("misiones.aprobar", "Aprobar Misiones", "Permite aprobar misiones", "misiones", "aprobar", False),
    ("misiones.eliminar", "Eliminar Misiones", "Permite eliminar misiones", "misiones", "eliminar", False),
    ("misiones.rechazar", "Rechazar Misiones", "Permite rechazar misiones", "misiones", "rechazar", False),
    
    ("reportes.ver", "Ver Reportes", "Permite ver reportes", "reportes", "ver", False),
    ("reportes.exportar", "Exportar Reportes", "Permite exportar reportes", "reportes", "exportar", False),
    
    ("usuarios.ver", "Ver Usuarios", "Permite ver usuarios", "usuarios", "ver", False),
    ("usuarios.crear", "Crear Usuarios", "Permite crear usuarios", "usuarios", "crear", False),
    ("usuarios.editar", "Editar Usuarios", "Permite editar usuarios", "usuarios", "editar", False),
    ("usuarios.eliminar", "Eliminar Usuarios", "Permite eliminar usuarios", "usuarios", "eliminar", False),
    
    ("auditoria.ver", "Ver Auditoría", "Permite ver registros de auditoría", "auditoria", "ver", False),
    
    ("configuracion.ver", "Ver Configuración", "Permite ver configuración", "configuracion", "ver", False),
    ("configuracion.crear", "Crear Configuración", "Permite crear configuración", "configuracion", "crear", False),
    ("configuracion.editar", "Editar Configuración", "Permite editar configuración", "configuracion", "editar", False),
    ("configuracion.eliminar", "Eliminar Configuración", "Permite eliminar configuración", "configuracion", "eliminar", False),
]

def upgrade():
    # Crear tabla de permisos
    op.create_table(
        'permisos',
        sa.Column('id_permiso', sa.Integer(), nullable=False),
        sa.Column('codigo', sa.String(50), nullable=False),
        sa.Column('nombre', sa.String(100), nullable=False),
        sa.Column('descripcion', sa.String(255)),
        sa.Column('modulo', sa.String(50), nullable=False),
        sa.Column('accion', sa.String(50), nullable=False),
        sa.Column('es_permiso_empleado', sa.Boolean(), default=False),
        sa.PrimaryKeyConstraint('id_permiso'),
        sa.UniqueConstraint('codigo')
    )

    # Crear tabla de asociación rol_permiso
    op.create_table(
        'rol_permiso',
        sa.Column('id_rol', sa.Integer(), nullable=False),
        sa.Column('id_permiso', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['id_rol'], ['roles.id_rol']),
        sa.ForeignKeyConstraint(['id_permiso'], ['permisos.id_permiso']),
        sa.PrimaryKeyConstraint('id_rol', 'id_permiso')
    )

    # Agregar columnas a la tabla roles
    op.add_column('roles', sa.Column('es_rol_empleado', sa.Boolean(), nullable=False, server_default='false'))
    op.add_column('roles', sa.Column('esta_activo', sa.Boolean(), nullable=False, server_default='true'))

    # Insertar permisos base
    op.execute(
        sa.text(
            "INSERT INTO permisos (codigo, nombre, descripcion, modulo, accion, es_permiso_empleado) "
            "VALUES (:codigo, :nombre, :descripcion, :modulo, :accion, :es_permiso_empleado)"
        ),
        [
            {
                "codigo": codigo,
                "nombre": nombre,
                "descripcion": descripcion,
                "modulo": modulo,
                "accion": accion,
                "es_permiso_empleado": es_permiso_empleado
            }
            for codigo, nombre, descripcion, modulo, accion, es_permiso_empleado in BASE_PERMISSIONS
        ]
    )

    # Marcar el rol de empleado
    op.execute(
        "UPDATE roles SET es_rol_empleado = true WHERE nombre_rol = 'Empleado'"
    )

    # Migrar permisos existentes de permisos_json a la nueva estructura
    # Esto requiere un proceso más complejo que se debe hacer en código Python
    # Se implementará en una migración posterior o script separado

def downgrade():
    op.drop_table('rol_permiso')
    op.drop_table('permisos')
    op.drop_column('roles', 'es_rol_empleado')
    op.drop_column('roles', 'esta_activo') 