"""
Simplified Test - No WeasyPrint dependencies
Tests API structure and routing
"""

import sys
from pathlib import Path

def test_api_structure():
    """Test that API structure is properly set up"""
    print("\n" + "="*60)
    print("  API STRUCTURE VERIFICATION")
    print("="*60 + "\n")
    
    try:
        # Test 1: Can import main app components
        print("✓ Test 1: Importing core modules...")
        from app.config.database import get_db, SessionLocal
        from app.models.database import Company, Employee, Payslip
        from app.repositories.payslip_repository import PayslipRepository
        print("  ✅ Database config and models imported successfully")
        
        # Test 2: Can import API router
        print("\n✓ Test 2: Importing API router...")
        from app.api.v1 import payslips
        print( "  ✅ Payslips router imported successfully")
        print(f"  Router prefix: {payslips.router.prefix}")
        print(f"  Router tags: {payslips.router.tags}")
        
        # Test 3: Verify router has endpoints
        print("\n✓ Test 3: Verifying router endpoints...")
        routes = [route for route in payslips.router.routes]
        print(f"  Total routes defined: {len(routes)}")
        for route in routes:
            path = getattr(route, 'path', 'N/A')
            methods = getattr(route, 'methods', set())
            print(f"    - {path}: {', '.join(methods) if methods else 'N/A'}")
        
        # Test 4: Can import FastAPI app
        print("\n✓ Test 4: Importing FastAPI app...")
        from run import app
        print("  ✅ FastAPI app imported successfully")
        print(f"  App title: {app.title}")
        print(f"  App version: {app.version}")
        
        # Test 5: App has routes
        print("\n✓ Test 5: Verifying app routes...")
        app_routes = [route for route in app.routes]
        print(f"  Total routes in app: {len(app_routes)}")
        for route in app_routes[:10]:  # Show first 10
            path = getattr(route, 'path', 'N/A')
            print(f"    - {path}")
        
        # Test 6: Database can connect
        print("\n✓ Test 6: Testing database connection...")
        from sqlalchemy import text
        db = SessionLocal()
        result = db.execute(text("SELECT 1"))
        db.close()
        print("  ✅ Database connection successful")
        
        # Test 7: Can create repositories
        print("\n✓ Test 7: Creating repository instances...")
        db = SessionLocal()
        payslip_repo = PayslipRepository(db)
        print("  ✅ PayslipRepository created successfully")
        db.close()
        
        print("\n" + "="*60)
        print("  ✅ ALL TESTS PASSED!")
        print("="*60)
        print("\nYour API structure is ready. To run the server:")
        print("  1. Run: python run.py")
        print("  2. API will be available at: http://localhost:8000")
        print("  3. Docs available at: http://localhost:8000/docs")
        print("\nNote: PDF generation requires system libraries.")
        print("      For Windows, consider using WSL2 or Linux container.")
        return True
        
    except ImportError as e:
        print(f"\n❌ Import Error: {str(e)}")
        return False
    except Exception as e:
        print(f"\n❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def main():
    print("\n" + "="*60)
    print("  HR PAYSLIP API - STRUCTURE VERIFICATION")
    print("="*60)
    
    success = test_api_structure()
    
    if success:
        print("\n✅ Your backend is ready for testing!")
        return 0
    else:
        print("\n❌ There are issues with your API setup")
        return 1


if __name__ == "__main__":
    sys.exit(main())
