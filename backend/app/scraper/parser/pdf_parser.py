import pdfplumber
import io
import re
from app.scraper.domain.dtos import PdfParsedResultDTO

class PdfParser:
    """
    Parses Index-II PDFs using pdfplumber to extract tabular data.
    Gracefully handles Unicode/DV-TTYogesh font artifacts by preserving the exact text extracted.
    """
    
    @classmethod
    def parse(cls, pdf_bytes: bytes) -> PdfParsedResultDTO:
        result = PdfParsedResultDTO()
        
        try:
            with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
                for page in pdf.pages:
                    tables = page.extract_tables()
                    for table in tables:
                        for row in table:
                            if not row:
                                continue
                            
                            # Flatten the row to find the label and the value
                            # Sometimes they are in cols [0, 1], sometimes [0, 2] due to colspans
                            cells = [str(c).strip() for c in row if c is not None and str(c).strip()]
                            if not cells:
                                continue
                                
                            label_cell = cells[0]
                            value_cell = cells[1] if len(cells) > 1 else ""
                            
                            # Doc Reg. No is often buried in the header
                            for cell in cells:
                                if "Doc Reg. No. :" in cell:
                                    # Extract just the number
                                    match = re.search(r"Doc Reg\. No\. :\s*([^\s]+)", cell)
                                    if match:
                                        result.doc_no_raw = match.group(1)
                            
                            # Look for explicit numbered fields
                            if "(2)" in label_cell and "मोबदला" in label_cell:
                                result.consideration_amount_raw = value_cell
                            elif "(3)" in label_cell and "बाजारभाव" in label_cell:
                                result.market_value_raw = value_cell
                            elif "(4)" in label_cell:
                                result.properties_raw = value_cell
                            elif "(5)" in label_cell:
                                result.area_raw = value_cell
                            elif "(6)" in label_cell:
                                result.assessment_raw = value_cell
                            elif "(7)" in label_cell:
                                result.sellers_raw = value_cell
                            elif "(8)" in label_cell:
                                result.buyers_raw = value_cell
                            elif "(9)" in label_cell:
                                result.execution_date_raw = value_cell
                            elif "(10)" in label_cell:
                                result.registration_date_raw = value_cell
                            elif "(12)" in label_cell:
                                result.stamp_duty_raw = value_cell
                            elif "(13)" in label_cell:
                                result.registration_fee_raw = value_cell
                            elif "(14)" in label_cell:
                                result.remarks_raw = value_cell
        except Exception as e:
            # Let the caller decide how to handle, but do not crash the worker entirely on one bad PDF
            import logging
            logging.getLogger(__name__).error(f"Failed to parse PDF: {e}")
            raise e
            
        return result
