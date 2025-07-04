# Sistema de Gestión de Viáticos y Misiones - AITSA Backend

Este es el backend para el Sistema de Gestión de Viáticos, Misiones Oficiales y otras solicitudes de los colaboradores del Aeropuerto Internacional de Tocumen, S.A. (AITSA).

Está construido con FastAPI y se conecta a dos bases de datos:
1.  **`aitsa_financiero`**: Gestiona todo el flujo financiero de las misiones y viáticos.
2.  **`aitsa_rrhh`**: Contiene la información de los empleados y sus solicitudes generales.

---

## ✅ Checklist de Funcionalidades

### Módulo Financiero (Sistema Nuevo)

-   [x] Creación de Misiones a partir de Webhook de RRHH.
-   [x] Flujo de aprobación multi-etapa (Tesorería, Presupuesto, Contabilidad, Finanzas, CGR).
-   [x] Autenticación para personal del departamento financiero.
-   [x] Roles y permisos para el personal financiero.
-   [x] Registro de historial de cambios en las misiones (Pista de Auditoría).
-   [x] Capacidad de "subsanar" (devolver para corrección) solicitudes.
-   [ ] **(Pendiente)** Notificaciones automáticas por correo electrónico.
-   [ ] **(Pendiente)** Integración con firma electrónica calificada.

### Módulo de Empleados (Integración con `aitsa_rrhh`)

-   [x] **(Nuevo)** Login para empleados usando `cédula` y `usr_password` de la tabla `nompersonal`.
-   [x] **(Nuevo)** Validación de que el empleado no esté "De Baja".
-   [x] **(Nuevo)** Endpoint para que el empleado consulte sus propias solicitudes (`solicitudes_casos`).
-   [ ] **(Pendiente)** Endpoint para que el empleado cree nuevas solicitudes (actualmente se hacen en otro sistema).
-   [ ] **(Pendiente)** Endpoint para que los jefes aprueben/rechacen solicitudes directamente en este backend.

---

## 🚀 Configuración y Puesta en Marcha

Sigue estos pasos para configurar tu entorno de desarrollo.

### 1. Archivo de Entorno (`.env`)

Crea un archivo `.env` en la raíz del proyecto. **Este es un paso nuevo y crucial**, ya que ahora necesitamos las credenciales para ambas bases de datos.

```bash
# Credenciales para la Base de Datos Financiera (Sistema Nuevo)
DATABASE_URL="mysql+mysqlconnector://gestuser:gestpass@mysql:3306/aitsa_financiero"

# Credenciales para la Base de Datos de RRHH (Sistema Existente)
RRHH_DATABASE_URL="mysql+mysqlconnector://<usuario_rrhh>:<password_rrhh>@<host_rrhh>:3306/aitsa_rrhh"

# Clave secreta para los JWT (JSON Web Tokens)
SECRET_KEY="una-clave-muy-secreta-y-dificil-de-adivinar"

# Token para validar los Webhooks que vienen del sistema de RRHH
WEBHOOK_SECRET_TOKEN="un-token-secreto-para-el-webhook"

# Configuración General
ACCESS_TOKEN_EXPIRE_MINUTES=480 # 8 horas