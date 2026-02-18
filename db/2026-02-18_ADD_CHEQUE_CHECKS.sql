-- Migration: Agregar campos para tracking de cheque en misiones de viáticos
-- Fecha: 2025-02-18
-- Descripción: Agrega dos campos booleanos para marcar estado del cheque

-- Agregar campo para indicar que el cheque fue confeccionado
ALTER TABLE misiones 
ADD COLUMN cheque_confeccionado BOOLEAN DEFAULT FALSE 
COMMENT 'Indica si el cheque de viáticos ya fue confeccionado';

-- Agregar campo para indicar que el cheque fue firmado
ALTER TABLE misiones 
ADD COLUMN cheque_firmado BOOLEAN DEFAULT FALSE 
COMMENT 'Indica si el cheque de viáticos ya fue firmado';

-- Verificar que las columnas se agregaron correctamente
DESCRIBE misiones;

-- Nota: Estos campos aplican únicamente para misiones de tipo VIATICOS
-- La validación del tipo de misión se maneja desde el backend/frontend
