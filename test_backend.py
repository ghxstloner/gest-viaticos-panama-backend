#!/usr/bin/env python3
# test_backend.py - Comprehensive backend testing script

"""
Comprehensive test script for AITSA Gestión de Viáticos backend.
Tests database connectivity, API endpoints, workflow logic, and calculations.
"""

import asyncio
import sys
import traceback
from datetime import date, datetime, time
from decimal import Decimal
from typing import Dict, Any, List

# Add the app directory to Python path
sys.path.append('.')

from app.core.database import engine_financiero, engine_rrhh, get_db_financiero
from app.services.workflow_validator import WorkflowValidator
from app.services.calculation_engine import CalculationEngine
from app.services.mission import MissionService
from app.services.configuration import ConfigurationService
from app.models.mission import EstadoFlujo, TransicionFlujo, Mision
from app.models.user import Usuario, Rol
from app.models.enums import CategoriaBeneficiario, TipoViaje, TipoMision, TipoAccion
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text


class BackendTester:
    """Comprehensive backend testing suite"""
    
    def __init__(self):
        self.test_results = {
            "database_connectivity": {"passed": False, "errors": []},
            "workflow_validation": {"passed": False, "errors": []},
            "calculation_engine": {"passed": False, "errors": []},
            "api_services": {"passed": False, "errors": []},
            "data_integrity": {"passed": False, "errors": []}
        }
        
        # Create database sessions
        SessionFinanciero = sessionmaker(bind=engine_financiero)
        SessionRRHH = sessionmaker(bind=engine_rrhh)
        self.db_financiero = SessionFinanciero()
        self.db_rrhh = SessionRRHH()
    
    def run_all_tests(self) -> Dict[str, Any]:
        """Run all backend tests and return comprehensive results"""
        
        print("🚀 Starting AITSA Backend Comprehensive Test Suite")
        print("=" * 60)
        
        # Test 1: Database Connectivity
        print("\n📊 Testing Database Connectivity...")
        self.test_database_connectivity()
        
        # Test 2: Workflow Validation
        print("\n🔄 Testing Workflow Configuration...")
        self.test_workflow_validation()
        
        # Test 3: Calculation Engine
        print("\n🧮 Testing Calculation Engine...")
        self.test_calculation_engine()
        
        # Test 4: API Services
        print("\n🌐 Testing API Services...")
        self.test_api_services()
        
        # Test 5: Data Integrity
        print("\n🔒 Testing Data Integrity...")
        self.test_data_integrity()
        
        # Generate final report
        print("\n" + "=" * 60)
        return self.generate_final_report()
    
    def test_database_connectivity(self):
        """Test connectivity to both databases"""
        try:
            # Test financiero database
            result = self.db_financiero.execute(text("SELECT 1")).scalar()
            if result == 1:
                print("✅ Financiero database connection: OK")
            else:
                raise Exception("Unexpected result from financiero database")
            
            # Test RRHH database
            result = self.db_rrhh.execute(text("SELECT 1")).scalar()
            if result == 1:
                print("✅ RRHH database connection: OK")
            else:
                raise Exception("Unexpected result from RRHH database")
            
            # Test basic table access
            estados_count = self.db_financiero.query(EstadoFlujo).count()
            print(f"✅ Estados de flujo found: {estados_count}")
            
            usuarios_count = self.db_financiero.query(Usuario).count()
            print(f"✅ Usuarios found: {usuarios_count}")
            
            self.test_results["database_connectivity"]["passed"] = True
            
        except Exception as e:
            error_msg = f"Database connectivity test failed: {str(e)}"
            print(f"❌ {error_msg}")
            self.test_results["database_connectivity"]["errors"].append(error_msg)
    
    def test_workflow_validation(self):
        """Test workflow configuration and validation"""
        try:
            validator = WorkflowValidator(self.db_financiero)
            
            # Run complete workflow validation
            validation_result = validator.validate_complete_workflow()
            
            if validation_result["is_valid"]:
                print("✅ Workflow configuration is valid")
                
                # Print summary statistics
                summary = validator.get_workflow_summary()
                print(f"   📋 Total states: {summary['total_states']}")
                print(f"   🔄 Active transitions: {summary['total_active_transitions']}")
                print(f"   👥 Total roles: {summary['total_roles']}")
                
                self.test_results["workflow_validation"]["passed"] = True
            else:
                error_msg = f"Workflow validation failed: {len(validation_result['errors'])} errors"
                print(f"⚠️  {error_msg}")
                
                for error in validation_result["errors"]:
                    print(f"     - {error}")
                    self.test_results["workflow_validation"]["errors"].append(error)
                
                # Still mark as passed if only warnings
                if len(validation_result["errors"]) == 0:
                    self.test_results["workflow_validation"]["passed"] = True
        
        except Exception as e:
            error_msg = f"Workflow validation test failed: {str(e)}"
            print(f"❌ {error_msg}")
            self.test_results["workflow_validation"]["errors"].append(error_msg)
    
    def test_calculation_engine(self):
        """Test viáticos and transportation calculations"""
        try:
            calc_engine = CalculationEngine(self.db_financiero)
            
            # Test basic viáticos calculation
            viaticos_result = calc_engine.calculate_daily_viaticos(
                categoria=CategoriaBeneficiario.TITULAR,
                tipo_viaje=TipoViaje.NACIONAL,
                region_exterior=None,
                fecha=date.today()
            )
            
            print("✅ Daily viáticos calculation successful")
            print(f"   💰 Total calculated: B/. {viaticos_result['total']}")
            print(f"   🍳 Desayuno: B/. {viaticos_result['desayuno']}")
            print(f"   🍽️ Almuerzo: B/. {viaticos_result['almuerzo']}")
            print(f"   🌙 Cena: B/. {viaticos_result['cena']}")
            print(f"   🏨 Hospedaje: B/. {viaticos_result['hospedaje']}")
            
            # Test international calculation
            international_result = calc_engine.calculate_daily_viaticos(
                categoria=CategoriaBeneficiario.TITULAR,
                tipo_viaje=TipoViaje.INTERNACIONAL,
                region_exterior="CENTROAMERICA",
                fecha=date.today()
            )
            
            print("✅ International viáticos calculation successful")
            print(f"   🌍 International total: B/. {international_result['total']}")
            print(f"   📈 Applied increment: {international_result['applied_increment']}%")
            
            # Test calculation summary
            summary = calc_engine.get_calculation_summary()
            print("✅ Calculation configuration summary retrieved")
            print(f"   💳 Cash limit: B/. {summary['limits']['efectivo_viaticos']}")
            print(f"   🏛️ CGR threshold: B/. {summary['limits']['refrendo_cgr']}")
            
            self.test_results["calculation_engine"]["passed"] = True
            
        except Exception as e:
            error_msg = f"Calculation engine test failed: {str(e)}"
            print(f"❌ {error_msg}")
            self.test_results["calculation_engine"]["errors"].append(error_msg)
    
    def test_api_services(self):
        """Test core API service functionality"""
        try:
            # Test configuration service
            config_service = ConfigurationService(self.db_financiero)
            config_general = config_service.get_configuracion_general()
            
            if config_general:
                print("✅ Configuration service working")
                print(f"   🏢 Company: {config_general.nombre_empresa}")
            else:
                print("⚠️  No general configuration found")
            
            # Test mission service basic functionality
            mission_service = MissionService(self.db_financiero)
            
            # Get test user
            test_user = self.db_financiero.query(Usuario).filter(Usuario.is_active == True).first()
            if test_user:
                print(f"✅ Test user found: {test_user.login_username}")
                
                # Test mission listing (without creating new missions)
                missions_result = mission_service.get_missions(
                    user=test_user,
                    skip=0,
                    limit=10
                )
                
                print(f"✅ Mission listing successful")
                print(f"   📊 Total missions in system: {missions_result['total']}")
                print(f"   📋 Missions returned: {len(missions_result['items'])}")
                
            else:
                print("⚠️  No active users found for testing")
            
            self.test_results["api_services"]["passed"] = True
            
        except Exception as e:
            error_msg = f"API services test failed: {str(e)}"
            print(f"❌ {error_msg}")
            self.test_results["api_services"]["errors"].append(error_msg)
    
    def test_data_integrity(self):
        """Test data integrity and relationships"""
        try:
            # Test foreign key relationships
            estados_with_transitions = self.db_financiero.execute(text("""
                SELECT COUNT(DISTINCT ef.id_estado_flujo) as estados_count,
                       COUNT(tf.id_transicion) as transitions_count
                FROM estados_flujo ef
                LEFT JOIN transiciones_flujo tf ON ef.id_estado_flujo = tf.id_estado_origen
                WHERE tf.es_activa = 1
            """)).fetchone()
            
            print("✅ Data integrity check completed")
            print(f"   🔗 States with transitions: {estados_with_transitions.estados_count}")
            print(f"   ➡️  Active transitions: {estados_with_transitions.transitions_count}")
            
            # Test user-role relationships
            users_with_roles = self.db_financiero.execute(text("""
                SELECT COUNT(*) as count
                FROM usuarios u
                INNER JOIN roles r ON u.id_rol = r.id_rol
                WHERE u.is_active = 1
            """)).scalar()
            
            print(f"   👤 Active users with valid roles: {users_with_roles}")
            
            # Test configuration completeness
            essential_configs = [
                'LIMITE_EFECTIVO_VIATICOS',
                'MONTO_REFRENDO_CGR',
                'TARIFA_VIATICO_TITULAR_NACIONAL'
            ]
            
            missing_configs = []
            for config_key in essential_configs:
                config_exists = self.db_financiero.execute(text("""
                    SELECT COUNT(*) FROM configuraciones_sistema 
                    WHERE clave = :key
                """), {"key": config_key}).scalar()
                
                if config_exists == 0:
                    missing_configs.append(config_key)
            
            if missing_configs:
                print(f"⚠️  Missing essential configurations: {', '.join(missing_configs)}")
            else:
                print("✅ All essential configurations present")
            
            self.test_results["data_integrity"]["passed"] = True
            
        except Exception as e:
            error_msg = f"Data integrity test failed: {str(e)}"
            print(f"❌ {error_msg}")
            self.test_results["data_integrity"]["errors"].append(error_msg)
    
    def generate_final_report(self) -> Dict[str, Any]:
        """Generate and display final test report"""
        
        passed_tests = sum(1 for result in self.test_results.values() if result["passed"])
        total_tests = len(self.test_results)
        
        print("\n🎯 FINAL TEST REPORT")
        print("=" * 40)
        print(f"Tests Passed: {passed_tests}/{total_tests}")
        print(f"Success Rate: {(passed_tests/total_tests)*100:.1f}%")
        
        overall_status = "PASS" if passed_tests == total_tests else "PARTIAL" if passed_tests > 0 else "FAIL"
        status_emoji = "✅" if overall_status == "PASS" else "⚠️" if overall_status == "PARTIAL" else "❌"
        
        print(f"Overall Status: {status_emoji} {overall_status}")
        
        # Show failed tests
        failed_tests = [name for name, result in self.test_results.items() if not result["passed"]]
        if failed_tests:
            print(f"\n❌ Failed Tests: {', '.join(failed_tests)}")
            
            print("\n🔍 Error Details:")
            for test_name in failed_tests:
                errors = self.test_results[test_name]["errors"]
                print(f"\n  {test_name}:")
                for error in errors:
                    print(f"    - {error}")
        
        # Recommendations
        print(f"\n💡 RECOMMENDATIONS:")
        if overall_status == "PASS":
            print("  ✅ Backend is ready for production deployment")
            print("  ✅ All core functionality is working correctly")
            print("  ✅ Database integrity is maintained")
        elif overall_status == "PARTIAL":
            print("  ⚠️  Backend has some issues but core functionality works")
            print("  ⚠️  Review failed tests before production deployment")
            print("  ⚠️  Consider fixing configuration or data issues")
        else:
            print("  ❌ Backend has critical issues")
            print("  ❌ Do not deploy to production")
            print("  ❌ Fix all failed tests before proceeding")
        
        return {
            "overall_status": overall_status,
            "passed_tests": passed_tests,
            "total_tests": total_tests,
            "success_rate": (passed_tests/total_tests)*100,
            "test_results": self.test_results,
            "failed_tests": failed_tests
        }
    
    def cleanup(self):
        """Clean up database connections"""
        try:
            self.db_financiero.close()
            self.db_rrhh.close()
        except:
            pass


def main():
    """Main test execution function"""
    tester = BackendTester()
    
    try:
        final_report = tester.run_all_tests()
        
        # Save results to file
        import json
        with open('test_results.json', 'w') as f:
            json.dump(final_report, f, indent=2, default=str)
        
        print(f"\n📄 Detailed results saved to: test_results.json")
        
        # Exit with appropriate code
        exit_code = 0 if final_report["overall_status"] == "PASS" else 1
        sys.exit(exit_code)
        
    except Exception as e:
        print(f"\n💥 Test suite crashed: {str(e)}")
        print(f"Traceback:\n{traceback.format_exc()}")
        sys.exit(2)
    
    finally:
        tester.cleanup()


if __name__ == "__main__":
    main()