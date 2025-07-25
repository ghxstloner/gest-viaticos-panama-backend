# Sistema de Gestión de Viáticos y Misiones - AITSA Backend

Este es el backend para el Sistema de Gestión de Viáticos, Misiones Oficiales y otras solicitudes de los colaboradores del Aeropuerto Internacional de Tocumen, S.A. (AITSA).

Está construido con FastAPI y se conecta a dos bases de datos:
1.  **`aitsa_financiero`**: Gestiona todo el flujo financiero de las misiones y viáticos.
2.  **`aitsa_rrhh`**: Contiene la información de los empleados y sus solicitudes generales.

---

## 🚀 Configuración y Puesta en Marcha

Sigue estos pasos para configurar tu entorno de desarrollo.

### 1. Archivo de Entorno (`.env`)

Crea un archivo `.env` en la raíz del proyecto. **Este es un paso nuevo y crucial**, ya que ahora necesitamos las credenciales para ambas bases de datos.

Recordar lo siguiente:

Para windows se activa de esta forma el venv:

.\venv\Scripts\activate
.\venv\Scripts\Activate.ps1
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload



