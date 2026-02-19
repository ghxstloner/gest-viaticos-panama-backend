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


CREATE TABLE `nompersonal` (
  `personal_id` int NOT NULL,
  `cedula` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci DEFAULT NULL,
  `apenom` varchar(60) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci DEFAULT NULL,
  `sexo` varchar(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci DEFAULT NULL,
  `estado_civil` varchar(13) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci DEFAULT NULL,
  `direccion` varchar(150) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci DEFAULT NULL,
  `telefonos` varchar(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci DEFAULT NULL,
  `email` varchar(40) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci DEFAULT NULL,
  `fecnac` date DEFAULT NULL,
  `codpro` int DEFAULT NULL,
  `foto` varchar(80) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci DEFAULT NULL,
  `tipnom` int DEFAULT '0',
  `codnivel1` int DEFAULT NULL,
  `codnivel2` varchar(8) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci DEFAULT NULL,
  `codnivel3` varchar(8) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci DEFAULT NULL,
  `codnivel4` varchar(8) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci DEFAULT NULL,
  `codnivel5` varchar(8) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci DEFAULT NULL,
  `ficha` int DEFAULT NULL,
  `fecing` date DEFAULT NULL,
  `codcat` varchar(6) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci DEFAULT NULL,
  `codcargo` int(7) UNSIGNED ZEROFILL DEFAULT NULL,
  `nomposicion_id` int(4) UNSIGNED ZEROFILL NOT NULL,
  `forcob` varchar(39) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci DEFAULT NULL,
  `codbancob` int DEFAULT NULL,
  `cuentacob` varchar(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci DEFAULT NULL,
  `estado` varchar(100) DEFAULT NULL,
  `estado_anterior` varchar(100) DEFAULT NULL COMMENT 'Estado anterior antes de vacaciones o licencias',
  `tipemp` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci DEFAULT NULL,
  `sueldopro` decimal(20,2) DEFAULT NULL,
  `fechaplica` date DEFAULT NULL,
  `tipopres` tinyint DEFAULT NULL,
  `fechasus` date DEFAULT NULL,
  `fechareisus` date DEFAULT NULL,
  `fechavac` date DEFAULT NULL,
  `fechareivac` date DEFAULT NULL,
  `fecharetiro` date DEFAULT NULL,
  `periodo` int DEFAULT NULL,
  `markar` tinyint DEFAULT NULL,
  `cod_tli` varchar(19) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci DEFAULT NULL,
  `motivo_liq` varchar(8) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci DEFAULT NULL,
  `preaviso` varchar(2) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci DEFAULT NULL,
  `suesal` decimal(20,2) DEFAULT NULL,
  `id_moneda` int DEFAULT NULL,
  `contrato` varchar(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci DEFAULT NULL,
  `nombres` varchar(30) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci DEFAULT NULL,
  `nombres2` varchar(100) DEFAULT NULL,
  `apellidos` varchar(30) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci DEFAULT NULL,
  `nacionalidad` tinyint DEFAULT NULL,
  `ee` tinyint DEFAULT NULL,
  `codnivel6` varchar(8) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci DEFAULT NULL,
  `codnivel7` varchar(8) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci DEFAULT NULL,
  `inicio_periodo` date DEFAULT NULL,
  `fin_periodo` date DEFAULT NULL,
  `antiguedadap` varchar(2) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci DEFAULT NULL,
  `paso` int DEFAULT NULL,
  `motivo_retiro` varchar(30) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci DEFAULT NULL,
  `seguro_social` varchar(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci DEFAULT NULL,
  `hora_base` decimal(10,2) DEFAULT NULL,
  `dv` varchar(10) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci DEFAULT NULL,
  `ConceptoBaja` varchar(191) DEFAULT NULL,
  `imagen_cedula` varchar(80) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci DEFAULT NULL,
  `mes1` int DEFAULT NULL,
  `mes2` int DEFAULT NULL,
  `mes3` int DEFAULT NULL,
  `cta_presupuestaria` varchar(30) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci DEFAULT NULL,
  `clave_ir` varchar(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci DEFAULT NULL,
  `IdTipoSangre` int DEFAULT NULL,
  `TelefonoCelular` varchar(60) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci DEFAULT NULL,
  `ContactoEmergencia` varchar(300) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci DEFAULT NULL,
  `TelefonoEmergencia` varchar(60) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci DEFAULT NULL,
  `Hijos` int DEFAULT NULL,
  `EnfermedadesYAlergias` varchar(600) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci DEFAULT NULL,
  `useruid` varchar(300) DEFAULT NULL,
  `jefe` varchar(300) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci DEFAULT NULL,
  `condicion` char(15) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci DEFAULT NULL,
  `tiene_discapacidad` char(1) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci DEFAULT NULL,
  `comentario` varchar(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci DEFAULT NULL,
  `id_institucion` int DEFAULT NULL,
  `apellido_materno` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci DEFAULT NULL,
  `apellido_casada` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci DEFAULT NULL,
  `observaciones` varchar(200) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci DEFAULT NULL,
  `IdNivelEducativo` int DEFAULT NULL,
  `gastos_representacion` decimal(10,2) DEFAULT NULL,
  `antiguedad` decimal(10,2) DEFAULT NULL,
  `otros` decimal(10,2) DEFAULT NULL,
  `IdDepartamento` int DEFAULT NULL,
  `nomfuncion_id` int DEFAULT NULL,
  `estados` varchar(2) DEFAULT NULL,
  `tipo_funcionario` int NOT NULL,
  `unidad` int(5) UNSIGNED ZEROFILL DEFAULT NULL,
  `objeto` int(5) UNSIGNED ZEROFILL DEFAULT NULL,
  `usuario_workflow` varchar(50) DEFAULT NULL COMMENT 'NOMBRE USUARIO WORKFLOW',
  `usr_password` varchar(100) DEFAULT NULL,
  `provincia` varchar(5) DEFAULT NULL,
  `dir_provincia` int DEFAULT NULL,
  `dir_distrito` int DEFAULT NULL,
  `dir_corregimiento` int DEFAULT NULL,
  `extension` varchar(5) DEFAULT NULL,
  `correo_alternativo` varchar(50) DEFAULT NULL,
  `numero_carnet` varchar(50) DEFAULT NULL,
  `marca_reloj` int DEFAULT '0',
  `fecha_inicio_marca_reloj` date DEFAULT NULL,
  `titulo_profesional` int DEFAULT NULL,
  `institucion` int DEFAULT NULL,
  `proyecto` int UNSIGNED DEFAULT NULL,
  `fecha_reintegro` date NOT NULL,
  `ley_59` varchar(1) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci DEFAULT NULL,
  `observaciones_discapacidad` varchar(500) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NOT NULL,
  `discapacidad_ley_15_servidor_publico` int DEFAULT NULL,
  `discapacidad_ley_15_dx` varchar(500) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci DEFAULT NULL,
  `discapacidad_ley_15_nombre_familiar1` varchar(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci DEFAULT NULL,
  `discapacidad_ley_15_apellido_familiar1` varchar(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci DEFAULT NULL,
  `discapacidad_ley_15_parentesco_familiar1` int DEFAULT NULL,
  `discapacidad_ley_15_dx_familiar1` varchar(500) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci DEFAULT NULL,
  `discapacidad_ley_15_nombre_familiar2` varchar(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci DEFAULT NULL,
  `discapacidad_ley_15_apellido_familiar2` varchar(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci DEFAULT NULL,
  `discapacidad_ley_15_parentesco_familiar2` int DEFAULT NULL,
  `discapacidad_ley_15_dx_familiar2` varchar(500) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci DEFAULT NULL,
  `discapacidad_ley_15_ambos` int DEFAULT NULL,
  `discapacidad_senadis` int DEFAULT NULL,
  `discapacidad_carnet` varchar(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci DEFAULT NULL,
  `discapacidad_ley_15_observaciones` varchar(500) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci DEFAULT NULL,
  `discapacidad_ley_59_servidor_publico` int DEFAULT NULL,
  `discapacidad_ley_59_dx` varchar(500) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci DEFAULT NULL,
  `discapacidad_ley_59_nombre_familiar1` varchar(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci DEFAULT NULL,
  `discapacidad_ley_59_apellido_familiar1` varchar(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci DEFAULT NULL,
  `discapacidad_ley_59_parentesco_familiar1` int DEFAULT NULL,
  `discapacidad_ley_59_dx_familiar1` varchar(500) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci DEFAULT NULL,
  `discapacidad_ley_59_nombre_familiar2` varchar(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci DEFAULT NULL,
  `discapacidad_ley_59_apellido_familiar2` varchar(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci DEFAULT NULL,
  `discapacidad_ley_59_parentesco_familiar2` int DEFAULT NULL,
  `discapacidad_ley_59_dx_familiar2` varchar(500) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci DEFAULT NULL,
  `discapacidad_ley_59_ambos` int DEFAULT NULL,
  `discapacidad_ley_59_observaciones` varchar(500) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci DEFAULT NULL,
  `discapacidad_diagnostico_ocasional` int DEFAULT NULL,
  `discapacidad_diagnostico_ocasional_observaciones` varchar(500) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci DEFAULT NULL,
  `rango` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NOT NULL,
  `created_at` datetime DEFAULT NULL,
  `updated_at` datetime DEFAULT NULL ON UPDATE CURRENT_TIMESTAMP,
  `rata_x_hr` decimal(10,2) DEFAULT '0.00' COMMENT 'Rata por Hora - Regla de Negocio',
  `salario_diario` decimal(10,2) DEFAULT '0.00' COMMENT 'Salario Diario - Regla de Negocio',
  `cod_sur` varchar(10) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci DEFAULT NULL,
  `gasto_rep_diario` decimal(10,2) DEFAULT '0.00' COMMENT 'Gasto Diario de Representación - Regla de Negocio',
  `rata_hora_gasto_rep` decimal(10,2) DEFAULT '0.00' COMMENT 'Rata por Hora de Gasto de Representación - Regla de Negocio',
  `cuenta_pago` varchar(255) DEFAULT NULL COMMENT 'Cuenta Pago - Regla de Negocio',
  `cod_sin` varchar(10) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci DEFAULT NULL,
  `zona_economica` varchar(255) DEFAULT NULL COMMENT 'Zona Económica - Regla de Negocio',
  `cod_dia` varchar(10) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci DEFAULT NULL,
  `cod_tip` varchar(10) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci DEFAULT NULL,
  `cod_jor` varchar(10) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci DEFAULT NULL,
  `cod_sue` varchar(10) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci DEFAULT NULL,
  `ISRFijoPeriodo` decimal(10,2) DEFAULT '0.00' COMMENT 'Renta Fija por Periodo - Regla de Negocio',
  `cod_cos` varchar(10) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci DEFAULT NULL,
  `id_posicion_mef` int DEFAULT NULL,
  `id_codigo_cargo_mef` int DEFAULT NULL,
  `id_cargo_mef` int DEFAULT NULL,
  `cod_niv` varchar(6) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci DEFAULT NULL,
  `discapacidad_comprobada` tinyint(1) NOT NULL DEFAULT '0',
  `porcentaje_discapacidad_empleado` decimal(5,2) DEFAULT NULL,
  `certificado_senadis_empleado` tinyint(1) NOT NULL DEFAULT '0',
  `fecha_certificacion_empleado` date DEFAULT NULL,
  `tutor_discapacidad` tinyint(1) NOT NULL DEFAULT '0',
  `enfermedad_cronica_comprobada` tinyint(1) DEFAULT '0',
  `es_recurso` tinyint(1) DEFAULT '0',
  `es_agente` tinyint(1) DEFAULT '0',
  `es_usuario_web` tinyint(1) DEFAULT '0',
  `indicaciones_medicas_permanentes` tinyint(1) DEFAULT '0',
  `indicaciones_temporales` tinyint(1) DEFAULT '0',
  `indicaciones_temporales_fecha` date DEFAULT NULL,
  `embarazo` tinyint(1) DEFAULT '0',
  `ParentescoEmergencia` int DEFAULT NULL,
  `DireccionEmergencia` varchar(255) DEFAULT NULL,
  `ContactoEmergencia2` varchar(100) DEFAULT NULL,
  `TelefonoEmergencia2` varchar(20) DEFAULT NULL,
  `ParentescoEmergencia2` int DEFAULT NULL,
  `DireccionEmergencia2` varchar(255) DEFAULT NULL,
  `proposito_cargo` varchar(300) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci DEFAULT NULL,
  `cod_hor` int DEFAULT NULL,
  `observaciones_academico` varchar(191) DEFAULT NULL,
  `id_pais` int DEFAULT NULL,
  `barrio` varchar(100) DEFAULT NULL,
  `calle` varchar(100) DEFAULT NULL,
  `num_casa` varchar(20) DEFAULT NULL,
  `num_apto` varchar(20) DEFAULT NULL,
  `descripcion_pago` varchar(100) DEFAULT NULL,
  `cantidadDependientes` int DEFAULT NULL,
  `bl_fono_observacion` text COMMENT 'Observaciones de fonoaudiología',
  `bl_fono_diagnostico` varchar(255) DEFAULT NULL COMMENT 'Diagnóstico de fonoaudiología',
  `bl_fono_certificacion_senadis` tinyint(1) DEFAULT '0' COMMENT 'Si tiene certificación por SENADIS',
  `bl_fono_cantidad_examenes` int DEFAULT '0' COMMENT 'Cantidad de exámenes realizados',
  `bl_fono_fecha_ultimo_examen` date DEFAULT NULL COMMENT 'Fecha del último examen',
  `bl_fono_prox_evaluacion` date DEFAULT NULL COMMENT 'Fecha de próxima evaluación (6 meses después del último)',
  `turno_id` int DEFAULT NULL,
  `es_generalista` tinyint(1) NOT NULL DEFAULT '0',
  `bl_fono_diagnosticos_ids` varchar(255) DEFAULT NULL COMMENT 'IDs de diagnósticos separados por comas',
  `bl_fono_condicion_salud` enum('bilateral','unilateral') DEFAULT NULL COMMENT 'Condición de salud bilateral o unilateral',
  `bl_fono_status` enum('pendiente','completado','anulado') DEFAULT 'pendiente' COMMENT 'Status de la evaluación',
  `ultimo_dia_pagado` date DEFAULT NULL COMMENT 'Último día pagado del colaborador',
  `es_marcacion_abierta` tinyint(1) DEFAULT '0',
  `nota_aceptacion` varchar(250) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci DEFAULT NULL,
  `correo_institucional` varchar(100) DEFAULT NULL COMMENT 'Correo electrónico institucional del colaborador',
  `password_changed_at` datetime DEFAULT NULL COMMENT 'Fecha del último cambio de contraseña',
  `marcacion_abierta_archive` longtext,
  `id_enfermedad_cronica` int DEFAULT NULL,
  `certificado_medico_ley59` tinyint(1) NOT NULL DEFAULT '0',
  `fecha_diagnostico_ley59` date DEFAULT NULL,
  `observaciones_ley59` text CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci,
  `autorizacion_excepcion` varchar(100) DEFAULT NULL,
  `tipo_horario_id` int DEFAULT NULL,
  `dias_libres_id` int DEFAULT NULL,
  `situacion` varchar(50) DEFAULT NULL,
  `force_password_change` tinyint(1) NOT NULL DEFAULT '0' COMMENT 'Indica si se requiere cambio forzado de contraseña (0=No, 1=Sí)',
  `password_expiry_days` int NOT NULL DEFAULT '45' COMMENT 'Número de días que dura la contraseña antes de expirar'
) ENGINE=InnoDB AVG_ROW_LENGTH=290 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
feb 19 14:31:01 Talento-ubuntu-s-2vcpu-4gb-120gb-intel-sfo2-01 uvicorn[1272242]: Traceback (most recent call last):
feb 19 14:31:01 Talento-ubuntu-s-2vcpu-4gb-120gb-intel-sfo2-01 uvicorn[1272242]:   File "/var/www/html/gestviaticos/gest-viaticos-panama-backend/venv/lib/python3.12/site-packages/mysql/connector/connection_cext.py", line 772, in cmd_query
feb 19 14:31:01 Talento-ubuntu-s-2vcpu-4gb-120gb-intel-sfo2-01 uvicorn[1272242]:     self._cmysql.query(
feb 19 14:31:01 Talento-ubuntu-s-2vcpu-4gb-120gb-intel-sfo2-01 uvicorn[1272242]: _mysql_connector.MySQLInterfaceError: Unknown database 'aitsa_rrhh'
feb 19 14:31:01 Talento-ubuntu-s-2vcpu-4gb-120gb-intel-sfo2-01 uvicorn[1272242]: The above exception was the direct cause of the following exception:
feb 19 14:31:01 Talento-ubuntu-s-2vcpu-4gb-120gb-intel-sfo2-01 uvicorn[1272242]: Traceback (most recent call last):
feb 19 14:31:01 Talento-ubuntu-s-2vcpu-4gb-120gb-intel-sfo2-01 uvicorn[1272242]:   File "/var/www/html/gestviaticos/gest-viaticos-panama-backend/venv/lib/python3.12/site-packages/sqlalchemy/engine/base.py", line 1963, in _exec_single_context
feb 19 14:31:01 Talento-ubuntu-s-2vcpu-4gb-120gb-intel-sfo2-01 uvicorn[1272242]:     self.dialect.do_execute(
feb 19 14:31:01 Talento-ubuntu-s-2vcpu-4gb-120gb-intel-sfo2-01 uvicorn[1272242]:   File "/var/www/html/gestviaticos/gest-viaticos-panama-backend/venv/lib/python3.12/site-packages/sqlalchemy/engine/default.py", line 943, in do_execute
feb 19 14:31:01 Talento-ubuntu-s-2vcpu-4gb-120gb-intel-sfo2-01 uvicorn[1272242]:     cursor.execute(statement, parameters)
feb 19 14:31:01 Talento-ubuntu-s-2vcpu-4gb-120gb-intel-sfo2-01 uvicorn[1272242]:   File "/var/www/html/gestviaticos/gest-viaticos-panama-backend/venv/lib/python3.12/site-packages/mysql/connector/cursor_cext.py", line 356, in execute
feb 19 14:31:01 Talento-ubuntu-s-2vcpu-4gb-120gb-intel-sfo2-01 uvicorn[1272242]:     self._connection.cmd_query(
feb 19 14:31:01 Talento-ubuntu-s-2vcpu-4gb-120gb-intel-sfo2-01 uvicorn[1272242]:   File "/var/www/html/gestviaticos/gest-viaticos-panama-backend/venv/lib/python3.12/site-packages/mysql/connector/opentelemetry/context_propagation.py", line 97, in wrapper
feb 19 14:31:01 Talento-ubuntu-s-2vcpu-4gb-120gb-intel-sfo2-01 uvicorn[1272242]:     return method(cnx, *args, **kwargs)
feb 19 14:31:01 Talento-ubuntu-s-2vcpu-4gb-120gb-intel-sfo2-01 uvicorn[1272242]:            ^^^^^^^^^^^^^^^^^^^^^^^^^^^^
feb 19 14:31:01 Talento-ubuntu-s-2vcpu-4gb-120gb-intel-sfo2-01 uvicorn[1272242]:   File "/var/www/html/gestviaticos/gest-viaticos-panama-backend/venv/lib/python3.12/site-packages/mysql/connector/connection_cext.py", line 781, in cmd_query
feb 19 14:31:01 Talento-ubuntu-s-2vcpu-4gb-120gb-intel-sfo2-01 uvicorn[1272242]:     raise get_mysql_exception(
feb 19 14:31:01 Talento-ubuntu-s-2vcpu-4gb-120gb-intel-sfo2-01 uvicorn[1272242]: mysql.connector.errors.ProgrammingError: 1049 (42000): Unknown database 'aitsa_rrhh'
feb 19 14:31:01 Talento-ubuntu-s-2vcpu-4gb-120gb-intel-sfo2-01 uvicorn[1272242]: The above exception was the direct cause of the following exception:
feb 19 14:31:01 Talento-ubuntu-s-2vcpu-4gb-120gb-intel-sfo2-01 uvicorn[1272242]: Traceback (most recent call last):
feb 19 14:31:01 Talento-ubuntu-s-2vcpu-4gb-120gb-intel-sfo2-01 uvicorn[1272242]:   File "/var/www/html/gestviaticos/gest-viaticos-panama-backend/app/api/v1/missions.py", line 256, in get_employee_missions
feb 19 14:31:01 Talento-ubuntu-s-2vcpu-4gb-120gb-intel-sfo2-01 uvicorn[1272242]:     result = db_rrhh.execute(text("""
feb 19 14:31:01 Talento-ubuntu-s-2vcpu-4gb-120gb-intel-sfo2-01 uvicorn[1272242]:              ^^^^^^^^^^^^^^^^^^^^^^^^
feb 19 14:31:01 Talento-ubuntu-s-2vcpu-4gb-120gb-intel-sfo2-01 uvicorn[1272242]:   File "/var/www/html/gestviaticos/gest-viaticos-panama-backend/venv/lib/python3.12/site-packages/sqlalchemy/orm/session.py", line 2365, in execute
feb 19 14:31:01 Talento-ubuntu-s-2vcpu-4gb-120gb-intel-sfo2-01 uvicorn[1272242]:     return self._execute_internal(
feb 19 14:31:01 Talento-ubuntu-s-2vcpu-4gb-120gb-intel-sfo2-01 uvicorn[1272242]:            ^^^^^^^^^^^^^^^^^^^^^^^
feb 19 14:31:01 Talento-ubuntu-s-2vcpu-4gb-120gb-intel-sfo2-01 uvicorn[1272242]:   File "/var/www/html/gestviaticos/gest-viaticos-panama-backend/venv/lib/python3.12/site-packages/sqlalchemy/orm/session.py", line 2260, in _execute_internal
feb 19 14:31:01 Talento-ubuntu-s-2vcpu-4gb-120gb-intel-sfo2-01 uvicorn[1272242]:     result = conn.execute(
feb 19 14:31:01 Talento-ubuntu-s-2vcpu-4gb-120gb-intel-sfo2-01 uvicorn[1272242]:              ^^^^^^^^^^^^^
feb 19 14:31:01 Talento-ubuntu-s-2vcpu-4gb-120gb-intel-sfo2-01 uvicorn[1272242]:   File "/var/www/html/gestviaticos/gest-viaticos-panama-backend/venv/lib/python3.12/site-packages/sqlalchemy/engine/base.py", line 1415, in execute
feb 19 14:31:01 Talento-ubuntu-s-2vcpu-4gb-120gb-intel-sfo2-01 uvicorn[1272242]:     return meth(
feb 19 14:31:01 Talento-ubuntu-s-2vcpu-4gb-120gb-intel-sfo2-01 uvicorn[1272242]:            ^^^^^
feb 19 14:31:01 Talento-ubuntu-s-2vcpu-4gb-120gb-intel-sfo2-01 uvicorn[1272242]:   File "/var/www/html/gestviaticos/gest-viaticos-panama-backend/venv/lib/python3.12/site-packages/sqlalchemy/sql/elements.py", line 523, in _execute_on_connection
feb 19 14:31:01 Talento-ubuntu-s-2vcpu-4gb-120gb-intel-sfo2-01 uvicorn[1272242]:     return connection._execute_clauseelement(
feb 19 14:31:01 Talento-ubuntu-s-2vcpu-4gb-120gb-intel-sfo2-01 uvicorn[1272242]:            ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
feb 19 14:31:01 Talento-ubuntu-s-2vcpu-4gb-120gb-intel-sfo2-01 uvicorn[1272242]:   File "/var/www/html/gestviaticos/gest-viaticos-panama-backend/venv/lib/python3.12/site-packages/sqlalchemy/engine/base.py", line 1637, in _execute_clauseelement
feb 19 14:31:01 Talento-ubuntu-s-2vcpu-4gb-120gb-intel-sfo2-01 uvicorn[1272242]:     ret = self._execute_context(
feb 19 14:31:01 Talento-ubuntu-s-2vcpu-4gb-120gb-intel-sfo2-01 uvicorn[1272242]:           ^^^^^^^^^^^^^^^^^^^^^^
feb 19 14:31:01 Talento-ubuntu-s-2vcpu-4gb-120gb-intel-sfo2-01 uvicorn[1272242]:   File "/var/www/html/gestviaticos/gest-viaticos-panama-backend/venv/lib/python3.12/site-packages/sqlalchemy/engine/base.py", line 1842, in _execute_context
feb 19 14:31:01 Talento-ubuntu-s-2vcpu-4gb-120gb-intel-sfo2-01 uvicorn[1272242]:     return self._exec_single_context(
feb 19 14:31:01 Talento-ubuntu-s-2vcpu-4gb-120gb-intel-sfo2-01 uvicorn[1272242]:            ^^^^^^^^^^^^^^^^^^^^^^^^^^
feb 19 14:31:01 Talento-ubuntu-s-2vcpu-4gb-120gb-intel-sfo2-01 uvicorn[1272242]:   File "/var/www/html/gestviaticos/gest-viaticos-panama-backend/venv/lib/python3.12/site-packages/sqlalchemy/engine/base.py", line 1982, in _exec_single_context
feb 19 14:31:01 Talento-ubuntu-s-2vcpu-4gb-120gb-intel-sfo2-01 uvicorn[1272242]:     self._handle_dbapi_exception(
feb 19 14:31:01 Talento-ubuntu-s-2vcpu-4gb-120gb-intel-sfo2-01 uvicorn[1272242]:   File "/var/www/html/gestviaticos/gest-viaticos-panama-backend/venv/lib/python3.12/site-packages/sqlalchemy/engine/base.py", line 2351, in _handle_dbapi_exception
feb 19 14:31:01 Talento-ubuntu-s-2vcpu-4gb-120gb-intel-sfo2-01 uvicorn[1272242]:     raise sqlalchemy_exception.with_traceback(exc_info[2]) from e
feb 19 14:31:01 Talento-ubuntu-s-2vcpu-4gb-120gb-intel-sfo2-01 uvicorn[1272242]:   File "/var/www/html/gestviaticos/gest-viaticos-panama-backend/venv/lib/python3.12/site-packages/sqlalchemy/engine/base.py", line 1963, in _exec_single_context
feb 19 14:31:01 Talento-ubuntu-s-2vcpu-4gb-120gb-intel-sfo2-01 uvicorn[1272242]:     self.dialect.do_execute(
feb 19 14:31:01 Talento-ubuntu-s-2vcpu-4gb-120gb-intel-sfo2-01 uvicorn[1272242]:   File "/var/www/html/gestviaticos/gest-viaticos-panama-backend/venv/lib/python3.12/site-packages/sqlalchemy/engine/default.py", line 943, in do_execute
feb 19 14:31:01 Talento-ubuntu-s-2vcpu-4gb-120gb-intel-sfo2-01 uvicorn[1272242]:     cursor.execute(statement, parameters)
feb 19 14:31:01 Talento-ubuntu-s-2vcpu-4gb-120gb-intel-sfo2-01 uvicorn[1272242]:   File "/var/www/html/gestviaticos/gest-viaticos-panama-backend/venv/lib/python3.12/site-packages/mysql/connector/cursor_cext.py", line 356, in execute
feb 19 14:31:01 Talento-ubuntu-s-2vcpu-4gb-120gb-intel-sfo2-01 uvicorn[1272242]:     self._connection.cmd_query(
feb 19 14:31:01 Talento-ubuntu-s-2vcpu-4gb-120gb-intel-sfo2-01 uvicorn[1272242]:   File "/var/www/html/gestviaticos/gest-viaticos-panama-backend/venv/lib/python3.12/site-packages/mysql/connector/opentelemetry/context_propagation.py", line 97, in wrapper
feb 19 14:31:01 Talento-ubuntu-s-2vcpu-4gb-120gb-intel-sfo2-01 uvicorn[1272242]:     return method(cnx, *args, **kwargs)
feb 19 14:31:01 Talento-ubuntu-s-2vcpu-4gb-120gb-intel-sfo2-01 uvicorn[1272242]:            ^^^^^^^^^^^^^^^^^^^^^^^^^^^^
feb 19 14:31:01 Talento-ubuntu-s-2vcpu-4gb-120gb-intel-sfo2-01 uvicorn[1272242]:   File "/var/www/html/gestviaticos/gest-viaticos-panama-backend/venv/lib/python3.12/site-packages/mysql/connector/connection_cext.py", line 781, in cmd_query
feb 19 14:31:01 Talento-ubuntu-s-2vcpu-4gb-120gb-intel-sfo2-01 uvicorn[1272242]:     raise get_mysql_exception(
feb 19 14:31:01 Talento-ubuntu-s-2vcpu-4gb-120gb-intel-sfo2-01 uvicorn[1272242]: sqlalchemy.exc.ProgrammingError: (mysql.connector.errors.ProgrammingError) 1049 (42000): Unknown database 'aitsa_rrhh'
feb 19 14:31:01 Talento-ubuntu-s-2vcpu-4gb-120gb-intel-sfo2-01 uvicorn[1272242]: [SQL:
feb 19 14:31:01 Talento-ubuntu-s-2vcpu-4gb-120gb-intel-sfo2-01 uvicorn[1272242]:             SELECT personal_id FROM aitsa_rrhh.nompersonal
feb 19 14:31:01 Talento-ubuntu-s-2vcpu-4gb-120gb-intel-sfo2-01 uvicorn[1272242]:             WHERE cedula = %(cedula)s AND estado != 'De Baja'
feb 19 14:31:01 Talento-ubuntu-s-2vcpu-4gb-120gb-intel-sfo2-01 uvicorn[1272242]:         ]
feb 19 14:31:01 Talento-ubuntu-s-2vcpu-4gb-120gb-intel-sfo2-01 uvicorn[1272242]: [parameters: {'cedula': 'E-8-157323'}]
feb 19 14:31:01 Talento-ubuntu-s-2vcpu-4gb-120gb-intel-sfo2-01 uvicorn[1272242]: (Background on this error at: https://sqlalche.me/e/20/f405)
feb 19 14:31:01 Talento-ubuntu-s-2vcpu-4gb-120gb-intel-sfo2-01 uvicorn[1272242]: Error obteniendo misiones del empleado: (mysql.connector.errors.ProgrammingError) 1049 (42000): Unknown database 'aitsa_rrhh'
feb 19 14:31:01 Talento-ubuntu-s-2vcpu-4gb-120gb-intel-sfo2-01 uvicorn[1272242]: [SQL:
feb 19 14:31:01 Talento-ubuntu-s-2vcpu-4gb-120gb-intel-sfo2-01 uvicorn[1272242]:             SELECT personal_id FROM aitsa_rrhh.nompersonal
feb 19 14:31:01 Talento-ubuntu-s-2vcpu-4gb-120gb-intel-sfo2-01 uvicorn[1272242]:             WHERE cedula = %(cedula)s AND estado != 'De Baja'
feb 19 14:31:01 Talento-ubuntu-s-2vcpu-4gb-120gb-intel-sfo2-01 uvicorn[1272242]:         ]
feb 19 14:31:01 Talento-ubuntu-s-2vcpu-4gb-120gb-intel-sfo2-01 uvicorn[1272242]: [parameters: {'cedula': 'E-8-157323'}]
feb 19 14:31:01 Talento-ubuntu-s-2vcpu-4gb-120gb-intel-sfo2-01 uvicorn[1272242]: (Background on this error at: https://sqlalche.me/e/20/f405)
feb 19 14:31:01 Talento-ubuntu-s-2vcpu-4gb-120gb-intel-sfo2-01 uvicorn[1272242]: INFO:     181.53.96.10:0 - "GET /api/v1/employee/requests/dashboard HTTP/1.1" 500 Internal Server Error
feb 19 14:31:01 Talento-ubuntu-s-2vcpu-4gb-120gb-intel-sfo2-01 uvicorn[1272242]: ERROR:    Exception in ASGI application
feb 19 14:31:01 Talento-ubuntu-s-2vcpu-4gb-120gb-intel-sfo2-01 uvicorn[1272242]: Traceback (most recent call last):
feb 19 14:31:01 Talento-ubuntu-s-2vcpu-4gb-120gb-intel-sfo2-01 uvicorn[1272242]:   File "/var/www/html/gestviaticos/gest-viaticos-panama-backend/venv/lib/python3.12/site-packages/mysql/connector/connection_cext.py", line 772, in cmd_query
feb 19 14:31:01 Talento-ubuntu-s-2vcpu-4gb-120gb-intel-sfo2-01 uvicorn[1272242]:     self._cmysql.query(
feb 19 14:31:01 Talento-ubuntu-s-2vcpu-4gb-120gb-intel-sfo2-01 uvicorn[1272242]: _mysql_connector.MySQLInterfaceError: Unknown database 'aitsa_rrhh'
feb 19 14:31:01 Talento-ubuntu-s-2vcpu-4gb-120gb-intel-sfo2-01 uvicorn[1272242]: The above exception was the direct cause of the following exception:
feb 19 14:31:01 Talento-ubuntu-s-2vcpu-4gb-120gb-intel-sfo2-01 uvicorn[1272242]: Traceback (most recent call last):
feb 19 14:31:01 Talento-ubuntu-s-2vcpu-4gb-120gb-intel-sfo2-01 uvicorn[1272242]:   File "/var/www/html/gestviaticos/gest-viaticos-panama-backend/venv/lib/python3.12/site-packages/sqlalchemy/engine/base.py", line 1963, in _exec_single_context
feb 19 14:31:01 Talento-ubuntu-s-2vcpu-4gb-120gb-intel-sfo2-01 uvicorn[1272242]:     self.dialect.do_execute(
feb 19 14:31:01 Talento-ubuntu-s-2vcpu-4gb-120gb-intel-sfo2-01 uvicorn[1272242]:   File "/var/www/html/gestviaticos/gest-viaticos-panama-backend/venv/lib/python3.12/site-packages/sqlalchemy/engine/default.py", line 943, in do_execute
feb 19 14:31:01 Talento-ubuntu-s-2vcpu-4gb-120gb-intel-sfo2-01 uvicorn[1272242]:     cursor.execute(statement, parameters)
feb 19 14:31:01 Talento-ubuntu-s-2vcpu-4gb-120gb-intel-sfo2-01 uvicorn[1272242]:   File "/var/www/html/gestviaticos/gest-viaticos-panama-backend/venv/lib/python3.12/site-packages/mysql/connector/cursor_cext.py", line 356, in execute
feb 19 14:31:01 Talento-ubuntu-s-2vcpu-4gb-120gb-intel-sfo2-01 uvicorn[1272242]:     self._connection.cmd_query(
feb 19 14:31:01 Talento-ubuntu-s-2vcpu-4gb-120gb-intel-sfo2-01 uvicorn[1272242]:   File "/var/www/html/gestviaticos/gest-viaticos-panama-backend/venv/lib/python3.12/site-packages/mysql/connector/opentelemetry/context_propagation.py", line 97, in wrapper
feb 19 14:31:01 Talento-ubuntu-s-2vcpu-4gb-120gb-intel-sfo2-01 uvicorn[1272242]:     return method(cnx, *args, **kwargs)
feb 19 14:31:01 Talento-ubuntu-s-2vcpu-4gb-120gb-intel-sfo2-01 uvicorn[1272242]:            ^^^^^^^^^^^^^^^^^^^^^^^^^^^^
feb 19 14:31:01 Talento-ubuntu-s-2vcpu-4gb-120gb-intel-sfo2-01 uvicorn[1272242]:   File "/var/www/html/gestviaticos/gest-viaticos-panama-backend/venv/lib/python3.12/site-packages/mysql/connector/connection_cext.py", line 781, in cmd_query
feb 19 14:31:01 Talento-ubuntu-s-2vcpu-4gb-120gb-intel-sfo2-01 uvicorn[1272242]:     raise get_mysql_exception(
feb 19 14:31:01 Talento-ubuntu-s-2vcpu-4gb-120gb-intel-sfo2-01 uvicorn[1272242]: mysql.connector.errors.ProgrammingError: 1049 (42000): Unknown database 'aitsa_rrhh'
feb 19 14:31:01 Talento-ubuntu-s-2vcpu-4gb-120gb-intel-sfo2-01 uvicorn[1272242]: The above exception was the direct cause of the following exception:
feb 19 14:31:01 Talento-ubuntu-s-2vcpu-4gb-120gb-intel-sfo2-01 uvicorn[1272242]: Traceback (most recent call last):
feb 19 14:31:01 Talento-ubuntu-s-2vcpu-4gb-120gb-intel-sfo2-01 uvicorn[1272242]:   File "/var/www/html/gestviaticos/gest-viaticos-panama-backend/venv/lib/python3.12/site-packages/uvicorn/protocols/http/h11_impl.py", line 403, in run_asgi
feb 19 14:31:01 Talento-ubuntu-s-2vcpu-4gb-120gb-intel-sfo2-01 uvicorn[1272242]:     result = await app(  # type: ignore[func-returns-value]
feb 19 14:31:01 Talento-ubuntu-s-2vcpu-4gb-120gb-intel-sfo2-01 uvicorn[1272242]:              ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
feb 19 14:31:01 Talento-ubuntu-s-2vcpu-4gb-120gb-intel-sfo2-01 uvicorn[1272242]:   File "/var/www/html/gestviaticos/gest-viaticos-panama-backend/venv/lib/python3.12/site-packages/uvicorn/middleware/proxy_headers.py", line 60, in __call__
feb 19 14:31:01 Talento-ubuntu-s-2vcpu-4gb-120gb-intel-sfo2-01 uvicorn[1272242]:     return await self.app(scope, receive, send)
feb 19 14:31:01 Talento-ubuntu-s-2vcpu-4gb-120gb-intel-sfo2-01 uvicorn[1272242]:            ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
feb 19 14:31:01 Talento-ubuntu-s-2vcpu-4gb-120gb-intel-sfo2-01 uvicorn[1272242]:   File "/var/www/html/gestviaticos/gest-viaticos-panama-backend/venv/lib/python3.12/site-packages/fastapi/applications.py", line 1054, in __call__
feb 19 14:31:01 Talento-ubuntu-s-2vcpu-4gb-120gb-intel-sfo2-01 uvicorn[1272242]:     await super().__call__(scope, receive, send)
feb 19 14:31:01 Talento-ubuntu-s-2vcpu-4gb-120gb-intel-sfo2-01 uvicorn[1272242]:   File "/var/www/html/gestviaticos/gest-viaticos-panama-backend/venv/lib/python3.12/site-packages/starlette/applications.py", line 112, in __call__
feb 19 14:31:01 Talento-ubuntu-s-2vcpu-4gb-120gb-intel-sfo2-01 uvicorn[1272242]:     await self.middleware_stack(scope, receive, send)
feb 19 14:31:01 Talento-ubuntu-s-2vcpu-4gb-120gb-intel-sfo2-01 uvicorn[1272242]:   File "/var/www/html/gestviaticos/gest-viaticos-panama-backend/venv/lib/python3.12/site-packages/starlette/middleware/errors.py", line 187, in __call__
feb 19 14:31:01 Talento-ubuntu-s-2vcpu-4gb-120gb-intel-sfo2-01 uvicorn[1272242]:     raise exc
feb 19 14:31:01 Talento-ubuntu-s-2vcpu-4gb-120gb-intel-sfo2-01 uvicorn[1272242]:   File "/var/www/html/gestviaticos/gest-viaticos-panama-backend/venv/lib/python3.12/site-packages/starlette/middleware/errors.py", line 165, in __call__
feb 19 14:31:01 Talento-ubuntu-s-2vcpu-4gb-120gb-intel-sfo2-01 uvicorn[1272242]:     await self.app(scope, receive, _send)
feb 19 14:31:01 Talento-ubuntu-s-2vcpu-4gb-120gb-intel-sfo2-01 uvicorn[1272242]:   File "/var/www/html/gestviaticos/gest-viaticos-panama-backend/venv/lib/python3.12/site-packages/starlette/middleware/cors.py", line 85, in __call__
feb 19 14:31:01 Talento-ubuntu-s-2vcpu-4gb-120gb-intel-sfo2-01 uvicorn[1272242]:     await self.app(scope, receive, send)
feb 19 14:31:01 Talento-ubuntu-s-2vcpu-4gb-120gb-intel-sfo2-01 uvicorn[1272242]:   File "/var/www/html/gestviaticos/gest-viaticos-panama-backend/venv/lib/python3.12/site-packages/starlette/middleware/exceptions.py", line 62, in __call__
feb 19 14:31:01 Talento-ubuntu-s-2vcpu-4gb-120gb-intel-sfo2-01 uvicorn[1272242]:     await wrap_app_handling_exceptions(self.app, conn)(scope, receive, send)
feb 19 14:31:01 Talento-ubuntu-s-2vcpu-4gb-120gb-intel-sfo2-01 uvicorn[1272242]:   File "/var/www/html/gestviaticos/gest-viaticos-panama-backend/venv/lib/python3.12/site-packages/starlette/_exception_handler.py", line 53, in wrapped_app
feb 19 14:31:01 Talento-ubuntu-s-2vcpu-4gb-120gb-intel-sfo2-01 uvicorn[1272242]:     raise exc
feb 19 14:31:01 Talento-ubuntu-s-2vcpu-4gb-120gb-intel-sfo2-01 uvicorn[1272242]:   File "/var/www/html/gestviaticos/gest-viaticos-panama-backend/venv/lib/python3.12/site-packages/starlette/_exception_handler.py", line 42, in wrapped_app
feb 19 14:31:01 Talento-ubuntu-s-2vcpu-4gb-120gb-intel-sfo2-01 uvicorn[1272242]:     await app(scope, receive, sender)
feb 19 14:31:01 Talento-ubuntu-s-2vcpu-4gb-120gb-intel-sfo2-01 uvicorn[1272242]:   File "/var/www/html/gestviaticos/gest-viaticos-panama-backend/venv/lib/python3.12/site-packages/starlette/routing.py", line 714, in __call__
feb 19 14:31:01 Talento-ubuntu-s-2vcpu-4gb-120gb-intel-sfo2-01 uvicorn[1272242]:     await self.middleware_stack(scope, receive, send)
feb 19 14:31:01 Talento-ubuntu-s-2vcpu-4gb-120gb-intel-sfo2-01 uvicorn[1272242]:   File "/var/www/html/gestviaticos/gest-viaticos-panama-backend/venv/lib/python3.12/site-packages/starlette/routing.py", line 734, in app
feb 19 14:31:01 Talento-ubuntu-s-2vcpu-4gb-120gb-intel-sfo2-01 uvicorn[1272242]:     await route.handle(scope, receive, send)
feb 19 14:31:01 Talento-ubuntu-s-2vcpu-4gb-120gb-intel-sfo2-01 uvicorn[1272242]:   File "/var/www/html/gestviaticos/gest-viaticos-panama-backend/venv/lib/python3.12/site-packages/starlette/routing.py", line 288, in handle
feb 19 14:31:01 Talento-ubuntu-s-2vcpu-4gb-120gb-intel-sfo2-01 uvicorn[1272242]:     await self.app(scope, receive, send)
feb 19 14:31:01 Talento-ubuntu-s-2vcpu-4gb-120gb-intel-sfo2-01 uvicorn[1272242]:   File "/var/www/html/gestviaticos/gest-viaticos-panama-backend/venv/lib/python3.12/site-packages/starlette/routing.py", line 76, in app
feb 19 14:31:01 Talento-ubuntu-s-2vcpu-4gb-120gb-intel-sfo2-01 uvicorn[1272242]:     await wrap_app_handling_exceptions(app, request)(scope, receive, send)
feb 19 14:31:01 Talento-ubuntu-s-2vcpu-4gb-120gb-intel-sfo2-01 uvicorn[1272242]:   File "/var/www/html/gestviaticos/gest-viaticos-panama-backend/venv/lib/python3.12/site-packages/starlette/_exception_handler.py", line 53, in wrapped_app
feb 19 14:31:01 Talento-ubuntu-s-2vcpu-4gb-120gb-intel-sfo2-01 uvicorn[1272242]:     raise exc
feb 19 14:31:01 Talento-ubuntu-s-2vcpu-4gb-120gb-intel-sfo2-01 uvicorn[1272242]:   File "/var/www/html/gestviaticos/gest-viaticos-panama-backend/venv/lib/python3.12/site-packages/starlette/_exception_handler.py", line 42, in wrapped_app
feb 19 14:31:01 Talento-ubuntu-s-2vcpu-4gb-120gb-intel-sfo2-01 uvicorn[1272242]:     await app(scope, receive, sender)
feb 19 14:31:01 Talento-ubuntu-s-2vcpu-4gb-120gb-intel-sfo2-01 uvicorn[1272242]:   File "/var/www/html/gestviaticos/gest-viaticos-panama-backend/venv/lib/python3.12/site-packages/starlette/routing.py", line 73, in app
feb 19 14:31:01 Talento-ubuntu-s-2vcpu-4gb-120gb-intel-sfo2-01 uvicorn[1272242]:     response = await f(request)
feb 19 14:31:01 Talento-ubuntu-s-2vcpu-4gb-120gb-intel-sfo2-01 uvicorn[1272242]:                ^^^^^^^^^^^^^^^^
feb 19 14:31:01 Talento-ubuntu-s-2vcpu-4gb-120gb-intel-sfo2-01 uvicorn[1272242]:   File "/var/www/html/gestviaticos/gest-viaticos-panama-backend/venv/lib/python3.12/site-packages/fastapi/routing.py", line 301, in app
feb 19 14:31:01 Talento-ubuntu-s-2vcpu-4gb-120gb-intel-sfo2-01 uvicorn[1272242]:     raw_response = await run_endpoint_function(
feb 19 14:31:01 Talento-ubuntu-s-2vcpu-4gb-120gb-intel-sfo2-01 uvicorn[1272242]:                    ^^^^^^^^^^^^^^^^^^^^^^^^^^^^
feb 19 14:31:01 Talento-ubuntu-s-2vcpu-4gb-120gb-intel-sfo2-01 uvicorn[1272242]:   File "/var/www/html/gestviaticos/gest-viaticos-panama-backend/venv/lib/python3.12/site-packages/fastapi/routing.py", line 214, in run_endpoint_function
feb 19 14:31:01 Talento-ubuntu-s-2vcpu-4gb-120gb-intel-sfo2-01 uvicorn[1272242]:     return await run_in_threadpool(dependant.call, **values)
feb 19 14:31:01 Talento-ubuntu-s-2vcpu-4gb-120gb-intel-sfo2-01 uvicorn[1272242]:            ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
feb 19 14:31:01 Talento-ubuntu-s-2vcpu-4gb-120gb-intel-sfo2-01 uvicorn[1272242]:   File "/var/www/html/gestviaticos/gest-viaticos-panama-backend/venv/lib/python3.12/site-packages/starlette/concurrency.py", line 37, in run_in_threadpool
feb 19 14:31:01 Talento-ubuntu-s-2vcpu-4gb-120gb-intel-sfo2-01 uvicorn[1272242]:     return await anyio.to_thread.run_sync(func)
feb 19 14:31:01 Talento-ubuntu-s-2vcpu-4gb-120gb-intel-sfo2-01 uvicorn[1272242]:            ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
feb 19 14:31:01 Talento-ubuntu-s-2vcpu-4gb-120gb-intel-sfo2-01 uvicorn[1272242]:   File "/var/www/html/gestviaticos/gest-viaticos-panama-backend/venv/lib/python3.12/site-packages/anyio/to_thread.py", line 63, in run_sync
feb 19 14:31:01 Talento-ubuntu-s-2vcpu-4gb-120gb-intel-sfo2-01 uvicorn[1272242]:     return await get_async_backend().run_sync_in_worker_thread(
feb 19 14:31:01 Talento-ubuntu-s-2vcpu-4gb-120gb-intel-sfo2-01 uvicorn[1272242]:            ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
feb 19 14:31:01 Talento-ubuntu-s-2vcpu-4gb-120gb-intel-sfo2-01 uvicorn[1272242]:   File "/var/www/html/gestviaticos/gest-viaticos-panama-backend/venv/lib/python3.12/site-packages/anyio/_backends/_asyncio.py", line 2502, in run_sync_in_worker_thread
feb 19 14:31:01 Talento-ubuntu-s-2vcpu-4gb-120gb-intel-sfo2-01 uvicorn[1272242]:     return await future
feb 19 14:31:01 Talento-ubuntu-s-2vcpu-4gb-120gb-intel-sfo2-01 uvicorn[1272242]:            ^^^^^^^^^^^^
feb 19 14:31:01 Talento-ubuntu-s-2vcpu-4gb-120gb-intel-sfo2-01 uvicorn[1272242]:   File "/var/www/html/gestviaticos/gest-viaticos-panama-backend/venv/lib/python3.12/site-packages/anyio/_backends/_asyncio.py", line 986, in run
feb 19 14:31:01 Talento-ubuntu-s-2vcpu-4gb-120gb-intel-sfo2-01 uvicorn[1272242]:     result = context.run(func, *args)
feb 19 14:31:01 Talento-ubuntu-s-2vcpu-4gb-120gb-intel-sfo2-01 uvicorn[1272242]:              ^^^^^^^^^^^^^^^^^^^^^^^^
feb 19 14:31:01 Talento-ubuntu-s-2vcpu-4gb-120gb-intel-sfo2-01 uvicorn[1272242]:   File "/var/www/html/gestviaticos/gest-viaticos-panama-backend/app/api/v1/employee_requests.py", line 56, in get_employee_dashboard
feb 19 14:31:01 Talento-ubuntu-s-2vcpu-4gb-120gb-intel-sfo2-01 uvicorn[1272242]:     result = db_rrhh.execute(text("""
feb 19 14:31:01 Talento-ubuntu-s-2vcpu-4gb-120gb-intel-sfo2-01 uvicorn[1272242]:              ^^^^^^^^^^^^^^^^^^^^^^^^
feb 19 14:31:01 Talento-ubuntu-s-2vcpu-4gb-120gb-intel-sfo2-01 uvicorn[1272242]:   File "/var/www/html/gestviaticos/gest-viaticos-panama-backend/venv/lib/python3.12/site-packages/sqlalchemy/orm/session.py", line 2365, in execute
feb 19 14:31:01 Talento-ubuntu-s-2vcpu-4gb-120gb-intel-sfo2-01 uvicorn[1272242]:     return self._execute_internal(
feb 19 14:31:01 Talento-ubuntu-s-2vcpu-4gb-120gb-intel-sfo2-01 uvicorn[1272242]:            ^^^^^^^^^^^^^^^^^^^^^^^
feb 19 14:31:01 Talento-ubuntu-s-2vcpu-4gb-120gb-intel-sfo2-01 uvicorn[1272242]:   File "/var/www/html/gestviaticos/gest-viaticos-panama-backend/venv/lib/python3.12/site-packages/sqlalchemy/orm/session.py", line 2260, in _execute_internal
feb 19 14:31:01 Talento-ubuntu-s-2vcpu-4gb-120gb-intel-sfo2-01 uvicorn[1272242]:     result = conn.execute(
feb 19 14:31:01 Talento-ubuntu-s-2vcpu-4gb-120gb-intel-sfo2-01 uvicorn[1272242]:              ^^^^^^^^^^^^^
feb 19 14:31:01 Talento-ubuntu-s-2vcpu-4gb-120gb-intel-sfo2-01 uvicorn[1272242]:   File "/var/www/html/gestviaticos/gest-viaticos-panama-backend/venv/lib/python3.12/site-packages/sqlalchemy/engine/base.py", line 1415, in execute
feb 19 14:31:01 Talento-ubuntu-s-2vcpu-4gb-120gb-intel-sfo2-01 uvicorn[1272242]:     return meth(
feb 19 14:31:01 Talento-ubuntu-s-2vcpu-4gb-120gb-intel-sfo2-01 uvicorn[1272242]:            ^^^^^
feb 19 14:31:01 Talento-ubuntu-s-2vcpu-4gb-120gb-intel-sfo2-01 uvicorn[1272242]:   File "/var/www/html/gestviaticos/gest-viaticos-panama-backend/venv/lib/python3.12/site-packages/sqlalchemy/sql/elements.py", line 523, in _execute_on_connection
feb 19 14:31:01 Talento-ubuntu-s-2vcpu-4gb-120gb-intel-sfo2-01 uvicorn[1272242]:     return connection._execute_clauseelement(
feb 19 14:31:01 Talento-ubuntu-s-2vcpu-4gb-120gb-intel-sfo2-01 uvicorn[1272242]:            ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
feb 19 14:31:01 Talento-ubuntu-s-2vcpu-4gb-120gb-intel-sfo2-01 uvicorn[1272242]:   File "/var/www/html/gestviaticos/gest-viaticos-panama-backend/venv/lib/python3.12/site-packages/sqlalchemy/engine/base.py", line 1637, in _execute_clauseelement
feb 19 14:31:01 Talento-ubuntu-s-2vcpu-4gb-120gb-intel-sfo2-01 uvicorn[1272242]:     ret = self._execute_context(
feb 19 14:31:01 Talento-ubuntu-s-2vcpu-4gb-120gb-intel-sfo2-01 uvicorn[1272242]:           ^^^^^^^^^^^^^^^^^^^^^^
feb 19 14:31:01 Talento-ubuntu-s-2vcpu-4gb-120gb-intel-sfo2-01 uvicorn[1272242]:   File "/var/www/html/gestviaticos/gest-viaticos-panama-backend/venv/lib/python3.12/site-packages/sqlalchemy/engine/base.py", line 1842, in _execute_context
feb 19 14:31:01 Talento-ubuntu-s-2vcpu-4gb-120gb-intel-sfo2-01 uvicorn[1272242]:     return self._exec_single_context(
feb 19 14:31:01 Talento-ubuntu-s-2vcpu-4gb-120gb-intel-sfo2-01 uvicorn[1272242]:            ^^^^^^^^^^^^^^^^^^^^^^^^^^
feb 19 14:31:01 Talento-ubuntu-s-2vcpu-4gb-120gb-intel-sfo2-01 uvicorn[1272242]:   File "/var/www/html/gestviaticos/gest-viaticos-panama-backend/venv/lib/python3.12/site-packages/sqlalchemy/engine/base.py", line 1982, in _exec_single_context
feb 19 14:31:01 Talento-ubuntu-s-2vcpu-4gb-120gb-intel-sfo2-01 uvicorn[1272242]:     self._handle_dbapi_exception(
feb 19 14:31:01 Talento-ubuntu-s-2vcpu-4gb-120gb-intel-sfo2-01 uvicorn[1272242]:   File "/var/www/html/gestviaticos/gest-viaticos-panama-backend/venv/lib/python3.12/site-packages/sqlalchemy/engine/base.py", line 2351, in _handle_dbapi_exception
feb 19 14:31:01 Talento-ubuntu-s-2vcpu-4gb-120gb-intel-sfo2-01 uvicorn[1272242]:     raise sqlalchemy_exception.with_traceback(exc_info[2]) from e
feb 19 14:31:01 Talento-ubuntu-s-2vcpu-4gb-120gb-intel-sfo2-01 uvicorn[1272242]:   File "/var/www/html/gestviaticos/gest-viaticos-panama-backend/venv/lib/python3.12/site-packages/sqlalchemy/engine/base.py", line 1963, in _exec_single_context
feb 19 14:31:01 Talento-ubuntu-s-2vcpu-4gb-120gb-intel-sfo2-01 uvicorn[1272242]:     self.dialect.do_execute(
feb 19 14:31:01 Talento-ubuntu-s-2vcpu-4gb-120gb-intel-sfo2-01 uvicorn[1272242]:   File "/var/www/html/gestviaticos/gest-viaticos-panama-backend/venv/lib/python3.12/site-packages/sqlalchemy/engine/default.py", line 943, in do_execute
feb 19 14:31:01 Talento-ubuntu-s-2vcpu-4gb-120gb-intel-sfo2-01 uvicorn[1272242]:     cursor.execute(statement, parameters)
feb 19 14:31:01 Talento-ubuntu-s-2vcpu-4gb-120gb-intel-sfo2-01 uvicorn[1272242]:   File "/var/www/html/gestviaticos/gest-viaticos-panama-backend/venv/lib/python3.12/site-packages/mysql/connector/cursor_cext.py", line 356, in execute
feb 19 14:31:01 Talento-ubuntu-s-2vcpu-4gb-120gb-intel-sfo2-01 uvicorn[1272242]:     self._connection.cmd_query(
feb 19 14:31:01 Talento-ubuntu-s-2vcpu-4gb-120gb-intel-sfo2-01 uvicorn[1272242]:   File "/var/www/html/gestviaticos/gest-viaticos-panama-backend/venv/lib/python3.12/site-packages/mysql/connector/opentelemetry/context_propagation.py", line 97, in wrapper
feb 19 14:31:01 Talento-ubuntu-s-2vcpu-4gb-120gb-intel-sfo2-01 uvicorn[1272242]:     return method(cnx, *args, **kwargs)
feb 19 14:31:01 Talento-ubuntu-s-2vcpu-4gb-120gb-intel-sfo2-01 uvicorn[1272242]:            ^^^^^^^^^^^^^^^^^^^^^^^^^^^^
feb 19 14:31:01 Talento-ubuntu-s-2vcpu-4gb-120gb-intel-sfo2-01 uvicorn[1272242]:   File "/var/www/html/gestviaticos/gest-viaticos-panama-backend/venv/lib/python3.12/site-packages/mysql/connector/connection_cext.py", line 781, in cmd_query
feb 19 14:31:01 Talento-ubuntu-s-2vcpu-4gb-120gb-intel-sfo2-01 uvicorn[1272242]:     raise get_mysql_exception(
feb 19 14:31:01 Talento-ubuntu-s-2vcpu-4gb-120gb-intel-sfo2-01 uvicorn[1272242]: sqlalchemy.exc.ProgrammingError: (mysql.connector.errors.ProgrammingError) 1049 (42000): Unknown database 'aitsa_rrhh'
feb 19 14:31:01 Talento-ubuntu-s-2vcpu-4gb-120gb-intel-sfo2-01 uvicorn[1272242]: [SQL:
feb 19 14:31:01 Talento-ubuntu-s-2vcpu-4gb-120gb-intel-sfo2-01 uvicorn[1272242]:         SELECT personal_id FROM aitsa_rrhh.nompersonal
feb 19 14:31:01 Talento-ubuntu-s-2vcpu-4gb-120gb-intel-sfo2-01 uvicorn[1272242]:         WHERE cedula = %(cedula)s AND estado != 'De Baja'
feb 19 14:31:01 Talento-ubuntu-s-2vcpu-4gb-120gb-intel-sfo2-01 uvicorn[1272242]:     ]
feb 19 14:31:01 Talento-ubuntu-s-2vcpu-4gb-120gb-intel-sfo2-01 uvicorn[1272242]: [parameters: {'cedula': 'E-8-157323'}]
feb 19 14:31:01 Talento-ubuntu-s-2vcpu-4gb-120gb-intel-sfo2-01 uvicorn[1272242]: (Background on this error at: https://sqlalche.me/e/20/f405)
feb 19 14:31:01 Talento-ubuntu-s-2vcpu-4gb-120gb-intel-sfo2-01 uvicorn[1272242]: INFO:     181.53.96.10:0 - "GET /api/v1/missions/employee?size=5 HTTP/1.1" 500 Internal Server Error
