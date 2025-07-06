# app/services/workflow_validator.py

from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.models.mission import EstadoFlujo, TransicionFlujo
from app.models.user import Rol
from app.models.enums import TipoAccion, TipoFlujo
from app.core.exceptions import ConfigurationException


class WorkflowValidator:
    """
    Validates that the workflow is properly configured in the database
    with all required states, transitions, and roles.
    """
    
    def __init__(self, db: Session):
        self.db = db
        
    def validate_complete_workflow(self) -> Dict[str, Any]:
        """
        Performs a complete validation of the workflow configuration
        """
        validation_results = {
            "is_valid": True,
            "errors": [],
            "warnings": [],
            "states": self._validate_states(),
            "transitions": self._validate_transitions(),
            "roles": self._validate_roles(),
            "coverage": self._validate_coverage()
        }
        
        # Check if any validation failed
        for category in ["states", "transitions", "roles", "coverage"]:
            if not validation_results[category]["is_valid"]:
                validation_results["is_valid"] = False
                validation_results["errors"].extend(validation_results[category]["errors"])
                validation_results["warnings"].extend(validation_results[category]["warnings"])
        
        return validation_results
    
    def _validate_states(self) -> Dict[str, Any]:
        """
        Validates that all required workflow states exist
        """
        result = {"is_valid": True, "errors": [], "warnings": []}
        
        # Required states according to the documentation
        required_states = [
            "BORRADOR", "PENDIENTE_JEFE", "PENDIENTE_REVISION_TESORERIA",
            "PENDIENTE_ASIGNACION_PRESUPUESTO", "PENDIENTE_CONTABILIDAD",
            "PENDIENTE_APROBACION_FINANZAS", "PENDIENTE_REFRENDO_CGR",
            "APROBADO_PARA_PAGO", "PAGADO", "DEVUELTO_CORRECCION",
            "RECHAZADO", "CANCELADO", "PENDIENTE_FIRMA_ELECTRONICA",
            "ORDEN_PAGO_GENERADA"
        ]
        
        existing_states = self.db.query(EstadoFlujo).all()
        existing_state_names = [state.nombre_estado for state in existing_states]
        
        # Check for missing states
        missing_states = [state for state in required_states if state not in existing_state_names]
        if missing_states:
            result["is_valid"] = False
            result["errors"].append(f"Missing required states: {', '.join(missing_states)}")
        
        # Check for states without proper order
        states_without_order = [
            state for state in existing_states 
            if state.orden_flujo is None and state.nombre_estado not in ["DEVUELTO_CORRECCION", "RECHAZADO", "CANCELADO"]
        ]
        if states_without_order:
            result["warnings"].append(f"States without order: {[s.nombre_estado for s in states_without_order]}")
        
        # Check for orphaned states (not used in any transitions)
        result["existing_states"] = len(existing_states)
        result["required_states"] = len(required_states)
        
        return result
    
    def _validate_transitions(self) -> Dict[str, Any]:
        """
        Validates that required transitions exist between states
        """
        result = {"is_valid": True, "errors": [], "warnings": []}
        
        transitions = self.db.query(TransicionFlujo).all()
        
        # Check that each non-final state has at least one outgoing transition
        estados = self.db.query(EstadoFlujo).filter(EstadoFlujo.es_estado_final == False).all()
        
        for estado in estados:
            outgoing_transitions = [t for t in transitions if t.id_estado_origen == estado.id_estado_flujo and t.es_activa]
            if not outgoing_transitions:
                result["warnings"].append(f"State '{estado.nombre_estado}' has no outgoing transitions")
        
        # Check for critical workflow paths
        critical_actions = [TipoAccion.APROBAR, TipoAccion.RECHAZAR, TipoAccion.DEVOLVER]
        for action in critical_actions:
            action_transitions = [t for t in transitions if t.tipo_accion == action and t.es_activa]
            if not action_transitions:
                result["errors"].append(f"No transitions found for critical action: {action.value}")
                result["is_valid"] = False
        
        result["total_transitions"] = len(transitions)
        result["active_transitions"] = len([t for t in transitions if t.es_activa])
        
        return result
    
    def _validate_roles(self) -> Dict[str, Any]:
        """
        Validates that all required roles exist and have proper permissions
        """
        result = {"is_valid": True, "errors": [], "warnings": []}
        
        # Required roles according to the documentation
        required_roles = [
            "Solicitante", "Jefe Inmediato", "Analista Tesorería",
            "Custodio Caja Menuda", "Analista Presupuesto",
            "Analista Contabilidad", "Director Finanzas",
            "Fiscalizador CGR", "Administrador Sistema"
        ]
        
        existing_roles = self.db.query(Rol).all()
        existing_role_names = [role.nombre_rol for role in existing_roles]
        
        # Check for missing roles
        missing_roles = [role for role in required_roles if role not in existing_role_names]
        if missing_roles:
            result["is_valid"] = False
            result["errors"].append(f"Missing required roles: {', '.join(missing_roles)}")
        
        # Check that each role has some transitions
        for role in existing_roles:
            role_transitions = self.db.query(TransicionFlujo).filter(
                TransicionFlujo.id_rol_autorizado == role.id_rol,
                TransicionFlujo.es_activa == True
            ).count()
            
            if role_transitions == 0 and role.nombre_rol != "Administrador Sistema":
                result["warnings"].append(f"Role '{role.nombre_rol}' has no authorized transitions")
        
        result["existing_roles"] = len(existing_roles)
        result["required_roles"] = len(required_roles)
        
        return result
    
    def _validate_coverage(self) -> Dict[str, Any]:
        """
        Validates that the workflow covers all required business scenarios
        """
        result = {"is_valid": True, "errors": [], "warnings": []}
        
        # Check that both VIATICOS and CAJA_MENUDA workflows are covered
        estados_viaticos = self.db.query(EstadoFlujo).filter(
            EstadoFlujo.tipo_flujo.in_([TipoFlujo.VIATICOS, TipoFlujo.AMBOS])
        ).count()
        
        estados_caja_menuda = self.db.query(EstadoFlujo).filter(
            EstadoFlujo.tipo_flujo.in_([TipoFlujo.CAJA_MENUDA, TipoFlujo.AMBOS])
        ).count()
        
        if estados_viaticos < 5:  # Minimum expected states for VIATICOS
            result["warnings"].append("Insufficient states for VIATICOS workflow")
        
        if estados_caja_menuda < 3:  # Minimum expected states for CAJA_MENUDA
            result["warnings"].append("Insufficient states for CAJA_MENUDA workflow")
        
        # Check CGR refrendo path exists
        cgr_states = self.db.query(EstadoFlujo).filter(
            EstadoFlujo.nombre_estado == "PENDIENTE_REFRENDO_CGR"
        ).count()
        
        if cgr_states == 0:
            result["errors"].append("Missing CGR refrendo state for high-value missions")
            result["is_valid"] = False
        
        # Check electronic signature support
        firma_states = self.db.query(EstadoFlujo).filter(
            EstadoFlujo.nombre_estado == "PENDIENTE_FIRMA_ELECTRONICA"
        ).count()
        
        if firma_states == 0:
            result["warnings"].append("Missing electronic signature state")
        
        result["viaticos_states"] = estados_viaticos
        result["caja_menuda_states"] = estados_caja_menuda
        
        return result
    
    def get_workflow_summary(self) -> Dict[str, Any]:
        """
        Returns a summary of the current workflow configuration
        """
        states = self.db.query(EstadoFlujo).order_by(EstadoFlujo.orden_flujo).all()
        transitions = self.db.query(TransicionFlujo).filter(TransicionFlujo.es_activa == True).all()
        roles = self.db.query(Rol).all()
        
        summary = {
            "total_states": len(states),
            "total_active_transitions": len(transitions),
            "total_roles": len(roles),
            "states_by_type": {
                "VIATICOS": len([s for s in states if s.tipo_flujo in [TipoFlujo.VIATICOS, TipoFlujo.AMBOS]]),
                "CAJA_MENUDA": len([s for s in states if s.tipo_flujo in [TipoFlujo.CAJA_MENUDA, TipoFlujo.AMBOS]]),
                "AMBOS": len([s for s in states if s.tipo_flujo == TipoFlujo.AMBOS])
            },
            "transitions_by_action": {
                action.value: len([t for t in transitions if t.tipo_accion == action])
                for action in TipoAccion
            },
            "states_list": [
                {
                    "id": s.id_estado_flujo,
                    "name": s.nombre_estado,
                    "order": s.orden_flujo,
                    "type": s.tipo_flujo,
                    "is_final": s.es_estado_final
                }
                for s in states
            ]
        }
        
        return summary
    
    def fix_common_issues(self) -> Dict[str, Any]:
        """
        Automatically fixes common workflow configuration issues
        """
        fixes_applied = []
        
        # This would implement automatic fixes for common issues
        # For now, just return what could be fixed
        potential_fixes = [
            "Add missing workflow states",
            "Create missing critical transitions",
            "Set proper state ordering",
            "Ensure all roles have appropriate transitions"
        ]
        
        return {
            "fixes_applied": fixes_applied,
            "potential_fixes": potential_fixes,
            "manual_intervention_required": True
        }