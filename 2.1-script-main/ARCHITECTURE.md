# Architecture & Flow Diagram

## System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     IGR Property Search System                   │
└─────────────────────────────────────────────────────────────────┘

┌───────────────────┐         ┌──────────────────────────────────┐
│   User Scripts    │         │      Core Libraries              │
├───────────────────┤         ├──────────────────────────────────┤
│                   │         │                                  │
│ search_property.py│────────▶│ requests (HTTP)                  │
│ batch_search.py   │         │ beautifulsoup4 (HTML parsing)    │
│ test_setup.py     │         │ easyocr (CAPTCHA reading)        │
│                   │         │ lxml (XML parsing)               │
└───────────────────┘         └──────────────────────────────────┘
         │
         │
         ▼
┌───────────────────┐         ┌──────────────────────────────────┐
│  Configuration    │         │      Utilities                   │
├───────────────────┤         ├──────────────────────────────────┤
│                   │         │                                  │
│ config.py         │◀────────│ session.py (session mgmt)        │
│                   │         │ form_parser.py (form extraction) │
│ - District        │         │ property_form.py (form utils)    │
│ - Taluka          │         │ portal.py (navigation)           │
│ - Village         │         │                                  │
│ - Year            │         └──────────────────────────────────┘
│ - Property Number │
└───────────────────┘

         │
         │
         ▼
┌─────────────────────────────────────────────────────────────────┐
│                      IGR Portal (Remote)                         │
│   https://pay2igr.igrmaharashtra.gov.in                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│ /eDisplay/Propertydetails/index  ← Property Search Form         │
│ /eDisplay/captcha-image          ← CAPTCHA Image               │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘

         │
         │
         ▼
┌───────────────────┐         ┌──────────────────────────────────┐
│  Local Storage    │         │      Output                      │
├───────────────────┤         ├──────────────────────────────────┤
│                   │         │                                  │
│ captcha.png       │         │ responses/                       │
│                   │         │   ├── property_1.html            │
│                   │         │   ├── property_2.html            │
│                   │         │   └── property_N.html            │
│                   │         │                                  │
└───────────────────┘         └──────────────────────────────────┘
```

## Detailed Request Flow

```
┌──────────┐
│  START   │
└────┬─────┘
     │
     ▼
┌─────────────────────────────────────────┐
│ 1. Create Session                       │
│    - Initialize requests.Session()      │
│    - Set User-Agent header              │
│    - Enable cookie persistence          │
└────┬────────────────────────────────────┘
     │
     ▼
┌─────────────────────────────────────────┐
│ 2. GET Property Details Page            │
│    URL: /eDisplay/Propertydetails/index │
│    Response: HTML form                   │
└────┬────────────────────────────────────┘
     │
     ▼
┌─────────────────────────────────────────┐
│ 3. Parse HTML & Extract CSRF Token      │
│    - Find <input name="_csrfToken">     │
│    - Extract value attribute            │
└────┬────────────────────────────────────┘
     │
     ▼
┌─────────────────────────────────────────┐
│ 4. GET CAPTCHA Image                    │
│    URL: /eDisplay/captcha-image         │
│    - Use SAME session (important!)      │
│    - Save to captcha.png                │
└────┬────────────────────────────────────┘
     │
     ▼
┌─────────────────────────────────────────┐
│ 5. Read CAPTCHA with EasyOCR            │
│    - reader.readtext('captcha.png')     │
│    - Extract text from results          │
│    - Clean/normalize text               │
│    - Fallback to manual if fails        │
└────┬────────────────────────────────────┘
     │
     ▼
┌─────────────────────────────────────────┐
│ 6. Prepare Form Data                    │
│    - _csrfToken: [from step 3]          │
│    - captcha: [from step 5]             │
│    - district_id: 23                    │
│    - taluka_id: 1                       │
│    - village_id: 43                     │
│    - free_text: "1" (property number)   │
│    - yearsel: "2026"                    │
│    - ... (other fields)                 │
└────┬────────────────────────────────────┘
     │
     ▼
┌─────────────────────────────────────────┐
│ 7. POST Property Search                 │
│    URL: /eDisplay/Propertydetails/index │
│    Method: POST                          │
│    Headers:                              │
│      - Referer: [property URL]          │
│      - Origin: [base URL]               │
│    Data: [form payload from step 6]     │
└────┬────────────────────────────────────┘
     │
     ▼
┌─────────────────────────────────────────┐
│ 8. Receive & Save Response              │
│    - Get HTML response                   │
│    - Save to responses/property_1.html  │
│    - Report success                      │
└────┬────────────────────────────────────┘
     │
     ▼
┌──────────┐
│   END    │
└──────────┘
```

## Component Interaction

```
search_property.py (Main Script)
├── create_session()
│   └── requests.Session()
│
├── get_property_page(session)
│   └── session.get(PROPERTY_URL)
│
├── get_csrf_token(html)
│   └── BeautifulSoup(html).find('input', name='_csrfToken')
│
├── download_captcha(session)
│   └── session.get(CAPTCHA_URL)
│   └── Path('captcha.png').write_bytes()
│
├── read_captcha(captcha_path)
│   └── easyocr.Reader.readtext(captcha_path)
│   └── extract & clean text
│
├── search_property(session, csrf_token, captcha)
│   └── session.post(PROPERTY_URL, data=payload)
│
└── main()
    └── orchestrates all above functions
```

## Session & Cookie Management

```
┌────────────────────────────────────────────────────────────┐
│                  requests.Session()                         │
├────────────────────────────────────────────────────────────┤
│                                                             │
│  Purpose: Maintain state across multiple HTTP requests     │
│                                                             │
│  Features:                                                  │
│  ✓ Automatic cookie persistence                           │
│  ✓ Connection pooling                                      │
│  ✓ Default headers                                         │
│                                                             │
│  Why it's critical:                                        │
│  - CAPTCHA is tied to session                              │
│  - CSRF token validation requires same session             │
│  - Portal tracks user state in cookies                     │
│                                                             │
└────────────────────────────────────────────────────────────┘

Request 1: GET /Propertydetails/index
├── Server sets: Set-Cookie: PHPSESSID=abc123...
└── Session stores: Cookie: PHPSESSID=abc123...

Request 2: GET /captcha-image  
├── Session sends: Cookie: PHPSESSID=abc123...
└── Server links CAPTCHA to session abc123

Request 3: POST /Propertydetails/index (with CAPTCHA answer)
├── Session sends: Cookie: PHPSESSID=abc123...
└── Server validates: CAPTCHA for session abc123 ✓
```

## EasyOCR Integration

```
┌────────────────────────────────────────────────────────────┐
│                    EasyOCR Workflow                         │
├────────────────────────────────────────────────────────────┤
│                                                             │
│  1. Initialize (one-time)                                  │
│     reader = easyocr.Reader(['en'], gpu=False)            │
│     - Downloads language model on first run                │
│     - Cached for subsequent uses                           │
│                                                             │
│  2. Read Image                                             │
│     result = reader.readtext('captcha.png')               │
│     - Returns: [(bbox, text, confidence), ...]            │
│                                                             │
│  3. Extract Text                                           │
│     for bbox, text, confidence in result:                 │
│         captcha_text += text                              │
│     - Concatenate all detected text                        │
│     - Remove whitespace                                    │
│                                                             │
│  4. Confidence Check                                       │
│     if confidence < threshold:                             │
│         fallback to manual entry                           │
│                                                             │
└────────────────────────────────────────────────────────────┘
```

## Error Handling Strategy

```
┌────────────────────────────────────────────────────────────┐
│                   Error Handling Layers                     │
├────────────────────────────────────────────────────────────┤
│                                                             │
│  Layer 1: Network Errors                                   │
│  ├── Timeout → retry with longer timeout                   │
│  ├── Connection error → check internet                     │
│  └── 500 error → portal is down                           │
│                                                             │
│  Layer 2: Parsing Errors                                   │
│  ├── CSRF token not found → portal structure changed       │
│  ├── Form fields missing → inspect HTML                    │
│  └── Invalid response → check response content             │
│                                                             │
│  Layer 3: CAPTCHA Errors                                   │
│  ├── OCR fails → fallback to manual entry                  │
│  ├── Empty CAPTCHA → re-download                          │
│  └── Wrong CAPTCHA → session expired, restart              │
│                                                             │
│  Layer 4: Validation Errors                                │
│  ├── Invalid property number → check config               │
│  ├── Invalid district/taluka → verify IDs                  │
│  └── Form validation error → check payload                 │
│                                                             │
└────────────────────────────────────────────────────────────┘
```

## Batch Processing Flow

```
batch_search.py

FOR property_num in range(1, 10):
    │
    ├── Create NEW session
    │   └── (fresh cookies for each property)
    │
    ├── GET property page
    │   └── Extract CSRF token
    │
    ├── GET CAPTCHA
    │   └── Read with OCR
    │
    ├── POST search (with property_num)
    │   └── Save to property_{num}.html
    │
    ├── Success → add to success list
    │   Failure → add to failed list
    │
    └── Sleep(2 seconds)
        └── (rate limiting, be nice to server)

END FOR

Print summary:
├── Successful: [1, 2, 3, 4, 5]
└── Failed: [6 (CAPTCHA failed), 7 (timeout)]
```

## Data Flow Summary

```
User Config (config.py)
    ↓
Session Creation (session.py)
    ↓
HTTP Request (requests)
    ↓
HTML Response
    ↓
Parse with BeautifulSoup (form_parser.py)
    ↓
Extract CSRF Token
    ↓
Download CAPTCHA Image
    ↓
OCR with EasyOCR
    ↓
Form Submission (search_property.py)
    ↓
HTML Response
    ↓
Save to File (responses/property_1.html)
```

## Security Considerations

```
✓ CSRF Protection
  - Token extracted from form
  - Included in POST request
  
✓ Session Management
  - Cookies maintained across requests
  - No manual cookie handling needed
  
✓ Rate Limiting
  - Delay between batch requests
  - Avoid overwhelming server
  
✓ User-Agent
  - Identifies as curl/8.13.0
  - Mimics legitimate client
  
✓ HTTPS
  - All requests over secure connection
  - No sensitive data exposure
```

## Performance Optimization

```
Single Request:
├── Network: ~2-3 seconds
├── CAPTCHA Download: ~1 second
├── OCR Processing: ~2-5 seconds
└── Total: ~5-10 seconds per property

Batch Processing (10 properties):
├── Sequential: ~50-100 seconds
├── With 2s delay: ~70-120 seconds
└── Parallelization: Not recommended (rate limiting)

Optimization Opportunities:
├── Pre-load EasyOCR model (one-time init)
├── Reuse session if possible (portal may allow)
├── Cache district/taluka/village IDs
└── Parallel processing (with caution)
```
