import asyncio
from playwright.async_api import async_playwright

#chrome.exe --remote-debugging-port=9222 --user-data-dir="C:\Selenium\ChromeProfile"
async def fill_sap_fiori_invoice():
    async with async_playwright() as p:
        # Connect to your already open Chrome session
        browser = await p.chromium.connect_over_cdp("http://localhost:9222")
        context = browser.contexts[0]
        
        # Locate the active SAP Fiori tab
        page = None
        for current_page in context.pages:
            if "SupplierInvoice-create" in current_page.url:
                page = current_page
                break
                
        if not page:
            print("Error: Could not find the active 'Create Supplier Invoice' tab. Make sure it's open!")
            return

        print(f"Connected to SAP Fiori page: {await page.title()}")

        # --- Define Your Default Data ---
        default_company_code = "4600"
        default_gross_amount = "192.70"
        default_reference = "3185488"
        default_gl_account = "51000100"
        default_item_text = "rocks"
        default_invoicing_party = "V00096"
        default_invoice_date = "06/04/26"
  
        # --- Populate Header Fields ---
        print("Populating Header Fields...")
        
        # 1. Wait for page to completely settle
        gross_amount_field = page.locator('input[id*="CEInputInvoiceGrossAmount-input-inner"]')
        await gross_amount_field.wait_for(state="visible", timeout=30000)
        
        # 2. Fill standard header fields safely
        await gross_amount_field.fill(default_gross_amount)
        await page.locator('input[id*="CEInputReference-input-inner"]').fill(default_reference)
        await page.locator('input[id*="CEInputInvoicingParty-input-inner"]').fill(default_invoicing_party)
        await page.locator('input[id*="CEDatePickerDocumentDate-datePicker-inner"]').fill(default_invoice_date)
        
        # --- Handle "Show More" & Document Type ---
        print("Checking for hidden header fields...")
        
        # Look for Fiori's 'Show More' button
        show_more_button = page.locator('button:has-text("Show More"), button:has-text("More"), button[id*="more" i]').first
        
        try:
            # Short timeout so it doesn't hang if already expanded
            if await show_more_button.is_visible(timeout=3000):
                print("Found 'Show More' button. Clicking to reveal Document Type...")
                await show_more_button.click()
                await page.wait_for_timeout(1500) # Give the DOM time to slide open
        except Exception:
            print("Header already expanded or 'Show More' not required.")

        # Target Document Type using the exact ID we found in the debug dump
        doc_type_field = page.locator('input[id*="InputAccountingDocumentType"][id*="inner"]').first
        try:
            await doc_type_field.wait_for(state="visible", timeout=5000)
            await doc_type_field.fill("NS")
            print("Successfully filled Document Type: NS")
        except Exception:
            print("Warning: Document Type field still could not be found.")

        # --- Populate G/L Account Row ---
        print("Populating G/L Account Row...")
        
        # 1. Click Add Button safely
        add_button = page.locator('button[id*="ButtonAddGLItemTable"]').first
        await add_button.scroll_into_view_if_needed()
        await page.wait_for_timeout(2000)
        await add_button.click(force=True)
        
        # 2. Define the G/L table container
        gl_table = page.locator('[id*="TableGLAccountItems"]')

        # 3. Target the fields by the EXACT IDs discovered in the dump
        gl_account_field  = gl_table.locator('input[id*="GLAccount"][id*="inner"]').first
        gl_amount_field   = gl_table.locator('input[id*="Amount"][id*="inner"]').first
        tax_code_field    = gl_table.locator('input[id*="TaxCode"][id*="inner"]').first
        tax_juris_field   = gl_table.locator('input[id*="TaxJurisCodeByProvider"][id*="inner"]').first
        cost_center_field = gl_table.locator('input[id*="CostCenter"][id*="inner"]').first
        item_text_field   = gl_table.locator('input[id*="DocumentItemText"][id*="inner"]').first

        # 4. Wait for the row's first element to render
        await gl_account_field.wait_for(state="visible", timeout=15000)

        # 5. Fill the row data
        await gl_account_field.fill(default_gl_account)
        await gl_amount_field.fill(default_gross_amount)
        await tax_code_field.fill("I0")
        await tax_juris_field.fill("3806712660")
        await cost_center_field.fill("460020450")
        await item_text_field.fill(default_item_text)

        print("G/L Account Row populated successfully!")


# Run the automation
asyncio.run(fill_sap_fiori_invoice())