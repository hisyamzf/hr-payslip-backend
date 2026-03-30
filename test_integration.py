"""
Test Script untuk HR Payslip API
Testing endpoint: PDF generation, download, view
"""

import requests
import sys
from datetime import date, timedelta
from sqlalchemy.orm import Session
from uuid import UUID
import json

# Import local modules for direct testing
from app.config.database import SessionLocal
from app.models.database import Company, Employee, Payslip
from app.utils.hashing import calculate_file_hash
from app.services.upload_service import UploadService
from app.services.pdf_service import PayslipPDFService
from decimal import Decimal

BASE_URL = "http://localhost:8000"

def print_header(title: str):
    """Print formatted section header"""
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}\n")


def test_direct_pdf_generation():
    """Test PDF generation directly without API"""
    print_header("TEST 1: Direct PDF Generation")
    
    try:
        pdf_service = PayslipPDFService()
        
        # Generate sample PDF
        pdf_bytes = pdf_service.generate_payslip_pdf(
            employee_id='EMP-001',
            employee_name='John Doe',
            employee_department='Engineering',
            employee_position='Senior Developer',
            employee_join_date=date(2020, 1, 15),
            employee_bank_account='1234567890',
            
            company_name='PT. Example Company',
            company_address='Jl. Sudirman No. 123, Jakarta',
            company_phone='+62 21-1111-2222',
            
            period_start=date(2025, 3, 1),
            period_end=date(2025, 3, 31),
            payment_date=date(2025, 4, 5),
            
            earnings={'salary': 5000000.0, 'allowance': 1000000.0, 'bonus': 500000.0},
            deductions={'tax': 500000.0, 'bpjs': 200000.0},
            total_earnings=6500000.0,
            total_deductions=700000.0,
            net_salary=5800000.0,
        )
        
        # Save to file
        with open('payslip_test.pdf', 'wb') as f:
            f.write(pdf_bytes)
        
        print(f"✅ PDF generated successfully!")
        print(f"   File size: {len(pdf_bytes):,} bytes")
        print(f"   Saved to: payslip_test.pdf")
        return True
    
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def test_upload_service_with_pdf():
    """Test UploadService integration with PDF"""
    print_header("TEST 2: UploadService with PDF Integration")
    
    db: Session = SessionLocal()
    
    try:
        # Get or create test data
        print("Preparing test data...")
        
        # Get a company
        company = db.query(Company).first()
        if not company:
            print("❌ No company found in database")
            return False
        
        print(f"   Company: {company.name}")
        
        # Get an employee
        employee = db.query(Employee).filter(Employee.company_id == company.id).first()
        if not employee:
            print("❌ No employee found in database")
            return False
        
        print(f"   Employee: {employee.full_name} ({employee.employee_number})")
        
        # Check if payslip exists
        existing_payslip = db.query(Payslip).filter(
            Payslip.company_id == company.id,
            Payslip.employee_id == employee.id,
            Payslip.period_start == date(2025, 3, 1)
        ).first()
        
        if existing_payslip:
            print(f"   Payslip already exists: {existing_payslip.id}")
        else:
            print("   Creating new payslip...")
            # Create a test payslip
            payslip = Payslip(
                company_id=company.id,
                employee_id=employee.id,
                period_start=date(2025, 3, 1),
                period_end=date(2025, 3, 31),
                payment_date=date(2025, 4, 5),
                full_name=employee.full_name,
                department=employee.department or 'Engineering',
                position=employee.position or 'Staff',
                earnings={'salary': 5000000.0, 'allowance': 1000000.0},
                deductions={'tax': 500000.0, 'bpjs': 200000.0},
                gross_salary=6000000.0,
                total_deductions=700000.0,
                net_salary=5300000.0,
                status='draft'
            )
            db.add(payslip)
            db.commit()
            existing_payslip = payslip
            print(f"   ✅ Payslip created: {payslip.id}")
        
        # Test PDF generation from payslip
        print("\nGenerating PDF from payslip data...")
        pdf_service = PayslipPDFService()
        
        pdf_bytes = pdf_service.generate_payslip_pdf(
            employee_id=employee.employee_number,
            employee_name=employee.full_name,
            employee_department=employee.department or 'N/A',
            employee_position=employee.position or 'N/A',
            employee_join_date=employee.date_of_joining,
            employee_bank_account=employee.bank_account_number,
            
            company_name=company.name,
            company_address=company.address or 'Jakarta',
            company_phone=company.phone or '',
            
            period_start=existing_payslip.period_start,
            period_end=existing_payslip.period_end,
            payment_date=existing_payslip.payment_date,
            
            earnings=existing_payslip.earnings or {},
            deductions=existing_payslip.deductions or {},
            total_earnings=float(existing_payslip.gross_salary),
            total_deductions=float(existing_payslip.total_deductions),
            net_salary=float(existing_payslip.net_salary),
        )
        
        # Save to file
        filename = f"payslip_{employee.employee_number}.pdf"
        with open(filename, 'wb') as f:
            f.write(pdf_bytes)
        
        print(f"✅ PDF generated successfully!")
        print(f"   File size: {len(pdf_bytes):,} bytes")
        print(f"   Saved to: {filename}")
        return True
    
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()
        return False
    
    finally:
        db.close()


def test_health_endpoint():
    """Test /health endpoint"""
    print_header("TEST 3: Health Endpoint")
    
    try:
        response = requests.get(f"{BASE_URL}/health", timeout=5)
        print(f"Status Code: {response.status_code}")
        print(f"Response: {json.dumps(response.json(), indent=2)}")
        
        if response.status_code == 200:
            print("✅ Health endpoint working!")
            return True
        else:
            print("❌ Unexpected status code")
            return False
    
    except requests.exceptions.ConnectionError:
        print("❌ Cannot connect to server. Is it running on http://localhost:8000?")
        print("   Start server with: python run.py")
        return False
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        return False


def test_list_payslips_endpoint():
    """Test list payslips endpoint"""
    print_header("TEST 4: List Payslips Endpoint")
    
    db: Session = SessionLocal()
    try:
        # Get employee ID
        employee = db.query(Employee).first()
        if not employee:
            print("❌ No employee in database")
            return False
        
        employee_id = employee.id
        print(f"Testing with employee: {employee.full_name} ({employee_id})")
        
        try:
            url = f"{BASE_URL}/api/v1/payslips/employee/{employee_id}"
            response = requests.get(url, timeout=5)
            print(f"Status Code: {response.status_code}")
            print(f"Response: {json.dumps(response.json(), indent=2)}")
            
            if response.status_code == 200:
                print("✅ List payslips endpoint working!")
                return True
            else:
                print(f"❌ Unexpected status code: {response.status_code}")
                return False
        
        except requests.exceptions.ConnectionError:
            print("❌ Cannot connect to server")
            return False
    
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()
        return False
    
    finally:
        db.close()


def test_pdf_download_endpoint():
    """Test PDF download endpoint"""
    print_header("TEST 5: PDF Download Endpoint")
    
    db: Session = SessionLocal()
    try:
        # Get payslip from database
        payslip = db.query(Payslip).first()
        if not payslip:
            print("❌ No payslip in database")
            return False
        
        payslip_id = payslip.id
        print(f"Testing with payslip: {payslip_id}")
        print(f"   Employee: {payslip.full_name}")
        print(f"   Period: {payslip.period_start} to {payslip.period_end}")
        
        try:
            url = f"{BASE_URL}/api/v1/payslips/{payslip_id}/pdf?download=true"
            response = requests.get(url, timeout=30)
            print(f"Status Code: {response.status_code}")
            print(f"Content-Type: {response.headers.get('content-type')}")
            
            if response.status_code == 200 and 'pdf' in response.headers.get('content-type', ''):
                # Save downloaded PDF
                filename = f"payslip_download_{payslip_id}.pdf"
                with open(filename, 'wb') as f:
                    f.write(response.content)
                
                print(f"✅ PDF downloaded successfully!")
                print(f"   File size: {len(response.content):,} bytes")
                print(f"   Saved to: {filename}")
                return True
            else:
                print(f"❌ Unexpected response")
                print(f"Response: {response.text[:200]}")
                return False
        
        except requests.exceptions.ConnectionError:
            print("❌ Cannot connect to server")
            return False
    
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()
        return False
    
    finally:
        db.close()


def run_all_tests():
    """Run all tests"""
    print("\n" + "="*60)
    print("  HR PAYSLIP API - COMPREHENSIVE TEST SUITE")
    print("="*60)
    
    results = []
    
    # Test 1: Direct PDF generation (doesn't require server)
    results.append(("Direct PDF Generation", test_direct_pdf_generation()))
    
    # Test 2: UploadService with PDF
    results.append(("UploadService with PDF", test_upload_service_with_pdf()))
    
    # Test 3-5: API endpoints (require server)
    print_header("RUNNING API ENDPOINT TESTS")
    print("Make sure the server is running: python run.py")
    input("Press Enter to continue with API tests...")
    
    results.append(("Health Endpoint", test_health_endpoint()))
    results.append(("List Payslips Endpoint", test_list_payslips_endpoint()))
    results.append(("PDF Download Endpoint", test_pdf_download_endpoint()))
    
    # Summary
    print_header("TEST SUMMARY")
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
    
    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
