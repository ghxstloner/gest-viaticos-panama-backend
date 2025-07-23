INSERT INTO `estados_flujo` (`id_estado_flujo`, `nombre_estado`, `descripcion`, `es_estado_final`, `requiere_comentario`, `orden_flujo`, `tipo_flujo`) VALUES (6, 'APROBADO_PARA_PAGO', 'Aprobado y listo para pago', 0, 0, 7, 'AMBOS');

ALTER TABLE `historial_flujo`
	ADD COLUMN `observacion` LONGTEXT NULL COLLATE 'utf8mb4_general_ci' AFTER `ip_usuario`;

ALTER TABLE `misiones`
	CHANGE COLUMN `categoria_beneficiario` `categoria_beneficiario` ENUM('TITULAR','OTROS_SERVIDORES_PUBLICOS','OTRAS _PERSONAS') NOT NULL COMMENT 'Categoría del beneficiario para cálculo de tarifas, según formulario y data' COLLATE 'utf8mb4_0900_ai_ci' AFTER `id_usuario_prepara`;
