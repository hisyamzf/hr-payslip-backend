# test_pdf_generation.py
from app.services.pdf_service import PayslipPDFService
from datetime import date

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
    
    earnings={'salary': 5000000.0, 'allowance': 1000000.0},
    deductions={'tax': 500000.0, 'bpjs': 200000.0},
    total_earnings=6000000.0,
    total_deductions=700000.0,
    net_salary=5300000.0,
)

# Save to file
with open('payslip_sample.pdf', 'wb') as f:
    f.write(pdf_bytes)

print(f"✅ PDF generated: payslip_sample.pdf ({len(pdf_bytes)} bytes)")