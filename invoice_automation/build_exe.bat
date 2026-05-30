pip install -r requirements.txt
pip install pyinstaller
pyinstaller --onefile --name InvoiceProcessor run_client.py
echo EXE created under dist\InvoiceProcessor.exe