# app/services/calculation_engine.py

from typing import List, Dict, Any, Optional, Tuple
from decimal import Decimal, ROUND_HALF_UP
from datetime import datetime, date, time
from sqlalchemy.orm import Session

from app.models.configuration import ConfiguracionSistema
from app.models.enums import CategoriaBeneficiario, TipoViaje, TipoTransporte
from app.core.exceptions import ConfigurationException, ValidationException


class CalculationEngine:
    """
    Centralized calculation engine for viáticos, transportation costs,
    and other financial calculations following AITSA business rules.
    """
    
    def __init__(self, db: Session):
        self.db = db
        self._config_cache = {}
        self._load_configuration()
    
    def _load_configuration(self):
        """Load all system configurations into cache for performance"""
        configs = self.db.query(ConfiguracionSistema).all()
        for config in configs:
            self._config_cache[config.clave] = config.valor
    
    def _get_config_decimal(self, key: str, default: str = "0.00") -> Decimal:
        """Get configuration value as Decimal"""
        value = self._config_cache.get(key, default)
        try:
            return Decimal(str(value))
        except:
            raise ConfigurationException(f"Invalid decimal configuration for {key}: {value}")
    
    def _get_config_int(self, key: str, default: str = "0") -> int:
        """Get configuration value as integer"""
        value = self._config_cache.get(key, default)
        try:
            return int(value)
        except:
            raise ConfigurationException(f"Invalid integer configuration for {key}: {value}")
    
    def _get_config_time(self, key: str, default: str = "00:00") -> time:
        """Get configuration value as time"""
        value = self._config_cache.get(key, default)
        try:
            hour, minute = value.split(":")
            return time(int(hour), int(minute))
        except:
            raise ConfigurationException(f"Invalid time configuration for {key}: {value}")
    
    def calculate_daily_viaticos(
        self,
        categoria: CategoriaBeneficiario,
        tipo_viaje: TipoViaje,
        region_exterior: Optional[str],
        fecha: date,
        hora_salida: Optional[time] = None,
        hora_llegada: Optional[time] = None,
        include_hospedaje: bool = True
    ) -> Dict[str, Decimal]:
        """
        Calculate daily viáticos based on category, destination, and meal times.
        
        Returns breakdown of: desayuno, almuerzo, cena, hospedaje, total
        """
        
        # Get base rates for category
        if categoria == CategoriaBeneficiario.TITULAR:
            base_viatico = self._get_config_decimal("TARIFA_VIATICO_TITULAR_NACIONAL")
            base_hospedaje = self._get_config_decimal("TARIFA_HOSPEDAJE_TITULAR_NACIONAL")
        elif categoria == CategoriaBeneficiario.OTROS_SERVIDORES:
            base_viatico = self._get_config_decimal("TARIFA_VIATICO_OTROS_SERVIDORES_NACIONAL")
            base_hospedaje = self._get_config_decimal("TARIFA_HOSPEDAJE_OTROS_SERVIDORES_NACIONAL")
        else:  # OTRAS_PERSONAS
            base_viatico = self._get_config_decimal("TARIFA_VIATICO_OTRAS_PERSONAS_NACIONAL")
            base_hospedaje = self._get_config_decimal("TARIFA_HOSPEDAJE_OTRAS_PERSONAS_NACIONAL")
        
        # Apply international increment if applicable
        if tipo_viaje == TipoViaje.INTERNACIONAL and region_exterior:
            increment_key = f"INCREMENTO_{region_exterior.upper().replace(' ', '_')}"
            increment_pct = self._get_config_decimal(increment_key, "0.00")
            
            if increment_pct > 0:
                multiplier = Decimal("1.00") + (increment_pct / Decimal("100.00"))
                base_viatico *= multiplier
                base_hospedaje *= multiplier
        
        # Get meal percentages
        pct_desayuno = self._get_config_decimal("PORCENTAJE_DESAYUNO") / Decimal("100.00")
        pct_almuerzo = self._get_config_decimal("PORCENTAJE_ALMUERZO") / Decimal("100.00")
        pct_cena = self._get_config_decimal("PORCENTAJE_CENA") / Decimal("100.00")
        
        # Get cutoff times
        corte_desayuno = self._get_config_time("HORA_CORTE_DESAYUNO")
        corte_almuerzo = self._get_config_time("HORA_CORTE_ALMUERZO")
        corte_cena = self._get_config_time("HORA_CORTE_CENA")
        
        # Calculate individual meals based on travel times
        desayuno = Decimal("0.00")
        almuerzo = Decimal("0.00")
        cena = Decimal("0.00")
        
        # If no specific times provided, include all meals
        if not hora_salida or not hora_llegada:
            desayuno = (base_viatico * pct_desayuno).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            almuerzo = (base_viatico * pct_almuerzo).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            cena = (base_viatico * pct_cena).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        else:
            # Include breakfast if departure is before cutoff
            if hora_salida <= corte_desayuno:
                desayuno = (base_viatico * pct_desayuno).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            
            # Include lunch if travel spans lunch time
            if hora_salida <= corte_almuerzo <= hora_llegada:
                almuerzo = (base_viatico * pct_almuerzo).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            
            # Include dinner if arrival is after cutoff
            if hora_llegada >= corte_cena:
                cena = (base_viatico * pct_cena).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        
        # Calculate lodging
        hospedaje = base_hospedaje if include_hospedaje else Decimal("0.00")
        
        total = desayuno + almuerzo + cena + hospedaje
        
        return {
            "desayuno": desayuno,
            "almuerzo": almuerzo,
            "cena": cena,
            "hospedaje": hospedaje,
            "total": total,
            "base_rate": base_viatico,
            "applied_increment": increment_pct if tipo_viaje == TipoViaje.INTERNACIONAL else Decimal("0.00")
        }
    
    def calculate_transportation_cost(
        self,
        tipo_transporte: TipoTransporte,
        origen: str,
        destino: str,
        distance_km: Optional[float] = None,
        is_official_transport: bool = False
    ) -> Decimal:
        """
        Calculate transportation costs based on type and distance.
        """
        
        if is_official_transport:
            return Decimal("0.00")  # No cost for official transport
        
        if tipo_transporte == TipoTransporte.TERRESTRE:
            if distance_km is None:
                raise ValidationException("Distance in km is required for terrestrial transport")
            
            rate_per_km = self._get_config_decimal("TARIFA_TRANSPORTE_TERRESTRE_KM")
            return (Decimal(str(distance_km)) * rate_per_km).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        
        elif tipo_transporte == TipoTransporte.AEREO:
            base_rate = self._get_config_decimal("TARIFA_TRANSPORTE_AEREO_NACIONAL")
            # TODO: Add logic for international flights with different rates
            return base_rate
        
        elif tipo_transporte in [TipoTransporte.ACUATICO, TipoTransporte.MARITIMO]:
            base_rate = self._get_config_decimal("TARIFA_TRANSPORTE_ACUATICO_BASE")
            return base_rate
        
        else:
            raise ValidationException(f"Unsupported transport type: {tipo_transporte}")
    
    def calculate_mission_total(
        self,
        items_viaticos: List[Dict[str, Any]],
        items_transporte: List[Dict[str, Any]],
        categoria_beneficiario: CategoriaBeneficiario,
        tipo_viaje: TipoViaje = TipoViaje.NACIONAL,
        region_exterior: Optional[str] = None
    ) -> Dict[str, Decimal]:
        """
        Calculate the total cost for a complete mission.
        """
        
        total_viaticos = Decimal("0.00")
        total_transporte = Decimal("0.00")
        
        # Calculate viáticos
        for item in items_viaticos:
            total_viaticos += Decimal(str(item.get("monto_desayuno", 0)))
            total_viaticos += Decimal(str(item.get("monto_almuerzo", 0)))
            total_viaticos += Decimal(str(item.get("monto_cena", 0)))
            total_viaticos += Decimal(str(item.get("monto_hospedaje", 0)))
        
        # Calculate transportation
        for item in items_transporte:
            total_transporte += Decimal(str(item.get("monto", 0)))
        
        total_mission = total_viaticos + total_transporte
        
        # Check if CGR refrendo is required
        monto_refrendo = self._get_config_decimal("MONTO_REFRENDO_CGR")
        requires_cgr_refrendo = total_mission >= monto_refrendo
        
        # Check if exceeds cash limit
        limite_efectivo = self._get_config_decimal("LIMITE_EFECTIVO_VIATICOS")
        exceeds_cash_limit = total_mission > limite_efectivo
        
        return {
            "total_viaticos": total_viaticos,
            "total_transporte": total_transporte,
            "total_mission": total_mission,
            "requires_cgr_refrendo": requires_cgr_refrendo,
            "exceeds_cash_limit": exceeds_cash_limit,
            "cgr_threshold": monto_refrendo,
            "cash_limit": limite_efectivo
        }
    
    def calculate_per_diem_for_period(
        self,
        fecha_inicio: date,
        fecha_fin: date,
        categoria: CategoriaBeneficiario,
        tipo_viaje: TipoViaje = TipoViaje.NACIONAL,
        region_exterior: Optional[str] = None,
        hora_salida: Optional[time] = None,
        hora_llegada: Optional[time] = None
    ) -> List[Dict[str, Any]]:
        """
        Calculate per diem for a complete period (multiple days).
        """
        
        items = []
        current_date = fecha_inicio
        
        while current_date <= fecha_fin:
            is_first_day = current_date == fecha_inicio
            is_last_day = current_date == fecha_fin
            
            # Adjust meal calculations for first and last days
            day_hora_salida = hora_salida if is_first_day else None
            day_hora_llegada = hora_llegada if is_last_day else None
            
            # Lodging not needed on the last day if returning same day
            include_lodging = not (is_last_day and fecha_inicio == fecha_fin)
            
            daily_calc = self.calculate_daily_viaticos(
                categoria=categoria,
                tipo_viaje=tipo_viaje,
                region_exterior=region_exterior,
                fecha=current_date,
                hora_salida=day_hora_salida,
                hora_llegada=day_hora_llegada,
                include_hospedaje=include_lodging
            )
            
            items.append({
                "fecha": current_date,
                "monto_desayuno": daily_calc["desayuno"],
                "monto_almuerzo": daily_calc["almuerzo"],
                "monto_cena": daily_calc["cena"],
                "monto_hospedaje": daily_calc["hospedaje"],
                "observaciones": f"Cálculo automático - {categoria.value}"
            })
            
            # Move to next day
            current_date = date(current_date.year, current_date.month, current_date.day + 1)
        
        return items
    
    def validate_mission_amounts(
        self,
        total_amount: Decimal,
        categoria: CategoriaBeneficiario,
        tipo_viaje: TipoViaje
    ) -> Dict[str, Any]:
        """
        Validate that mission amounts are within acceptable limits.
        """
        
        warnings = []
        errors = []
        
        # Check cash limit
        limite_efectivo = self._get_config_decimal("LIMITE_EFECTIVO_VIATICOS")
        if total_amount > limite_efectivo:
            warnings.append(f"Amount exceeds cash limit of B/. {limite_efectivo}")
        
        # Check CGR refrendo requirement
        monto_refrendo = self._get_config_decimal("MONTO_REFRENDO_CGR")
        if total_amount >= monto_refrendo:
            warnings.append(f"Amount requires CGR refrendo (≥ B/. {monto_refrendo})")
        
        # Additional business rule validations can be added here
        
        return {
            "is_valid": len(errors) == 0,
            "warnings": warnings,
            "errors": errors,
            "requires_cgr_refrendo": total_amount >= monto_refrendo,
            "exceeds_cash_limit": total_amount > limite_efectivo
        }
    
    def get_calculation_summary(self) -> Dict[str, Any]:
        """
        Get a summary of current calculation rates and rules.
        """
        
        return {
            "rates": {
                "titular_nacional": {
                    "viatico": self._get_config_decimal("TARIFA_VIATICO_TITULAR_NACIONAL"),
                    "hospedaje": self._get_config_decimal("TARIFA_HOSPEDAJE_TITULAR_NACIONAL")
                },
                "otros_servidores_nacional": {
                    "viatico": self._get_config_decimal("TARIFA_VIATICO_OTROS_SERVIDORES_NACIONAL"),
                    "hospedaje": self._get_config_decimal("TARIFA_HOSPEDAJE_OTROS_SERVIDORES_NACIONAL")
                },
                "otras_personas_nacional": {
                    "viatico": self._get_config_decimal("TARIFA_VIATICO_OTRAS_PERSONAS_NACIONAL"),
                    "hospedaje": self._get_config_decimal("TARIFA_HOSPEDAJE_OTRAS_PERSONAS_NACIONAL")
                }
            },
            "meal_percentages": {
                "desayuno": self._get_config_decimal("PORCENTAJE_DESAYUNO"),
                "almuerzo": self._get_config_decimal("PORCENTAJE_ALMUERZO"),
                "cena": self._get_config_decimal("PORCENTAJE_CENA")
            },
            "cutoff_times": {
                "desayuno": self._get_config_time("HORA_CORTE_DESAYUNO").strftime("%H:%M"),
                "almuerzo": self._get_config_time("HORA_CORTE_ALMUERZO").strftime("%H:%M"),
                "cena": self._get_config_time("HORA_CORTE_CENA").strftime("%H:%M")
            },
            "limits": {
                "efectivo_viaticos": self._get_config_decimal("LIMITE_EFECTIVO_VIATICOS"),
                "refrendo_cgr": self._get_config_decimal("MONTO_REFRENDO_CGR"),
                "dias_presentacion": self._get_config_int("DIAS_LIMITE_PRESENTACION")
            },
            "transport_rates": {
                "terrestre_km": self._get_config_decimal("TARIFA_TRANSPORTE_TERRESTRE_KM"),
                "aereo_nacional": self._get_config_decimal("TARIFA_TRANSPORTE_AEREO_NACIONAL"),
                "acuatico_base": self._get_config_decimal("TARIFA_TRANSPORTE_ACUATICO_BASE")
            },
            "international_increments": {
                "centroamerica": self._get_config_decimal("INCREMENTO_CENTROAMERICA"),
                "norteamerica": self._get_config_decimal("INCREMENTO_NORTEAMERICA"),
                "sudamerica": self._get_config_decimal("INCREMENTO_SUDAMERICA"),
                "europa": self._get_config_decimal("INCREMENTO_EUROPA"),
                "asia": self._get_config_decimal("INCREMENTO_ASIA"),
                "otros": self._get_config_decimal("INCREMENTO_OTROS")
            }
        }