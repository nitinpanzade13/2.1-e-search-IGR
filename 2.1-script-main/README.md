# IGR Maharashtra Property Search Automation

Automated tool to fetch property details from the IGR Maharashtra portal. CAPTCHAs are read by an OpenAI vision model, so bulk runs need nobody at the keyboard.

## Features

- ✅ Automatic CSRF token extraction
- ✅ CAPTCHA download and automatic reading (OpenAI vision model)
- ✅ Property search form submission
- ✅ Bulk search across years and survey numbers, resumable at any point
- ✅ IP rotation when the portal's daily quota trips
- ✅ Falls back to manual CAPTCHA entry if the model is unavailable

## Installation

1. Create a virtual environment (recommended):
```cmd
python -m venv venv
venv\Scripts\activate
```

2. Install dependencies:
```cmd
pip install -r requirements.txt
```

3. Create your `.env` from the template (this file is gitignored, so your
   settings never leave your machine):
```cmd
copy .env.example .env
```

Then put your OpenAI key in it:
```
OPENAI_API_KEY=sk-...
```

Without a key the scripts still run — they just ask you to type each CAPTCHA.

4. Check the setup:
```cmd
python test_setup.py
```

## Configuration

**Everything you need to change lives in `.env`.** `config.py` holds the
defaults (Kharadi / Haveli / Pune); any line you set in `.env` overrides
the matching default, and anything you leave out keeps it. You should not
have to edit `config.py` at all.

### Which village to scrape

The portal identifies places by numeric ids that are impossible to guess, so
a helper asks the portal for them:

```cmd
python setup_location.py
```

It lists the districts, then the talukas in the one you pick, then the
villages — filter by typing a name in either script (`kharadi` finds
खराडी) — and prints the finished `.env` lines to paste in:

```
IGR_DISTRICT=पुणे
IGR_TALUKA=हवेली
IGR_VILLAGE=खराडी (पुणे महापालिकेमध्ये समाविष्ट)

IGR_DISTRICT_ID=23
IGR_TALUKA_ID=1
IGR_VILLAGE_ID=43

IGR_CSV_PREFIX=kharadi_haveli_pune
```

Copy all of them together — the names are posted alongside the ids and have
to describe the same place.

### What to search

```
IGR_SURVEY_START=1
IGR_SURVEY_END=99
IGR_YEARS=2026,2025,2024,2023,2022,2021,2020,2019
IGR_TARGET_UNIQUE_ROWS=100000
```

Years run newest first and the run stops early once the target is reached.
The portal holds nothing for 2003–2011.

### Wi-Fi rotation

The portal caps searches per IP per day. When it refuses, the scraper hops to
a second network and back to your phone's hotspot, which makes the carrier
hand out a fresh IP. The profile names are whatever Windows has saved on your
PC, so they differ for everyone:

```cmd
python setup_location.py --wifi
```

That prints your saved networks and your interface name. Pick two:

```
IGR_HOTSPOT_PROFILE=Galaxy M51DFA7     your phone's hotspot
IGR_PARKING_PROFILE=Airtel_Prathmesh   any other saved network
IGR_WIFI_INTERFACE=Wi-Fi
```

The parking network is only somewhere to sit for a few seconds so the
disconnect is real — it does not matter which one it is.

## Usage

Bulk search — the main entry point. Walks every survey number across every configured year, appending to one CSV and resuming wherever it left off:

```cmd
python scrape.py              resume (or start) the full job
python scrape.py --yes        ... without the confirmation prompt
python scrape.py --status     show progress without searching
python scrape.py --reset      forget progress and start over
```

Single search, useful for a quick check:

```cmd
python search_property.py
```

### What it does:

1. Opens a session with the IGR portal
2. Fetches the property search page
3. Extracts the CSRF token
4. Downloads the CAPTCHA image to `captcha.png`
5. **Reads the CAPTCHA with an OpenAI vision model**
6. Submits the property search form
7. Saves the response and appends new rows to the CSV

## CAPTCHA solving

`captcha_solver.py` handles this for every script. It cleans the image up
before sending it — a median filter at native resolution wipes the speckled
background, then the image is enlarged — and samples the model three times,
taking the majority answer. The image is uploaded once, so the extra votes
cost almost nothing and cut the number of rejected guesses, which matters
because every wrong answer spends one of the day's searches.

The portal is the only real judge, so the scraper feeds its verdict back.
Rejected images are saved to `state/failed_captchas/` with the guess in the
filename, and the running hit rate shows up in `--status`.

Tune it in `config.py`, or override per run:

```cmd
set CAPTCHA_MODE=manual                 type every CAPTCHA yourself
set OPENAI_CAPTCHA_MODEL=gpt-4o-mini    cheaper, less accurate
```

Read an image without touching the portal:

```cmd
python captcha_solver.py captcha.png          read it
python captcha_solver.py --dry captcha.png    only show what would be sent
```

### Manual CAPTCHA fallback

The solver hands the keyboard back on its own if there is no API key, if the
key is rejected, or after 8 rejections in a row — that last one usually means
the CAPTCHA has changed, and it stops the run burning quota on bad guesses.

## Project Structure

```
igr2.1/
├── .env.example              # Template - copy to .env and edit that
├── config.py                 # Defaults; every per-user value reads .env first
├── setup_location.py         # Finds your district/taluka/village ids and Wi-Fi names
├── scrape.py                 # Bulk search - the main entry point
├── captcha_solver.py         # Reads CAPTCHAs with an OpenAI vision model
├── igr_parser.py             # Classifies responses and extracts rows
├── netswitch.py              # IP rotation when the daily quota trips
├── search_property.py        # Single search
├── session.py                # Session management
├── property_form.py          # Form parsing utilities
├── form_parser.py            # Generic form field extraction
├── portal.py                 # Portal navigation
├── requirements.txt          # Python dependencies
├── captcha.png               # Most recent CAPTCHA image
├── state/                    # Progress, dedup keys, rejected CAPTCHAs
├── output/                   # Merged CSV
└── responses/                # Raw HTML of every search
```

## Inspection Scripts

The following scripts were used during development to understand the portal:

- `inspect_property.py` - Analyze property form structure
- `inspect_form.py` - Form field inspection
- `inspect_ajax.py` - AJAX endpoint discovery
- `find_dropdown_api.py` - Dropdown API detection
- `inspect_search_form.py` - Search form analysis
- `inspect_search_js.py` - JavaScript analysis
- `search_submit_info.py` - Form submission details

## Workflow

```
1. GET Property Details page
   ↓
2. Extract CSRF token
   ↓
3. GET CAPTCHA image → captcha.png
   ↓
4. Clean it up, read it with the OpenAI model, vote on the answer
   ↓
5. POST property search
   ↓
6. Save response, append new rows to the CSV
```

## Troubleshooting

### The model keeps misreading the CAPTCHA

- Look in `state/failed_captchas/` — the filenames hold what it guessed, so
  you can see whether it is misreading the image or the CAPTCHA has changed
- `python captcha_solver.py --dry captcha.png` writes exactly what gets sent;
  if that image is dirty, adjust `CAPTCHA_DENOISE` / `CAPTCHA_UPSCALE`
- Raise `CAPTCHA_VOTES` for more agreement, or try a different
  `OPENAI_CAPTCHA_MODEL`

### "You have no credits remaining"

- The solver says so once and switches to manual entry for the rest of the run
- Add credits, or run with `CAPTCHA_MODE=manual` deliberately

### Session/Cookie issues

- The script maintains session cookies automatically
- If you get authentication errors, the portal might have changed
- Check `session.py` for headers and user-agent

## Notes

- The script uses `requests.Session()` to maintain cookies across requests
- CSRF token is extracted from the HTML form
- CAPTCHA must be solved using the same session that downloaded it
- Response is saved as-is (HTML format)
