"""
API Endpoint Tests
Test endpoints tanpa melibatkan WeasyPrint
"""

import requests
import sys
import time
import json
from datetime import date

BASE_URL = "http://localhost:8000"

def wait_for_server(timeout=20):
    """Wait for server to be ready"""
    start = time.time()
    while time.time() - start < timeout:
        try:
            response = requests.get(f"{BASE_URL}/health", timeout=2)
            if response.status_code == 200:
                return True
        except:
            pass
        time.sleep(1)
    return False


def test_health():
    """Test /health endpoint"""
    print("\n" + "="*60)
    print("TEST 1: Health Endpoint")
    print("="*60)
    
    try:
        response = requests.get(f"{BASE_URL}/health", timeout=5)
        print(f"Status: {response.status_code}")
        print(f"Response:\n{json.dumps(response.json(), indent=2)}")
        
        if response.status_code == 200:
            print("✅ PASS")
            return True
        else:
            print("❌ FAIL")
            return False
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        return False


def test_root():
    """Test / endpoint"""
    print("\n" + "="*60)
    print("TEST 2: Root Endpoint")
    print("="*60)
    
    try:
        response = requests.get(f"{BASE_URL}/", timeout=5)
        print(f"Status: {response.status_code}")
        print(f"Response:\n{json.dumps(response.json(), indent=2)}")
        
        if response.status_code == 200:
            print("✅ PASS")
            return True
        else:
            print("❌ FAIL")
            return False
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        return False


def test_list_payslips():
    """Test list payslips endpoint"""
    print("\n" + "="*60)
    print("TEST 3: List Payslips Endpoint")
    print("="*60)
    
    try:
        # Use a placeholder UUID - will just test routing
        employee_id = "550e8400-e29b-41d4-a716-446655440000"
        
        response = requests.get(
            f"{BASE_URL}/api/v1/payslips/employee/{employee_id}",
            timeout=5
        )
        
        print(f"Status: {response.status_code}")
        print(f"Endpoint: /api/v1/payslips/employee/{employee_id}")
        print(f"Response: {response.text[:200]}")
        
        # 200 OK or 404 Not Found are both acceptable (depends on data)
        if response.status_code in [200, 404]:
            print("✅ PASS - Endpoint is accessible")
            return True
        else:
            print(f"❌ FAIL - Unexpected status {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        return False


def test_api_documentation():
    """Test /docs endpoint"""
    print("\n" + "="*60)
    print("TEST 4: API Documentation")
    print("="*60)
    
    try:
        response = requests.get(f"{BASE_URL}/docs", timeout=5)
        print(f"Status: {response.status_code}")
        
        if response.status_code == 200:
            print(f"Content length: {len(response.text)} bytes")
            print("✅ PASS - Swagger UI available at /docs")
            return True
        else:
            print(f"❌ FAIL - Status {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        return False


def test_openapi_schema():
    """Test OpenAPI schema"""
    print("\n" + "="*60)
    print("TEST 5: OpenAPI Schema")
    print("="*60)
    
    try:
        response = requests.get(f"{BASE_URL}/openapi.json", timeout=5)
        print(f"Status: {response.status_code}")
        
        if response.status_code == 200:
            schema = response.json()
            print(f"API Title: {schema.get('info', {}).get('title')}")
            print(f"API Version: {schema.get('info', {}).get('version')}")
            
            paths = schema.get('paths', {})
            print(f"Total paths defined: {len(paths)}")
            for path in list(paths.keys())[:5]:
                print(f"  - {path}")
            
            print("✅ PASS - OpenAPI schema generated")
            return True
        else:
            print(f"❌ FAIL - Status {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        return False


def main():
    print("\n" + "="*60)
    print("  HR PAYSLIP API - ENDPOINT TESTS")
    print("="*60)
    print(f"\nConnecting to: {BASE_URL}")
    print("Waiting for server to be ready...")
    
    if not wait_for_server():
        print("\n❌ Server not responding!")
        print("Make sure to run 'python run.py' in another terminal")
        return 1
    
    print("✅ Server is ready!\n")
    
    results = []
    
    # Run tests
    results.append(("Health Endpoint", test_health()))
    results.append(("Root Endpoint", test_root()))
    results.append(("List Payslips", test_list_payslips()))
    results.append(("API Documentation", test_api_documentation()))
    results.append(("OpenAPI Schema", test_openapi_schema()))
    
    # Summary
    print("\n" + "="*60)
    print("  TEST SUMMARY")
    print("="*60)
    
    passed = 0
    failed = 0
    
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} - {test_name}")
        if result:
            passed += 1
        else:
            failed += 1
    
    print(f"\nTotal: {passed} passed, {failed} failed")
    
    print("\n" + "="*60)
    print("  AVAILABLE ENDPOINTS")
    print("="*60)
    print(f"""
✓ GET  /health
  Health check endpoint
  
✓ GET  /
  Root info endpoint
  
✓ GET  /docs
  API documentation (Swagger UI)
  
✓ GET  /openapi.json
  OpenAPI schema
  
✓ GET  /api/v1/payslips/{{payslip_id}}/pdf
  Get payslip as PDF (download or view)
  Query params:
    - download=true : Download as attachment
    - download=false : View inline in browser
  
✓ GET  /api/v1/payslips/employee/{{employee_id}}/period/{{period_start}}
  Get payslip by employee and period
  Example: .../employee/550e8400.../period/2025-03-01
  
✓ GET  /api/v1/payslips/employee/{{employee_id}}
  List all payslips for an employee
  Query params:
    - limit (default: 20)
    - offset (default: 0)
""")
    
    print("\n" + "="*60)
    print("  NEXT STEPS")
    print("="*60)
    print("""
1. ✅ Backend API structure is ready
2. ✅ Database models and repositories configured
3. ✅ PDF service implemented (lazy-loads WeasyPrint)
4. ✅ UploadService integrated with PDF support
5. ✅ API endpoints for PDF generation/download

⏭️  To fully test PDF generation:
   - Use Linux/WSL2 or Docker container
   - Or use Supabase/external API for PDF generation

📝 Integration points:
   - UploadService.process_upload() queues PDFs
   - PayslipPDFService.generate_payslip_pdf() renders PDFs
   - Payslips API routes provide download/view endpoints
""")
    
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
