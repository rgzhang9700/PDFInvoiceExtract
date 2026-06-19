@echo off
REM Run North Sky invoice automation
REM Put this BAT file in: C:\PYTHON\PDFInvoiceExtract\invoice_automation

cd /d C:\PYTHON\PDFInvoiceExtract\invoice_automation

echo ============================================
echo Running North Sky invoice automation...
echo ============================================

python run_client.py --client-config clients/northsky_comm/config.yaml

echo.
echo ============================================
echo Finished.
echo ============================================
pause
