"""
Custom exceptions for the SIRCEL (Sistema Integrado de Refrendo y Gestión de Cobro en Línea) application.

This module defines business-specific exceptions that can be raised throughout the application
and handled by FastAPI's exception handlers to return appropriate HTTP responses.
"""

from typing import Dict, Any, Optional
from fastapi import HTTPException, status


class BaseAppException(Exception):
    """Excepción base para todas las excepciones de la aplicación"""
    def __init__(self, message: str, status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR):
        self.message = message
        self.status_code = status_code
        super().__init__(self.message)


class AuthenticationException(BaseAppException):
    """Excepción para errores de autenticación"""
    def __init__(self, message: str = "Error de autenticación"):
        super().__init__(message, status_code=status.HTTP_401_UNAUTHORIZED)


class ValidationException(BaseAppException):
    """Excepción para errores de validación"""
    def __init__(self, message: str = "Error de validación"):
        super().__init__(message, status_code=status.HTTP_422_UNPROCESSABLE_ENTITY)


class PermissionException(BaseAppException):
    """Excepción para errores de permisos"""
    def __init__(self, message: str = "No tiene permisos para realizar esta acción"):
        super().__init__(message, status_code=status.HTTP_403_FORBIDDEN)


class BusinessException(BaseAppException):
    """Excepción para errores de lógica de negocio"""
    def __init__(self, message: str = "Error en la lógica de negocio"):
        super().__init__(message, status_code=status.HTTP_400_BAD_REQUEST)


class MissionException(BusinessException):
    """Excepción específica para errores relacionados con misiones"""
    pass


class WorkflowException(BusinessException):
    """Excepción específica para errores en el flujo de trabajo"""
    pass


class ResourceNotFoundException(BaseAppException):
    """Excepción para recursos no encontrados"""
    def __init__(self, message: str = "Recurso no encontrado"):
        super().__init__(message, status_code=status.HTTP_404_NOT_FOUND)


class DatabaseException(BaseAppException):
    """Excepción para errores de base de datos"""
    def __init__(self, message: str = "Error en la base de datos"):
        super().__init__(message, status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)


class ConfigurationException(BaseAppException):
    """Excepción para errores de configuración"""
    def __init__(self, message: str = "Error en la configuración"):
        super().__init__(message, status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)


# HTTP Exception Classes for API responses
class MissionNotFound(HTTPException):
    """HTTP exception for mission not found errors."""
    
    def __init__(self, mission_id: int):
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Mission with ID {mission_id} not found"
        )


class UserNotFound(HTTPException):
    """HTTP exception for user not found errors."""
    
    def __init__(self, user_id: int = None, identifier: str = None):
        if user_id:
            detail = f"User with ID {user_id} not found"
        elif identifier:
            detail = f"User with identifier '{identifier}' not found"
        else:
            detail = "User not found"
            
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=detail
        )


class UnauthorizedAction(HTTPException):
    """HTTP exception for unauthorized actions."""
    
    def __init__(self, action: str, resource: str = "resource"):
        super().__init__(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Not authorized to {action} on {resource}"
        )


class InvalidWorkflowTransition(HTTPException):
    """HTTP exception for invalid workflow transitions."""
    
    def __init__(self, current_state: str, attempted_action: str):
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot perform '{attempted_action}' action from state '{current_state}'"
        )


class BusinessRuleViolation(HTTPException):
    """HTTP exception for business rule violations."""
    
    def __init__(self, rule: str, details: str = None):
        detail = f"Business rule violation: {rule}"
        if details:
            detail += f". {details}"
            
        super().__init__(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=detail
        )


class AmountLimitExceeded(HTTPException):
    """HTTP exception for amount limit violations."""
    
    def __init__(self, current_amount: float, limit: float, limit_type: str = ""):
        limit_desc = f" {limit_type}" if limit_type else ""
        super().__init__(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Amount B/. {current_amount:,.2f} exceeds{limit_desc} limit of B/. {limit:,.2f}"
        )


class MissionDateException(HTTPException):
    """HTTP exception for mission date validation errors."""
    
    def __init__(self, message: str):
        super().__init__(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Mission date validation error: {message}"
        )


class CGRReframeRequired(HTTPException):
    """HTTP exception when CGR refrendo is required but not properly configured."""
    
    def __init__(self, amount: float, threshold: float):
        super().__init__(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Mission amount B/. {amount:,.2f} requires CGR refrendo (threshold: B/. {threshold:,.2f})"
        ) 