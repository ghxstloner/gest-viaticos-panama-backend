"""
Custom exceptions for the SIRCEL (Sistema Integrado de Refrendo y Gestión de Cobro en Línea) application.

This module defines business-specific exceptions that can be raised throughout the application
and handled by FastAPI's exception handlers to return appropriate HTTP responses.
"""

from fastapi import HTTPException, status
from typing import Optional, Dict, Any


class BusinessException(Exception):
    """
    Base exception for business logic errors.
    
    This exception is raised when business rules are violated or 
    invalid operations are attempted according to the SIRCEL workflow.
    """
    
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        self.message = message
        self.details = details or {}
        super().__init__(self.message)


class WorkflowException(BusinessException):
    """
    Exception raised when workflow state transitions are invalid.
    
    Used specifically for SIRCEL workflow violations like:
    - Invalid state transitions
    - Unauthorized workflow actions
    - Missing required approvals
    """
    pass


class ValidationException(BusinessException):
    """
    Exception raised when data validation fails.
    
    Used for business rule validations like:
    - Invalid mission dates
    - Amount limits exceeded
    - Required field violations
    """
    pass


class PermissionException(BusinessException):
    """
    Exception raised when user lacks required permissions.
    
    Used for role-based access control violations like:
    - Insufficient user role for action
    - Unauthorized resource access
    - Invalid operation for user type
    """
    pass


class ConfigurationException(BusinessException):
    """
    Exception raised when system configuration is invalid or missing.
    
    Used for configuration-related errors like:
    - Missing system parameters
    - Invalid configuration values
    - Required settings not found
    """
    pass


class MissionException(BusinessException):
    """
    Exception raised for mission-specific business rule violations.
    
    Used for mission-related errors like:
    - Invalid mission type operations
    - CGR refrendo requirements not met
    - Mission amount calculations errors
    """
    pass


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