# Quick Setup Guide

## Prerequisites

- Python 3.8 or higher
- pip (Python package manager)
- Internet connection

## Step-by-Step Installation

### 1. Activate Virtual Environment (if you have one)

```cmd
venv\Scripts\activate
```

If you don't have a virtual environment yet, create one:

```cmd
python -m venv venv
venv\Scripts\activate
```

### 2. Install Dependencies

```cmd
pip install -r requirements.txt
```

**Note:** EasyOCR will download language models on first use (~100MB for English).

### 3. Configure Your Search

Copy the template and edit `.env` — `config.py` only holds the defaults:

```cmd
copy .env.example .env
```

The portal's district / taluka / village ids cannot be guessed, so ask it
for them and paste the printed lines into `.env`:

```cmd
python setup_location.py          your village's ids
python setup_location.py --wifi   your saved Wi-Fi profile names
```

```
IGR_DISTRICT=पुणे          # Your district
IGR_TALUKA=हवेली           # Your taluka
IGR_VILLAGE=खराडी (पुणे महापालिकेमध्ये समाविष्ट)
IGR_DISTRICT_ID=23
IGR_TALUKA_ID=1
IGR_VILLAGE_ID=43
```

### 4. Run the Script

```cmd
python search_property.py
```

## Expected Output

```
Creating session...
Opening Property Details page...
Initial response: XXXXX bytes
CSRF token obtained: XX characters

CAPTCHA saved to: d:\PureFrame\igr2.1\captcha.png

Reading CAPTCHA from captcha.png...
  Detected: 'ABC123' (confidence: 0.95)
Final CAPTCHA text: 'ABC123'

Sending property search...
Status: 200
Response size: XXXXX

Response saved to: d:\PureFrame\igr2.1\responses\property_1.html
```

## What Happens

1. ✅ Session created with proper headers
2. ✅ Property page fetched
3. ✅ CSRF token extracted
4. ✅ CAPTCHA downloaded to `captcha.png`
5. ✅ CAPTCHA automatically read using EasyOCR
6. ✅ Form submitted with property number
7. ✅ Response saved to `responses/property_1.html`

## If CAPTCHA OCR Fails

The script will prompt:

```
Automatic CAPTCHA reading failed: [error message]

====================================
Please enter the CAPTCHA manually
====================================
CAPTCHA: 
```

Just open `captcha.png`, read the text, and type it in.

## Verify Results

Check the saved response:

```cmd
start responses\property_1.html
```

Or open it with your browser to view the property details.

## Troubleshooting

### EasyOCR not installing

Try upgrading pip first:
```cmd
python -m pip install --upgrade pip
pip install easyocr
```

### Import errors

Make sure virtual environment is activated:
```cmd
venv\Scripts\activate
```

### Connection timeout

- Check your internet connection
- The IGR portal might be down
- Try increasing timeout in `search_property.py`

### CAPTCHA always fails

- The CAPTCHA might use special fonts
- Try adjusting EasyOCR parameters
- Use manual entry as fallback

## Next Steps

Once you have a successful response in `responses/property_1.html`:

1. Parse the HTML to extract property details
2. Automate for multiple property numbers
3. Add error handling and retry logic
4. Export results to CSV/JSON format
