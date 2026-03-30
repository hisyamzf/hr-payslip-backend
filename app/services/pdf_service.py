from jinja2 import Environment, FileSystemLoader
from io import BytesIO
from datetime import datetime
from pathlib import Path
import logging
import os

logger = logging.getLogger(__name__)


class PDFGenerationError(Exception):
    """Exception untuk PDF generation errors"""
    pass


class PayslipPDFService:
    """
    Service untuk generate PDF payslip using Jinja2 + WeasyPrint
    Dengan fallback untuk Windows development
    """
    
    # Class variable untuk track WeasyPrint availability
    WEASYPRINT_AVAILABLE = None
    
    def __init__(self, template_dir: str = None, force_mock: bool = False):
        """
        Args:
            template_dir: Path ke folder yang berisi HTML templates
            force_mock: Force mock PDF mode (untuk testing)
        """
        if template_dir is None:
            template_dir = str(Path(__file__).parent.parent / "templates")
        
        self.template_dir = template_dir
        self.env = Environment(loader=FileSystemLoader(template_dir))
        self.force_mock = force_mock or os.getenv('PDF_MOCK_MODE', 'false').lower() == 'true'
        
        # Add custom filters
        self.env.filters['strftime'] = self._strftime_filter
        self.env.filters['currency'] = self._currency_filter
        
        # Check WeasyPrint on first init
        if PayslipPDFService.WEASYPRINT_AVAILABLE is None:
            self._check_weasyprint()
        
        mode = "MOCK (development)" if (self.force_mock or not PayslipPDFService.WEASYPRINT_AVAILABLE) else "FULL PDF"
        logger.info(f"✅ PDFService ready [{mode}] - Templates: {template_dir}")
    
    @classmethod
    def _check_weasyprint(cls):
        """Check if WeasyPrint dependencies available"""
        try:
            from weasyprint import HTML
            # Try simple render test
            HTML(string='<p>test</p>').render()
            cls.WEASYPRINT_AVAILABLE = True
            logger.info("✅ WeasyPrint fully available")
        except Exception as e:
            cls.WEASYPRINT_AVAILABLE = False
            logger.warning(f"⚠️  WeasyPrint unavailable: {str(e)[:80]}... Using mock mode")
    
    def _strftime_filter(self, date_obj, format_string='%d %B %Y'):
        """Format dates"""
        if date_obj is None:
            return ''
        return date_obj.strftime(format_string)
    
    def _currency_filter(self, amount, prefix='Rp '):
        """Format currency"""
        if amount is None:
            return f"{prefix}0"
        try:
            return f"{prefix}{amount:,.0f}"
        except (ValueError, TypeError):
            return f"{prefix}0"
    
    def render_payslip_html(
        self,
        employee_id: str,
        employee_name: str,
        employee_department: str,
        employee_position: str,
        employee_join_date,
        employee_bank_account: str = None,
        company_name: str = "PT. Example Company",
        company_address: str = "Jl. Contoh No. 123, Jakarta",
        company_phone: str = "+62 21-1234-5678",
        company_logo: str = None,
        period_start = None,
        period_end = None,
        payment_date = None,
        earnings: dict = None,
        deductions: dict = None,
        total_earnings: float = 0,
        total_deductions: float = 0,
        net_salary: float = 0,
    ) -> str:
        """Render HTML dari template"""
        try:
            template = self.env.get_template('payslip_template.html')
            
            context = {
                'employee_id': employee_id,
                'employee_name': employee_name,
                'employee_department': employee_department or 'N/A',
                'employee_position': employee_position or 'N/A',
                'employee_join_date': employee_join_date or datetime.now(),
                'employee_bank_account': employee_bank_account,
                'company_name': company_name,
                'company_address': company_address,
                'company_phone': company_phone,
                'company_logo': company_logo,
                'period_start': period_start or datetime.now(),
                'period_end': period_end or datetime.now(),
                'payment_date': payment_date or datetime.now(),
                'earnings': earnings or {},
                'deductions': deductions or {},
                'total_earnings': total_earnings,
                'total_deductions': total_deductions,
                'net_salary': net_salary,
                'signature_date': datetime.now(),
                'generated_date': datetime.now(),
            }
            
            html_content = template.render(**context)
            logger.debug(f"✅ HTML rendered for {employee_id}")
            return html_content
        
        except Exception as e:
            logger.error(f"❌ Template render failed: {str(e)}")
            raise PDFGenerationError(f"Error rendering template: {str(e)}")
    
    def _generate_mock_pdf(self, html_content: str) -> bytes:
        """Generate mock PDF for development (Windows)"""
        try:
            from reportlab.lib.pagesizes import letter
            from reportlab.pdfgen import canvas
            from io import BytesIO as BytesIOLib
            
            buffer = BytesIOLib()
            c = canvas.Canvas(buffer, pagesize=letter)
            c.setFont("Helvetica-Bold", 16)
            c.drawString(50, 750, "PAYSLIP")
            c.setFont("Helvetica", 9)
            c.drawString(50, 720, "Generated in mock PDF mode (development/Windows)")
            c.drawString(50, 50, "Deploy with WeasyPrint on Linux/WSL for production PDF")
            c.save()
            
            pdf_bytes = buffer.getvalue()
            logger.info(f"✅ Mock PDF generated ({len(pdf_bytes)} bytes)")
            return pdf_bytes
        
        except ImportError:
            # Fallback: return HTML as bytes
            logger.warning("⚠️ ReportLab not available, returning HTML")
            return html_content.encode('utf-8')
    
    def generate_pdf_bytes(self, html_content: str) -> bytes:
        """Convert HTML to PDF with fallback"""
        if self.force_mock or not PayslipPDFService.WEASYPRINT_AVAILABLE:
            logger.info("ℹ️  Using mock PDF mode")
            return self._generate_mock_pdf(html_content)
        
        try:
            from weasyprint import HTML
            pdf_bytes = HTML(string=html_content).write_pdf()
            logger.info(f"✅ PDF generated ({len(pdf_bytes)} bytes)")
            return pdf_bytes
        
        except Exception as e:
            error_msg = str(e)
            if 'libgobject' in error_msg or 'error 0x7e' in error_msg:
                logger.warning("⚠️ System library missing - using mock PDF")
                return self._generate_mock_pdf(html_content)
            
            logger.error(f"❌ PDF render error: {error_msg[:100]}")
            logger.warning("⚠️ Falling back to mock PDF")
            return self._generate_mock_pdf(html_content)
    
    def generate_payslip_pdf(
        self,
        employee_id: str,
        employee_name: str,
        employee_department: str,
        employee_position: str,
        employee_join_date,
        employee_bank_account: str = None,
        company_name: str = "PT. Example Company",
        company_address: str = "Jl. Contoh No. 123, Jakarta",
        company_phone: str = "+62 21-1234-5678",
        company_logo: str = None,
        period_start = None,
        period_end = None,
        payment_date = None,
        earnings: dict = None,
        deductions: dict = None,
        total_earnings: float = 0,
        total_deductions: float = 0,
        net_salary: float = 0,
    ) -> bytes:
        """Complete: Render HTML + Generate PDF (with fallback)"""
        html_content = self.render_payslip_html(
            employee_id=employee_id,
            employee_name=employee_name,
            employee_department=employee_department,
            employee_position=employee_position,
            employee_join_date=employee_join_date,
            employee_bank_account=employee_bank_account,
            company_name=company_name,
            company_address=company_address,
            company_phone=company_phone,
            company_logo=company_logo,
            period_start=period_start,
            period_end=period_end,
            payment_date=payment_date,
            earnings=earnings,
            deductions=deductions,
            total_earnings=total_earnings,
            total_deductions=total_deductions,
            net_salary=net_salary,
        )
        
        return self.generate_pdf_bytes(html_content)