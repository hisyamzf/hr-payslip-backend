# Quick Start Guide - HR Payslip API

## 🚀 Start Server

```bash
cd backend
.venv\Scripts\python.exe run.py
```

Server: `http://localhost:8000`

## 📚 API Documentation

Open in browser: http://localhost:8000/docs

## 🧪 Test Everything

```bash
# Test 1: Verify structure
.venv\Scripts\python.exe test_structure.py

# Test 2: Test endpoints (with running server)
.venv\Scripts\python.exe test_endpoints.py
```

## 📋 Common API Calls

### Get Payslip as PDF (Download)
```bash
curl -o payslip.pdf "http://localhost:8000/api/v1/payslips/{payslip_id}/pdf?download=true"
```

### Get Payslip as PDF (View in Browser)
```
http://localhost:8000/api/v1/payslips/{payslip_id}/pdf?download=false
```

### List All Payslips for Employee
```bash
curl "http://localhost:8000/api/v1/payslips/employee/{employee_id}?limit=20&offset=0"
```

### Get Payslip by Employee & Period
```bash
curl "http://localhost:8000/api/v1/payslips/employee/{employee_id}/period/2025-03-01"
```

### Health Check
```bash
curl "http://localhost:8000/health"
```

## 🔌 Integration with Frontend

### React Example
```javascript
// Get payslip PDF
const downloadPayslip = async (payslipId) => {
  try {
    const response = await fetch(
      `/api/v1/payslips/${payslipId}/pdf?download=true`
    );
    const blob = await response.blob();
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `payslip_${payslipId}.pdf`;
    a.click();
  } catch (error) {
    console.error('Error downloading payslip:', error);
  }
};

// View payslip PDF
const viewPayslip = (payslipId) => {
  window.open(
    `/api/v1/payslips/${payslipId}/pdf?download=false`,
    '_blank'
  );
};

// List employee payslips
const listPayslips = async (employeeId) => {
  try {
    const response = await fetch(
      `/api/v1/payslips/employee/${employeeId}?limit=20`
    );
    const data = await response.json();
    return data.payslips;
  } catch (error) {
    console.error('Error fetching payslips:', error);
  }
};
```

## 📦 How It Works

1. **Upload Excel** → UploadService processes
2. **Payslips Created** → Inserted into database
3. **PDF Queued** → _queue_pdf_generation() called
4. **Frontend Requests** → API endpoint called
5. **PDF Generated** → Rendered on demand
6. **Return to User** → Download or view inline

## ✅ What's Integrated

- ✅ FastAPI server
- ✅ PDF generation endpoints
- ✅ UploadService integration
- ✅ Database connectivity
- ✅ Error handling

## ⚠️ Windows PDF Generation Limitation

WeasyPrint needs system libraries. Two options:

**Option 1: Use WSL2**
```bash
# In WSL2 terminal
wsl
cd /path/to/backend
python run.py
```

**Option 2: Use Docker**
```bash
# Docker will have all system libraries
docker build -t hr-payslip .
docker run -p 8000:8000 hr-payslip
```

## 📝 Example Usage

### 1. Test Server is Running
```bash
curl http://localhost:8000/health
# Response: {"status":"ok","service":"HR Payslip API","version":"1.0.0"}
```

### 2. List Employee Payslips
```bash
curl "http://localhost:8000/api/v1/payslips/employee/550e8400-e29b-41d4-a716-446655440000?limit=10"
```

### 3. Download Payslip PDF
```bash
# Replace with actual UUID
curl "http://localhost:8000/api/v1/payslips/abc123-def456/pdf?download=true" \
  -o payslip.pdf
```

## 🔑 Key Files

- `run.py` - Start the server
- `app/api/v1/payslips.py` - PDF endpoints
- `app/services/pdf_service.py` - PDF generation
- `app/services/upload_service.py` - Upload workflow
- `app/templates/payslip_template.html` - PDF template

## 🎯 Next: Add Frontend Integration

1. Add Payslip Download button in employee portal
2. Add View PDF button in payslip list
3. Store payslip PDFs (optional)
4. Add email notification with PDF attachment

## 📞 Troubleshooting

### "Cannot import module X"
→ Ensure .venv is activated: `.venv\Scripts\activate.ps1`

### "Connection refused" on localhost:8000
→ Make sure server is running: `python run.py`

### WeasyPrint import errors
→ Use WSL2 or Docker instead of Windows

### PDF is blank or incomplete
→ Check payslip data in database
→ Verify earnings/deductions are populated

## ✨ Done!

Your HR Payslip API is ready to use! 🎉
