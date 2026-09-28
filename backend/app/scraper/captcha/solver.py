import os
import base64
import io
import re
from openai import OpenAI
from PIL import Image, ImageFilter, ImageOps

OPENAI_MODEL = "gpt-4o"
OPENAI_IMAGE_DETAIL = "high"
CAPTCHA_LENGTH = 6
CAPTCHA_VOTES = 3
CAPTCHA_TEMPERATURE = 0.7

PROMPT = (
    "The image is a CAPTCHA from a government records website.\n"
    f"It contains exactly {CAPTCHA_LENGTH} characters drawn from A-Z, a-z "
    "and 0-9, in a bold sans-serif font on a speckled background.\n"
    "Read it character by character, left to right. The characters are "
    "CASE SENSITIVE - judge case from a letter's height relative to its "
    "neighbours, not from its shape alone. Ignore the background specks "
    "and any stray dots touching the letters.\n"
    "Look twice at the usual confusions: 0/O/o, 1/l/I, 2/Z/z, 5/S/s, "
    "6/G, 7/T, 8/B, 9/g/q, U/V, c/C, k/K, m/M, w/W, x/X, y/Y, z/Z.\n"
    f"Answer with the {CAPTCHA_LENGTH} characters and nothing else: no "
    "spaces, no quotes, no punctuation, no explanation."
)

_JUNK = re.compile(r"[^A-Za-z0-9]")

def _preprocess(raw):
    try:
        image = Image.open(io.BytesIO(raw)).convert("L")
        image = image.filter(ImageFilter.MedianFilter(3))
        image = ImageOps.autocontrast(image)
        width, height = image.size
        image = image.resize((width * 3, height * 3), Image.LANCZOS)
        buffer = io.BytesIO()
        image.save(buffer, format="PNG")
        return buffer.getvalue()
    except Exception as exc:
        print(f"CAPTCHA preprocessing failed: {exc}")
        return raw

def _clean(text):
    if not text:
        return ""
    return _JUNK.sub("", text.strip())

def read_captcha(raw_bytes: bytes, api_key: str):
    if not api_key:
        print("No OpenAI API key provided. Falling back to file entry.")
        path = "storage/captcha.png"
        text_path = "storage/captcha.txt"
        if os.path.exists(text_path):
            os.remove(text_path)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as f:
            f.write(raw_bytes)
        print(f"\nCAPTCHA image saved to: {os.path.abspath(path)}")
        print(f"Please write the 6-character CAPTCHA to {os.path.abspath(text_path)} to continue...")
        import time
        while not os.path.exists(text_path):
            time.sleep(1)
        with open(text_path, "r") as f:
            text = f.read().strip()
        os.remove(text_path)
        return text

    client = OpenAI(api_key=api_key, timeout=60)
    image_b64 = base64.b64encode(_preprocess(raw_bytes)).decode("ascii")
    
    request = {
        "model": OPENAI_MODEL,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": PROMPT},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/png;base64,{image_b64}",
                            "detail": OPENAI_IMAGE_DETAIL,
                        },
                    },
                ],
            }
        ],
        "max_tokens": 16,
        "n": CAPTCHA_VOTES,
        "temperature": CAPTCHA_TEMPERATURE,
    }
    
    response = client.chat.completions.create(**request)
    answers = []
    for choice in response.choices:
        answer = _clean(choice.message.content)
        if len(answer) == CAPTCHA_LENGTH:
            answers.append(answer)
            
    if not answers:
        return None
        
    from collections import Counter
    winner, _ = Counter(answers).most_common(1)[0]
    return winner
