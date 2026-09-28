# Quick Start - Get Property Details in 3 Steps

## Step 1: Install Dependencies

```cmd
pip install -r requirements.txt
```

**What gets installed:**
- `requests` - HTTP client
- `beautifulsoup4` - HTML parser  
- `easyocr` - CAPTCHA reader (automatic!)
- `lxml` - XML parser

## Step 2: Test Your Setup

```cmd
python test_setup.py
```

**Expected output:**
```
🎉 ALL TESTS PASSED - Setup is complete!
```

## Step 3: Run the Script

### Option A: Single Property

```cmd
python search_property.py
```

**What happens:**
1. Opens IGR portal
2. Gets CSRF token
3. Downloads CAPTCHA → `captcha.png`
4. **Reads CAPTCHA automatically** (EasyOCR)
5. Submits search for property #1
6. Saves result → `responses/property_1.html`

### Option B: Multiple Properties

```cmd
python batch_search.py
```

**What happens:**
- Fetches properties 1-10 automatically
- Handles CAPTCHA for each
- Saves as `property_1.html`, `property_2.html`, etc.

## ⚙️ Customize Search

Edit `.env`, not `config.py`. Run this to get the right lines for your
village, then paste them in:

```cmd
python setup_location.py
```

```
IGR_DISTRICT=पुणे
IGR_TALUKA=हवेली
IGR_VILLAGE=खराडी (पुणे महापालिकेमध्ये समाविष्ट)
IGR_DISTRICT_ID=23
IGR_TALUKA_ID=1
IGR_VILLAGE_ID=43

IGR_SURVEY_START=1
IGR_SURVEY_END=99
IGR_YEARS=2026,2025,2024,2023,2022,2021,2020,2019
```

See the Configuration section of `README.md` for the full list.

For batch search, edit `batch_search.py`:

```python
START_PROPERTY = 1
END_PROPERTY = 10
DELAY_BETWEEN_REQUESTS = 2  # seconds
```

## 📂 Output

All responses saved to `responses/` directory:

```
responses/
├── property_1.html
├── property_2.html
└── property_3.html
```

## 🔍 View Results

Open the HTML files in your browser:

```cmd
start responses\property_1.html
```

## ❓ If CAPTCHA Reading Fails

The script automatically falls back to manual entry:

```
====================================
Please enter the CAPTCHA manually
====================================
CAPTCHA: [type the text from captcha.png]
```

## 📋 Complete Workflow

```
User runs:
  python search_property.py

↓

Script does:
  1. GET https://pay2igr.igrmaharashtra.gov.in/eDisplay/Propertydetails/index
  2. Parse HTML → Extract CSRF token
  3. GET /eDisplay/captcha-image → Save as captcha.png
  4. EasyOCR reads captcha.png → Get text (e.g., "ABC123")
  5. POST form data with:
     - CSRF token
     - CAPTCHA text
     - District/Taluka/Village IDs
     - Property number
  6. Save response → responses/property_1.html

↓

Result:
  ✅ Property details in responses/property_1.html
```

## 🎯 That's It!

You now have automated property search with CAPTCHA reading.

For more details, see:
- `README.md` - Full documentation
- `SETUP.md` - Detailed setup guide
- `SUMMARY.md` - Project overview
