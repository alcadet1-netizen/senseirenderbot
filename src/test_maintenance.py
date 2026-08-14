import sys
import os
sys.path.append(os.getcwd())

try:
    from src.services.maintenance_service import MaintenanceService
    print("[OK] MaintenanceService imported")

    from src.bot.middlewares.maintenance import MaintenanceMiddleware
    print("[OK] MaintenanceMiddleware imported")

    from src.bot.handlers.maintenance import router
    print("[OK] Maintenance router imported")

    # Test service state
    MaintenanceService.enable(reason="Test")
    assert MaintenanceService.is_enabled()
    print("[OK] MaintenanceService enable works")

    MaintenanceService.disable()
    assert not MaintenanceService.is_enabled()
    print("[OK] MaintenanceService disable works")

except ImportError as e:
    print(f"[ERROR] ImportError: {e}")
    sys.exit(1)
except Exception as e:
    print(f"[ERROR] Error: {e}")
    sys.exit(1)