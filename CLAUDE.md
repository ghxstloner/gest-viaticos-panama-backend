---

# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) and all developers working with this repository.

---

## Project Overview

This is a **FastAPI-based backend** for managing **travel expense requests (Viáticos) and Petty Cash (Caja Menuda)** for official missions at **Aeropuerto Internacional de Tocumen, S.A. (AITSA)**.

Key features include:

* Role-based, multi-stage approval workflows.
* Integration with a legacy HR database.
* Automatic per diem, lodging, transportation cost calculations based on configurable rates.
* Secure, auditable record of all approvals with electronic signatures.
* Excel and PDF report generation.
* Dual-database architecture (Financial and HR).

---

## System Architecture

### Databases

**1. `aitsa_financiero`** (Primary Financial DB)

* Core tables: `misiones`, `historial_flujo`, `transiciones_flujo`, `estados_flujo`, `items_viaticos`, `items_transporte`, `gestiones_cobro`, `firmas_electronicas`.
* Contains all financial workflows, audit logs, state transitions.
* Supports both Viáticos and Caja Menuda.

**2. `aitsa_rrhh`** (Legacy HR DB)

* Employee master data (e.g., name, position, ID).
* Read-only integration for authentication and beneficiary data.

---

### Environment Configuration

Required variables in `.env`:

```env
DATABASE_URL="mysql+mysqlconnector://root:root@localhost:3306/aitsa_financiero"
RRHH_DATABASE_URL="mysql+mysqlconnector://root:root@localhost:3306/aitsa_rrhh"
SECRET_KEY="very-secret-32-characters"
WEBHOOK_SECRET_TOKEN="replace-in-production"
ACCESS_TOKEN_EXPIRE_MINUTES=480
FRONTEND_URL=http://localhost:8080
ALLOWED_ORIGINS=["http://localhost:8080"]
```

---

## Detailed Workflow

The system implements a **sequential approval chain**. Here's how the process unfolds:

1. **Draft (BORRADOR)**

   * Created by a **Solicitante**.
   * Defines mission type (VIATICOS or CAJA\_MENUDA), beneficiary, objective, destination, dates.
   * Enters expense details:

     * Viáticos: per-day breakdown (items\_viaticos/items\_viaticos\_completos).
     * Transportation segments (items\_transporte).
     * International missions: region-specific (items\_misiones\_exterior).

2. **Submission (PENDIENTE\_JEFE)**

   * Submitted by Solicitante for review.
   * Moves to Jefe Inmediato.

3. **Manager Approval**

   * Jefe Inmediato can:

     * Approve → moves to PENDIENTE\_REVISION\_TESORERIA.
     * Return for correction (DEVUELTO\_CORRECCION).

4. **Treasury Review**

   * Analista Tesorería validates:

     * Approves → PENDIENTE\_ASIGNACION\_PRESUPUESTO (for Viáticos).
     * May create **gestion\_cobro** if required.

5. **Budget Assignment**

   * Analista Presupuesto allocates budget (mision\_partidas\_presupuestarias).
   * Moves to PENDIENTE\_CONTABILIDAD.

6. **Accounting Processing**

   * Analista Contabilidad posts entries.
   * Moves to PENDIENTE\_APROBACION\_FINANZAS.

7. **Finance Approval**

   * Director Finanzas gives final approval.
   * If amount exceeds `MONTO_REFRENDO_CGR`, moves to PENDIENTE\_REFRENDO\_CGR.
   * Otherwise, moves to APROBADO\_PARA\_PAGO.

8. **CGR Refrendo (if applicable)**

   * Fiscalizador CGR reviews high-value requests.
   * On approval → APROBADO\_PARA\_PAGO.

9. **Payment**

   * Tesorería or Custodio Caja Menuda executes payment.
   * Final state → PAGADO.

**At any step**, requests can be **rejected** or **returned for correction**.
All transitions are logged in `historial_flujo` with user, timestamp, and comments.
Electronic signatures (`firmas_electronicas`) ensure integrity and non-repudiation.

---

## Business Rules & Calculations

* **Per-diem rates** depend on `configuraciones_sistema`.
* Beneficiary category (`categoria_beneficiario`) influences rates:

  * TITULAR
  * OTROS SERVIDORES PÚBLICOS
  * OTRAS PERSONAS
* International missions apply regional **percentage increments**.
* Transport costs follow defined **tarifa** per km/type.
* **configuraciones\_sistema** stores all rates, limits, cut-off times for meals.
* CGR refrendo required if amount > `MONTO_REFRENDO_CGR`.

---

## Database Models

### Core Table: `misiones`

* Primary record of each request.
* Tracks:

  * Type: VIATICOS or CAJA\_MENUDA.
  * Beneficiary (HR link).
  * Dates, destination.
  * State via `id_estado_flujo`.
  * Financial amounts (calculated vs approved).
  * Flags for refrendo, payment.

### Supporting Tables

* `items_viaticos`, `items_viaticos_completos`: per-day breakdown.
* `items_transporte`: transport segments.
* `items_misiones_exterior`: international details.
* `gestiones_cobro`: treasury payment flows.
* `mision_partidas_presupuestarias`: budget assignments.
* `firmas_electronicas`: signed approvals.
* `historial_flujo`: complete audit trail.
* `adjuntos`: file uploads.

---

## Workflow Engine

### States (`estados_flujo`)

* BORRADOR
* PENDIENTE\_JEFE
* PENDIENTE\_REVISION\_TESORERIA
* PENDIENTE\_ASIGNACION\_PRESUPUESTO
* PENDIENTE\_CONTABILIDAD
* PENDIENTE\_APROBACION\_FINANZAS
* PENDIENTE\_REFRENDO\_CGR
* APROBADO\_PARA\_PAGO
* PAGADO
* DEVUELTO\_CORRECCION
* RECHAZADO
* CANCELADO
* PENDIENTE\_FIRMA\_ELECTRONICA
* ORDEN\_PAGO\_GENERADA

### Transitions (`transiciones_flujo`)

* Defined role-based matrix.
* Maps origin/destination states, authorized role, action (APPROVE/REJECT/RETURN/SUBSANAR).
* Enforced in service layer.

---

## Roles & Permissions

Example roles:

* Solicitante
* Jefe Inmediato
* Analista Tesorería
* Custodio Caja Menuda
* Analista Presupuesto
* Analista Contabilidad
* Director Finanzas
* Fiscalizador CGR
* Administrador Sistema

Permissions:

* Stored in `roles` table as JSON.
* Used to validate transitions and access.

---

## API Structure

All endpoints are under `/api/v1/`. Example modules:

* `/auth` - JWT authentication for financial staff.
* `/missions` - CRUD + workflow transitions.
* `/users` - User management.
* `/employee` - Employee-facing self-service.
* `/configuration` - System settings.
* `/reports` - Excel/PDF generation.
* `/dashboard` - Overview metrics.
* `/webhooks` - External integrations.

---

## Core Services

### Mission Service (`app/services/mission.py`)

* Handles mission creation, editing, state transitions.
* Validates roles against transitions.
* Calculates amounts based on category, region, transport.

### Employee Request Service (`app/services/employee_request_service.py`)

* Interfaces with `aitsa_rrhh`.
* Authenticates employees (ID, password).

### Configuration Service (`app/services/configuration.py`)

* Manages `configuraciones_sistema`.
* Defines limits, rates, cutoff times.

### Reports Service (`app/services/reports.py`)

* Generates Excel and PDF outputs.
* Mimics official forms like “Solicitud y Pago de Viáticos y Transporte”.

---

## Exception Handling

Custom exceptions in `app/core/exceptions.py`:

* `BusinessException`
* `WorkflowException`
* `ValidationException`
* `PermissionException`
* `ConfigurationException`
* `MissionException`

Global handlers defined in `app/main.py`.

---

## File Upload System

* Uploads stored in:

  * `uploads/missions/`
  * `uploads/logos/`
* Managed asynchronously with `aiofiles`.
* Metadata in `adjuntos` table.

---

## Development Setup

### Running the App

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
docker-compose up
```

### Database Migrations

```bash
alembic revision --autogenerate -m "description"
alembic upgrade head
alembic downgrade -1
```

### Dependencies

```bash
pip install -r requirements.txt
pip install package && pip freeze > requirements.txt
```

---

## Development Notes

* Use SQLAlchemy 2.0 with modern `Mapped` typing.
* All models inherit from `Base`.
* Timestamps via `TimestampMixin`.
* Dependency injection with:

  * `Depends(get_db_financiero)`
  * `Depends(get_db_rrhh)`
* Audit trail mandatory for all state changes.
* Never hard-code rates; always fetch from `configuraciones_sistema`.

---

## Testing Recommendations

* Test all workflow states and transitions.
* Validate calculations per `categoria_beneficiario`.
* Include international region increments.
* Ensure role-based permissions on transitions.
* Check signature validity in `firmas_electronicas`.
* Test edge cases: rejection, correction, cancellation.

---

