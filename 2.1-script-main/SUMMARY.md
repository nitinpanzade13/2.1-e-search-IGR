# Project Summary - IGR Maharashtra Property Search

## 🎯 Goal Achieved

Your workflow is now **fully implemented and automated**:

```
✅ GET Property Details page
   ↓
✅ Extract CSRF token  
   ↓
✅ GET CAPTCHA image → captcha.png
   ↓
✅ Read CAPTCHA with EasyOCR (AUTOMATIC!)
   ↓
✅ POST property search (property_number = 1)
   ↓
✅ Save response → responses/property_1.html
```

## 📁 Directory Structure Analysis

### Core Scripts (Your Main Tools)

| File | Purpose | Status |
|------|---------|--------|
| **`search_property.py`** | **Main script** - Automated property search with CAPTCHA OCR | ✅ **ENHANCED** |
| `config.py` | Configuration (district, taluka, village, year, property) | ✅ Ready |
| `session.py` | Session management and portal access | ✅ Ready |
| `batch_search.py` | Fetch multiple properties (1-10, etc.) | ✅ **NEW** |

### Utility Scripts

| File | Purpose |
|------|---------|
| `property_form.py` | Form parsing and option selection |
| `form_parser.py` | Generic form field extraction |
| `portal.py` | Portal navigation utilities |
| `locations.py` | Location/district management |

### Inspection Scripts (Development Tools)

These scripts were used to reverse-engineer the portal:

- `inspect_property.py` - Analyze property form structure
- `inspect_form.py` - Form field inspection  
- `inspect_ajax.py` - AJAX endpoint discovery
- `find_dropdown_api.py` - Dropdown API detection
- `inspect_search_form.py` - Search form analysis
- `inspect_search_js.py` - JavaScript analysis
- `search_submit_info.py` - Form submission details

### Documentation (New)

- `README.md` - Complete project documentation
- `SETUP.md` - Quick setup guide
- `SUMMARY.md` - This file
- `requirements.txt` - Python dependencies

## 🚀 Quick Start

### 1. Install Dependencies

```cmd
pip install -r requirements.txt
```

### 2. Run Single Property Search

```cmd
python search_property.py
```

**Result:** `responses/property_1.html`

### 3. Run Batch Search (Multiple Properties)

```cmd
python batch_search.py
```

**Result:** `responses/property_1.html`, `property_2.html`, etc.

## 🔧 Key Enhancements Made

### 1. Automatic CAPTCHA Reading ✨

**Before:**
```python
captcha = input("CAPTCHA: ").strip()  # Manual entry
```

**After:**
```python
captcha = read_captcha(captcha_path)  # Automatic with EasyOCR!
```

- Uses EasyOCR for automatic text recognition
- Falls back to manual entry if OCR fails
- Shows confidence scores for debugging

### 2. Batch Processing Script

- Process properties 1-10 (or any range)
- Automatic delay between requests
- Error handling and retry logic
- Summary report at the end

### 3. Complete Documentation

- README with full instructions
- SETUP guide for beginners
- requirements.txt for easy installation
- Code comments for clarity

## 📊 Workflow Details

### Single Property Search (`search_property.py`)

1. **Session Creation**
   - Initialize requests.Session()
   - Set headers (User-Agent, etc.)

2. **Page Access**
   - GET property details page
   - Extract CSRF token from HTML

3. **CAPTCHA Handling**
   - Download CAPTCHA image
   - **OCR with EasyOCR** (automatic)
   - Fallback to manual entry

4. **Form Submission**
   - POST with all form data
   - Include CSRF token + CAPTCHA
   - Maintain session cookies

5. **Response Saving**
   - Save HTML response
   - Store in `responses/` directory

### Batch Search (`batch_search.py`)

- Loop through property numbers
- Create fresh session for each
- Handle CAPTCHA for each request
- Delay between requests (rate limiting)
- Collect success/failure statistics

## 🔑 Configuration

Edit `config.py`:

```python
BASE_URL = "https://pay2igr.igrmaharashtra.gov.in"
SEARCH_URL = f"{BASE_URL}/eDisplay/Propertydetails/index"

DISTRICT = "पुणे"
TALUKA = "हवेली"
VILLAGE = "खराडी"

YEAR = "2026"
PROPERTY_NUMBER = "1"

OUTPUT_DIR = "responses"
```

## 📦 Dependencies

```
requests>=2.31.0        # HTTP client
beautifulsoup4>=4.12.0  # HTML parsing
easyocr>=1.7.0          # CAPTCHA reading
lxml>=4.9.0             # XML/HTML parser
```

## 🎓 Technical Details

### Session Management
- Cookies preserved across requests
- CSRF token extracted from HTML
- Proper headers (User-Agent, Referer, Origin)

### CAPTCHA Strategy
1. Download using same session (important!)
2. OCR with EasyOCR (English language)
3. Clean text (remove spaces)
4. Submit with form data

### Form Payload
```python
{
    "_csrfToken": "...",
    "years": "3",
    "district_id": "23",
    "taluka_id": "1",
    "village_id": "43",
    "free_text": "1",  # Property number
    "captcha": "ABC123",
    # ... more fields
}
```

## 🐛 Troubleshooting

| Issue | Solution |
|-------|----------|
| CAPTCHA OCR fails | Script falls back to manual entry |
| Connection timeout | Check internet, increase timeout value |
| CSRF token not found | Portal HTML changed, check inspect scripts |
| Wrong property data | Verify district/taluka/village IDs in payload |

## 🎯 Next Steps (Optional Enhancements)

1. **Response Parser**
   - Extract property details from HTML
   - Convert to JSON/CSV format

2. **Database Storage**
   - Store results in SQLite/MySQL
   - Query and analyze data

3. **Web Interface**
   - Flask/Django web app
   - User-friendly search form

4. **Better OCR**
   - Pre-process CAPTCHA image
   - Try different OCR engines (Tesseract)
   - Train custom OCR model

5. **Async Processing**
   - Use asyncio/aiohttp
   - Parallel property fetching

## ✅ Success Criteria Met

- [x] GET Property Details page
- [x] Extract CSRF token
- [x] Download CAPTCHA image
- [x] **Automatic CAPTCHA reading** (EasyOCR)
- [x] POST property search with property_number = 1
- [x] Save response to `responses/property_1.html`
- [x] Bonus: Batch processing for multiple properties

## 📞 Support

If you encounter issues:

1. Check `captcha.png` - is it downloaded correctly?
2. Try manual CAPTCHA entry (automatic fallback)
3. Verify configuration in `config.py`
4. Check portal availability (might be down)
5. Review error messages for clues

---

**🎉 Your IGR Maharashtra property search automation is complete and ready to use!**
