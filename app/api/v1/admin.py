# app/api/v1/admin.py

from typing import Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db_financiero
from app.api.deps import get_current_user
from app.models.user import Usuario
from app.services.workflow_validator import WorkflowValidator
from app.services.calculation_engine import CalculationEngine
from app.core.exceptions import PermissionException

router = APIRouter()


def require_admin_role(current_user: Usuario = Depends(get_current_user)):
    """Dependency to require admin role for sensitive operations"""
    if current_user.rol.nombre_rol != "Administrador Sistema":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acceso denegado. Se requiere rol de Administrador Sistema."
        )
    return current_user


@router.get("/system/health", tags=["Administration"])
async def system_health_check(
    db: Session = Depends(get_db_financiero),
    current_user: Usuario = Depends(require_admin_role)
) -> Dict[str, Any]:
    """
    Comprehensive system health check including database connectivity,
    workflow validation, and configuration verification.
    """
    
    health_status = {
        "status": "healthy",
        "timestamp": "2025-07-06T00:00:00Z",
        "checks": {},
        "issues": []
    }
    
    try:
        # Database connectivity check
        db.execute("SELECT 1").scalar()
        health_status["checks"]["database"] = {"status": "ok", "message": "Database connection successful"}
    except Exception as e:
        health_status["status"] = "unhealthy"
        health_status["checks"]["database"] = {"status": "error", "message": f"Database error: {str(e)}"}
        health_status["issues"].append("Database connectivity failed")
    
    try:
        # Workflow validation
        validator = WorkflowValidator(db)
        workflow_validation = validator.validate_complete_workflow()
        
        if workflow_validation["is_valid"]:
            health_status["checks"]["workflow"] = {"status": "ok", "message": "Workflow configuration is valid"}
        else:
            health_status["status"] = "degraded"
            health_status["checks"]["workflow"] = {
                "status": "warning", 
                "message": f"Workflow issues: {len(workflow_validation['errors'])} errors, {len(workflow_validation['warnings'])} warnings"
            }
            health_status["issues"].extend(workflow_validation["errors"])
            
    except Exception as e:
        health_status["status"] = "unhealthy"
        health_status["checks"]["workflow"] = {"status": "error", "message": f"Workflow validation failed: {str(e)}"}
        health_status["issues"].append("Workflow validation failed")
    
    try:
        # Configuration validation
        calc_engine = CalculationEngine(db)
        calc_summary = calc_engine.get_calculation_summary()
        
        # Check for essential configurations
        essential_configs = ["rates", "limits", "meal_percentages"]
        missing_configs = [config for config in essential_configs if not calc_summary.get(config)]
        
        if missing_configs:
            health_status["status"] = "degraded"
            health_status["checks"]["configuration"] = {
                "status": "warning", 
                "message": f"Missing configurations: {', '.join(missing_configs)}"
            }
            health_status["issues"].append(f"Missing essential configurations: {', '.join(missing_configs)}")
        else:
            health_status["checks"]["configuration"] = {"status": "ok", "message": "All essential configurations present"}
            
    except Exception as e:
        health_status["status"] = "unhealthy"
        health_status["checks"]["configuration"] = {"status": "error", "message": f"Configuration check failed: {str(e)}"}
        health_status["issues"].append("Configuration validation failed")
    
    return health_status


@router.get("/workflow/validate", tags=["Administration"])
async def validate_workflow(
    db: Session = Depends(get_db_financiero),
    current_user: Usuario = Depends(require_admin_role)
) -> Dict[str, Any]:
    """
    Detailed workflow validation including states, transitions, and role coverage.
    """
    
    validator = WorkflowValidator(db)
    return validator.validate_complete_workflow()


@router.get("/workflow/summary", tags=["Administration"])
async def workflow_summary(
    db: Session = Depends(get_db_financiero),
    current_user: Usuario = Depends(require_admin_role)
) -> Dict[str, Any]:
    """
    Get a comprehensive summary of the current workflow configuration.
    """
    
    validator = WorkflowValidator(db)
    return validator.get_workflow_summary()


@router.get("/calculations/summary", tags=["Administration"])
async def calculation_summary(
    db: Session = Depends(get_db_financiero),
    current_user: Usuario = Depends(require_admin_role)
) -> Dict[str, Any]:
    """
    Get a summary of current calculation rates and business rules.
    """
    
    calc_engine = CalculationEngine(db)
    return calc_engine.get_calculation_summary()


@router.post("/workflow/fix-issues", tags=["Administration"])
async def fix_workflow_issues(
    db: Session = Depends(get_db_financiero),
    current_user: Usuario = Depends(require_admin_role)
) -> Dict[str, Any]:
    """
    Attempt to automatically fix common workflow configuration issues.
    """
    
    validator = WorkflowValidator(db)
    return validator.fix_common_issues()


@router.get("/system/stats", tags=["Administration"])
async def system_statistics(
    db: Session = Depends(get_db_financiero),
    current_user: Usuario = Depends(require_admin_role)
) -> Dict[str, Any]:
    """
    Get comprehensive system statistics and metrics.
    """
    
    try:
        # Mission statistics
        mission_stats = db.execute("""
            SELECT 
                COUNT(*) as total_missions,
                COUNT(CASE WHEN tipo_mision = 'VIATICOS' THEN 1 END) as viaticos_count,
                COUNT(CASE WHEN tipo_mision = 'CAJA_MENUDA' THEN 1 END) as caja_menuda_count,
                COALESCE(SUM(monto_total_calculado), 0) as total_amount
            FROM misiones
        """).fetchone()
        
        # State distribution
        state_distribution = db.execute("""
            SELECT 
                ef.nombre_estado,
                COUNT(m.id_mision) as count
            FROM estados_flujo ef
            LEFT JOIN misiones m ON ef.id_estado_flujo = m.id_estado_flujo
            GROUP BY ef.id_estado_flujo, ef.nombre_estado
            ORDER BY count DESC
        """).fetchall()
        
        # User statistics
        user_stats = db.execute("""
            SELECT 
                COUNT(*) as total_users,
                COUNT(CASE WHEN is_active = 1 THEN 1 END) as active_users,
                COUNT(DISTINCT id_rol) as unique_roles
            FROM usuarios
        """).fetchone()
        
        return {
            "mission_statistics": {
                "total_missions": mission_stats.total_missions,
                "viaticos_count": mission_stats.viaticos_count,
                "caja_menuda_count": mission_stats.caja_menuda_count,
                "total_amount": float(mission_stats.total_amount or 0)
            },
            "state_distribution": [
                {"state": row.nombre_estado, "count": row.count}
                for row in state_distribution
            ],
            "user_statistics": {
                "total_users": user_stats.total_users,
                "active_users": user_stats.active_users,
                "unique_roles": user_stats.unique_roles
            }
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving system statistics: {str(e)}"
        )


@router.get("/system/version", tags=["Administration"])
async def system_version() -> Dict[str, str]:
    """
    Get system version information.
    """
    
    return {
        "system_name": "AITSA Gestión de Viáticos",
        "version": "1.0.0",
        "api_version": "v1",
        "build_date": "2025-07-06",
        "environment": "production"
    }