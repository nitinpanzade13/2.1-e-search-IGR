import base64
import io
import re
from typing import Optional
from collections import Counter
import openai
from PIL import Image, ImageFilter, ImageOps

from app.scraper.client.captcha import CaptchaSolver
from app.core.config import settings

PROMPT = (
    "The image is a CAPTCHA from a government records website.\n"
    "It contains exactly 6 characters drawn from A-Z, a-z "
    "and 0-9, in a bold sans-serif font on a speckled background.\n"
    "Read it character by character, left to right. The characters are "
    "CASE SENSITIVE - judge case from a letter's height relative to its "
    "neighbours, not from its shape alone. Ignore the background specks "
    "and any stray dots touching the letters.\n"
    "Look twice at the usual confusions: 0/O/o, 1/l/I, 2/Z/z, 5/S/s, "
    "6/G, 7/T, 8/B, 9/g/q, U/V, c/C, k/K, m/M, w/W, x/X, y/Y, z/Z.\n"
    "Answer with the 6 characters and nothing else: no "
    "spaces, no quotes, no punctuation, no explanation."
)

_JUNK = re.compile(r"[^A-Za-z0-9]")

class OpenAICaptchaSolver(CaptchaSolver):
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or settings.OPENAI_API_KEY
        if not self.api_key:
            raise ValueError("OpenAI API key is required but not configured.")
        self.client = openai.OpenAI(api_key=self.api_key, timeout=30.0)

    def _preprocess(self, raw: bytes) -> bytes:
        try:
            image = Image.open(io.BytesIO(raw)).convert("L")
            image = image.filter(ImageFilter.MedianFilter(3))
            image = ImageOps.autocontrast(image)
            
            width, height = image.size
            image = image.resize(
                (width * 4, height * 4),
                Image.LANCZOS,
            )
            
            buffer = io.BytesIO()
            image.save(buffer, format="PNG")
            return buffer.getvalue()
        except Exception:
            return raw

    def solve(self, image_bytes: bytes) -> str:
        if not image_bytes:
            raise ValueError("Empty image bytes")
            
        processed_bytes = self._preprocess(image_bytes)
        image_b64 = base64.b64encode(processed_bytes).decode("ascii")

        request = {
            "model": settings.OPENAI_CAPTCHA_MODEL,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": PROMPT},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/png;base64,{image_b64}",
                                "detail": "high",
                            },
                        },
                    ],
                }
            ],
            "max_tokens": 16,
            "n": 3,
            "temperature": 0.5,
        }

        try:
            response = self.client.chat.completions.create(**request)
        except openai.AuthenticationError as e:
            raise ValueError(f"OpenAI Authentication Error: {e}") from e
        except openai.APIError as e:
            raise RuntimeError(f"OpenAI API Error: {e}") from e
        except openai.OpenAIError as e:
            raise RuntimeError(f"OpenAI Network Error: {e}") from e

        answers = []
        for choice in response.choices:
            if not choice.message.content:
                continue
            answer = _JUNK.sub("", choice.message.content.strip())
            if len(answer) == 6:
                answers.append(answer)

        if not answers:
            raise ValueError("Model did not return any usable 6-character answers.")

        winner, _ = Counter(answers).most_common(1)[0]
        return winner
