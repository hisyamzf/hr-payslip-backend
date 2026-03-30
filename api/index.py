"""
Vercel API handler for HR Payslip Backend
"""

from vercel_fastapi import VercelAPI
from run import app

handler = VercelAPI(app)
