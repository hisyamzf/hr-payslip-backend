from sqlalchemy.orm import Session
from app.config.database import SessionLocal
from app.services.upload_service import UploadService
from app.utils.hashing import calculate_file_hash
from uuid import uuid4
from datetime import date
import uuid

def main():
    """
    Test flow: Create session → Submit mapping → Process
    """
    # Get DB session
    db: Session = SessionLocal()
    
    try:
        service = UploadService(db)
        company_id = uuid.UUID("0ddae477-fa92-4aa5-9c0a-724e2e79980d")  # Ganti dengan company ID real
        
        # Step 1: Create upload session
        print("📝 Step 1: Creating upload session...")
        # print("PK:", upload_session.id)
        # print("PUBLIC ID:", upload_session.upload_session_id)
        upload_session = service.create_upload_session(
            company_id=company_id,
            file_path="dummy_payroll_march_2025.xlsx",
            file_hash=calculate_file_hash(b"dummy file content"),
            period_start=date(2025, 3, 1),
            period_end=date(2025, 3, 31),
            payment_date=date(2025, 4, 5),
            created_by="admin@company.com"
        )
        print(f"✅ Created: {upload_session.upload_session_id}")
        
        # Step 2: Submit column mapping
        print("\n📝 Step 2: Submitting column mapping...")
        column_mapping = {
            'start_row': 5,  # mulai parsing dari row 5 untuk semua sheet
            'fixed_columns': {
                'employee_number': 'A',
                'full_name': 'B',
            },
            'earnings': {
                'sheet_name': 'Benefit',
                'columns': [
                    {'column': 'C', 'key': 'salary', 'header': 'Sallary'},
                    {'column': 'D', 'key': 'allowance', 'header': 'Allowance'},
                    {'column': 'E', 'key': 'bonus', 'header': 'Bonus'},
                ]
            },
            'deductions': {
                'sheet_name': 'Deduction',
                'columns': [
                    {'column': 'C', 'key': 'tax', 'header': 'Tax'},
                    {'column': 'D', 'key': 'bpjs', 'header': 'BPJS'},
                    {'column': 'E', 'key': 'loan', 'header': 'Loan'},
                ]
            }
        }

        # Pass it to submit_column_mapping
        service.submit_column_mapping(
            upload_session.upload_session_id, 
            column_mapping
        )
        print("✅ Mapping submitted")
        
        # Step 3: Process upload
        print("\n📝 Step 3: Processing upload...")
        result = service.process_upload(upload_session.upload_session_id)
        
        print("\n📊 RESULT:")
        print(f"   Total rows: {result['total_rows']}")
        print(f"   Successful: {result['successful_inserts']}")
        print(f"   Failed: {result['failed']}")
        if result['errors']:
            print(f"   Errors:")
            for error in result['errors']:
                print(f"      - Row {error['row_number']}: {error['error']}")
    
    except Exception as e:
        print(f"❌ Error: {e}")
    
    finally:
        db.close()

if __name__ == "__main__":
    main()