import re
from bs4 import BeautifulSoup
from app.scraper.domain.dtos import SearchResultDTO, SearchResponseDTO, SearchScopeDTO
from app.scraper.domain.exceptions import IGRParserError

class PureHtmlParser:
    """
    Pure component that parses HTML bytes from the IGR search result page
    and maps them to domain DTOs. Does not manage networks or side effects.
    """
    def parse(self, html_bytes: bytes, year: int, survey_query: str, scope: SearchScopeDTO) -> SearchResponseDTO:
        try:
            html = html_bytes.decode('utf-8', errors='replace')
        except Exception as e:
            raise IGRParserError(f"Failed to decode HTML: {e}")

        soup = BeautifulSoup(html, "html.parser")
        
        # 1. Truncation / Record count detection
        msg_div = soup.find("div", class_="message")
        flash_message = msg_div.get_text(" ", strip=True) if msg_div else ""
        
        reported_count = None
        match = re.search(r"([\d,]+)\s*Records?\s*found", flash_message, re.I)
        if match:
            try:
                reported_count = int(match.group(1).replace(",", ""))
            except ValueError:
                pass
                
        # 2. Structural table validation
        table = soup.find("table", id="tableparty")
        if not table:
            raise IGRParserError("Missing tableparty in HTML response")
            
        thead = table.find("thead")
        if not thead:
            raise IGRParserError("Missing thead in tableparty")
            
        # 3. Dynamic header mapping
        headers = [th.get_text(" ", strip=True) for th in thead.find_all("th")]
        
        def find_col(possible_names):
            for i, h in enumerate(headers):
                normalized_h = h.replace(" ", "").replace("\n", "")
                for name in possible_names:
                    if name.replace(" ", "") == normalized_h:
                        return i
            raise IGRParserError(f"Missing required column: {possible_names[0]}")

        # Map the exact Marathi columns
        try:
            col_sr_no = find_col(["अनु क्र."])
            col_doc_no = find_col(["दस्त क्र."])
            col_doc_type = find_col(["दस्त प्रकार"])
            col_office = find_col(["दू. नि. कार्यालय", "दू.नि.कार्यालय", "दु. नि. कार्यालय", "दु.नि.कार्यालय"])
            col_date = find_col(["दिनांक"])
            col_seller = find_col(["लिहून देणार"])
            col_buyer = find_col(["लिहून घेणार"])
            col_other = find_col(["इतर माहीती", "इतर माहिती"])
            col_indexii = find_col(["सूची क्र. २", "सूची क्र .२", "सूची क्र . २", "सूचीक्र.२"])
        except IGRParserError as e:
            raise e

        tbody = table.find("tbody")
        if not tbody:
            raise IGRParserError("Missing tbody in tableparty")
            
        # 4. Row extraction
        results = []
        for row in tbody.find_all("tr"):
            cells = row.find_all("td")
            if not cells:
                continue
            # Handle empty / no data row: e.g. <td colspan="9">No data available in table</td>
            if len(cells) == 1 and ("no data" in cells[0].text.lower() or "माहिती उपलब्ध नाही" in cells[0].text):
                continue
            if not row.get("id") == "tbdata" and not cells:
                continue
                
            max_col = max(col_sr_no, col_doc_no, col_doc_type, col_office, col_date, col_seller, col_buyer, col_other, col_indexii)
            if len(cells) <= max_col:
                if row.get("id") == "tbdata":
                    raise IGRParserError(f"Row has insufficient cells ({len(cells)} <= {max_col})")
                continue
                
            def clean_cell(td):
                for br in td.find_all("br"):
                    br.replace_with("\n")
                text = td.get_text(separator="\n", strip=True)
                # Remove consecutive newlines if any
                text = re.sub(r'\n+', '\n', text)
                # Remove any random spaces around newlines
                text = re.sub(r' \n |\n | \n', '\n', text)
                return text.strip()

            # 5. Extract Index II
            # Keep conservative behavior: extract the pure href string.
            # Do NOT evaluate javascript, doSubmit(...), decode tokens, or download the PDF.
            indexii_td = cells[col_indexii]
            a_tag = indexii_td.find("a")
            href = a_tag.get("href", "") if a_tag else ""
            if not href:
                raise IGRParserError("Missing Index II link in cell")

            # Validate/clean the href per DTO
            if not href.startswith("/") and not href.startswith("http"):
                raise IGRParserError("Malformed Index II URL format")

            try:
                dto = SearchResultDTO(
                    year=year,
                    survey_query=survey_query,
                    sr_no=clean_cell(cells[col_sr_no]),
                    doc_no=clean_cell(cells[col_doc_no]),
                    doc_type=clean_cell(cells[col_doc_type]),
                    office=clean_cell(cells[col_office]),
                    date=clean_cell(cells[col_date]),
                    seller=clean_cell(cells[col_seller]),
                    buyer=clean_cell(cells[col_buyer]),
                    other_info=clean_cell(cells[col_other]),
                    indexii_url=href
                )
                results.append(dto)
            except Exception as e:
                # If DTO validation fails for a row, it's structurally malformed relative to expectations
                raise IGRParserError(f"Row mapping failed: {e}")

        # 6. Truncation logic
        retrieved_count = len(results)
        truncated = False
        if reported_count is not None:
            if reported_count > retrieved_count:
                truncated = True
            elif reported_count == 5000 and retrieved_count == 5000:
                truncated = True

        return SearchResponseDTO(
            results=results,
            reported_count=reported_count,
            retrieved_count=retrieved_count,
            truncated=truncated,
            year=year,
            survey_query=survey_query,
            location=scope
        )
