import pytest
import os
from app.scraper.parser.pdf_parser import PdfParser

def test_pdf_parser_extracts_fields():
    pdf_path = os.path.join(os.path.dirname(__file__), "..", "storage", "raw", "test_document.pdf")
    if not os.path.exists(pdf_path):
        pytest.skip(f"Test fixture not found: {pdf_path}")
        
    with open(pdf_path, "rb") as f:
        pdf_bytes = f.read()
        
    result = PdfParser.parse(pdf_bytes)
    
    # Doc Reg No
    assert result.doc_no_raw == "HVL6-9874-2026"
    
    # Consideration & Market Value
    assert result.consideration_amount_raw == "10000000"
    assert result.market_value_raw == "10464409.976"
    
    # Dates
    assert result.execution_date_raw == "27-03-2026"
    assert result.registration_date_raw == "30-03-2026"
    
    # Financials
    assert result.stamp_duty_raw == "Rs. 735000"
    assert result.registration_fee_raw == "Rs. 30000"
    
    # Sellers / Buyers
    assert result.sellers_raw is not None
    assert "वय: 50" in result.sellers_raw
    assert result.buyers_raw is not None
    assert "वय: 40" in result.buyers_raw
    
    # Properties
    assert result.properties_raw is not None
    assert "10. 50" in result.properties_raw
    assert result.area_raw is not None
    assert "10.5" in result.area_raw
