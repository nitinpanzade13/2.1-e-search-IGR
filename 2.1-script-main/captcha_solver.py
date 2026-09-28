"""
Read the IGR portal's CAPTCHA with an OpenAI vision model.

The portal's CAPTCHA is six case-sensitive alphanumeric characters in a
bold sans-serif face, scattered over a speckled background. That is well
within reach of a vision model once the image is enlarged and the specks
are filtered out, so the scraper no longer needs a human at the keyboard.

Two things guard against a confidently wrong read:

  * the image is upscaled and denoised before it is sent, and
  * the model is sampled several times and the answers are voted on,
    which costs almost nothing extra because the image is uploaded once.

The portal itself is the only real judge, so `note_result` feeds its
verdict back here. A long run of rejections means something has changed -
the font, the length, the model - and the solver hands the keyboard back
to you rather than burning the daily search quota on guesses.

    CAPTCHA_MODE=manual python scrape.py     type them yourself
    python captcha_solver.py captcha.png     read one image and stop
"""
import base64
import io
import os
import re
import sys
import time
from collections import Counter
from pathlib import Path

from config import (
    CAPTCHA_URL,
    CAPTCHA_PATH,
    CAPTCHA_MODE,
    CAPTCHA_LENGTH,
    CAPTCHA_VOTES,
    CAPTCHA_TEMPERATURE,
    CAPTCHA_API_RETRIES,
    CAPTCHA_PREPROCESS,
    CAPTCHA_UPSCALE,
    CAPTCHA_DENOISE,
    CAPTCHA_AUTO_FAIL_STREAK,
    FAILED_CAPTCHA_DIR,
    OPENAI_MODEL,
    OPENAI_IMAGE_DETAIL,
    OPENAI_TIMEOUT,
)

# config loads .env on import - see the note there.

try:
    from PIL import Image, ImageFilter, ImageOps
except ImportError:  # Pillow is optional - the raw PNG still works.
    Image = None


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

# Failures that retrying cannot fix: no credit, bad key, no access to the
# model. Retrying these just stalls every search behind three timeouts.
_PERMANENT = (
    "insufficient_quota",
    "credit_balance_exhausted",
    "invalid_api_key",
    "account_deactivated",
    "model_not_found",
    "does not exist or you do not have access",
)

FAILED_DIR = Path(FAILED_CAPTCHA_DIR)

STATS = {
    "asked": 0,        # CAPTCHAs handed to the portal
    "accepted": 0,     # ... that the portal took
    "rejected": 0,     # ... that the portal threw back
    "unreadable": 0,   # model never produced a well-formed answer
    "api_errors": 0,
    "manual": 0,       # typed by hand
    "streak": 0,       # consecutive rejections right now
}

_client = None
_client_looked_up = False
_manual_mode = CAPTCHA_MODE == "manual"
_manual_reason = "CAPTCHA_MODE=manual" if _manual_mode else ""
_viewer_opened = False

# The last image we sent, kept so a rejection can be filed for review.
_last = {"raw": None, "guess": None}


# ---------------------------------------------------------------
# OpenAI client
# ---------------------------------------------------------------

def _get_client():
    """Build the client once; return None if there is no key to use."""

    global _client, _client_looked_up

    if _client_looked_up:
        return _client

    _client_looked_up = True

    if not os.environ.get("OPENAI_API_KEY"):
        return None

    from openai import OpenAI

    _client = OpenAI(timeout=OPENAI_TIMEOUT)

    return _client


def _fall_back_to_manual(reason):
    global _manual_mode, _manual_reason

    if _manual_mode:
        return

    _manual_mode = True
    _manual_reason = reason

    print(f"\n  ! {reason}")
    print("  ! Switching to manual CAPTCHA entry for the rest of this run.\n")


# ---------------------------------------------------------------
# Image handling
# ---------------------------------------------------------------

def _preprocess(raw):
    """
    Clean the CAPTCHA, then enlarge it, before it goes to the model.

    The order matters and the obvious one is wrong. The background specks
    are single pixels while the strokes are several wide, so a median
    filter at native resolution erases the specks and leaves the letters
    untouched. Upscale first and the resampling smears every speck into a
    soft blob the filter can no longer tell from a stroke - autocontrast
    then hardens those blobs back to black and the image comes out dirtier
    than it started.
    """

    if not CAPTCHA_PREPROCESS or Image is None:
        return raw

    try:
        image = Image.open(io.BytesIO(raw)).convert("L")

        if CAPTCHA_DENOISE:
            image = image.filter(ImageFilter.MedianFilter(CAPTCHA_DENOISE))

        image = ImageOps.autocontrast(image)

        width, height = image.size

        image = image.resize(
            (width * CAPTCHA_UPSCALE, height * CAPTCHA_UPSCALE),
            Image.LANCZOS,
        )

        buffer = io.BytesIO()
        image.save(buffer, format="PNG")

        return buffer.getvalue()

    except Exception as exc:
        print(f"  ! CAPTCHA preprocessing failed ({exc}); sending the original")
        return raw


def download(session):
    """Fetch a fresh CAPTCHA on this session and save it to disk."""

    response = session.get(CAPTCHA_URL, timeout=60)
    response.raise_for_status()

    Path(CAPTCHA_PATH).write_bytes(response.content)

    return response.content


# ---------------------------------------------------------------
# Reading
# ---------------------------------------------------------------

def _clean(text):
    """Strip anything that is not a character of the answer."""

    if not text:
        return ""

    return _JUNK.sub("", text.strip())


def _ask_model(client, raw):
    """Sample the model on one image; return every well-formed answer."""

    image_b64 = base64.b64encode(_preprocess(raw)).decode("ascii")

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
    }

    # One sample is a straight answer; several are votes, and they need
    # some temperature or the model just repeats itself.
    if CAPTCHA_VOTES > 1:
        request["n"] = CAPTCHA_VOTES
        request["temperature"] = CAPTCHA_TEMPERATURE
    else:
        request["temperature"] = 0

    response = client.chat.completions.create(**request)

    answers = []

    for choice in response.choices:
        answer = _clean(choice.message.content)

        if len(answer) == CAPTCHA_LENGTH:
            answers.append(answer)

    return answers


def _vote(answers):
    """Pick the answer the samples agree on, plus how strong that was."""

    if not answers:
        return None, 0

    winner, votes = Counter(answers).most_common(1)[0]

    return winner, votes


def read(raw):
    """
    Read one CAPTCHA image.

    Returns the text, or None if the model never produced a well-formed
    answer - transient API failures are retried, a bad read is not.
    """

    client = _get_client()

    if client is None:
        _fall_back_to_manual("OPENAI_API_KEY is not set")
        return None

    answers = []

    for attempt in range(1, CAPTCHA_API_RETRIES + 1):

        try:
            answers = _ask_model(client, raw)
            break

        except Exception as exc:
            STATS["api_errors"] += 1

            detail = str(exc)

            if any(marker in detail for marker in _PERMANENT):
                _fall_back_to_manual(f"OpenAI rejected the request: {detail}")
                return None

            print(f"  ! OpenAI call failed ({attempt}/{CAPTCHA_API_RETRIES}): {detail}")

            if attempt == CAPTCHA_API_RETRIES:
                return None

            time.sleep(2 * attempt)

    guess, votes = _vote(answers)

    if guess is None:
        STATS["unreadable"] += 1
        print(f"  ! model did not return {CAPTCHA_LENGTH} usable characters")
        return None

    if CAPTCHA_VOTES > 1:
        print(f"  read {guess!r} ({votes}/{len(answers)} agree)")
    else:
        print(f"  read {guess!r}")

    return guess


# ---------------------------------------------------------------
# Manual entry
# ---------------------------------------------------------------

def _ask_human():
    """Show the image and wait for the user to type what they see."""

    global _viewer_opened

    path = Path(CAPTCHA_PATH)

    # Only launch a viewer for the first one. The path never changes, so
    # an editor preview or image window refreshes in place - opening it
    # every round would leave hundreds of windows behind.
    if not _viewer_opened:
        _viewer_opened = True

        try:
            os.startfile(path)  # noqa: S606 - Windows image viewer
        except Exception:
            pass

        print(f"\n  CAPTCHA image: {path.absolute()}")
        print("  Tip: keep it open in VS Code - the preview refreshes itself.\n")

    text = input(
        f"  CAPTCHA ({CAPTCHA_LENGTH} chars, case-sensitive, blank to skip): "
    ).strip()

    if text:
        STATS["manual"] += 1

    return text


# ---------------------------------------------------------------
# What the scraper calls
# ---------------------------------------------------------------

def solve(session):
    """
    Produce a CAPTCHA answer for this session.

    Downloads a fresh image and reads it. Returns the text to submit,
    None if the model could not read this image - fetch a new one and
    call again, no human needed - or "" if the user skipped it while
    typing them by hand.
    """

    raw = download(session)

    if _manual_mode:
        guess = _ask_human()

    else:
        guess = read(raw)

        # read() may have just given up on automatic solving for good.
        # If it has, ask rather than discarding this CAPTCHA.
        if guess is None and _manual_mode:
            guess = _ask_human()

    _last["raw"] = raw
    _last["guess"] = guess

    if guess:
        STATS["asked"] += 1

    return guess


def note_result(accepted):
    """
    Record what the portal made of the last answer.

    Rejections are filed to disk with the guess in the filename, which is
    what you want when the hit rate drops and you need to see whether the
    model is misreading the image or the CAPTCHA itself has changed.
    """

    if not _last["guess"]:
        return

    if accepted:
        STATS["accepted"] += 1
        STATS["streak"] = 0
        return

    STATS["rejected"] += 1
    STATS["streak"] += 1

    if not _manual_mode and _last["raw"]:
        try:
            FAILED_DIR.mkdir(parents=True, exist_ok=True)

            name = f"{int(time.time())}_{_last['guess']}.png"
            (FAILED_DIR / name).write_bytes(_last["raw"])

        except Exception:
            pass

    if not _manual_mode and STATS["streak"] >= CAPTCHA_AUTO_FAIL_STREAK:
        _fall_back_to_manual(
            f"{STATS['streak']} CAPTCHAs rejected in a row - "
            f"see {FAILED_DIR.absolute()}"
        )


def accuracy():
    """Share of submitted CAPTCHAs the portal accepted, or None."""

    judged = STATS["accepted"] + STATS["rejected"]

    if not judged:
        return None

    return STATS["accepted"] / judged


def describe():
    """One-line summary of how the solving is going, for the status block."""

    rate = accuracy()

    if rate is None:
        return "no CAPTCHAs submitted yet"

    mode = "manual" if _manual_mode else f"auto ({OPENAI_MODEL})"

    return (
        f"{mode}: {STATS['accepted']}/{STATS['accepted'] + STATS['rejected']} "
        f"accepted ({rate:.0%})"
        + (f", {STATS['unreadable']} unreadable" if STATS["unreadable"] else "")
        + (f", {STATS['manual']} typed by hand" if STATS["manual"] else "")
    )


def banner():
    """What the scraper prints before it starts, so the mode is obvious."""

    if _manual_mode:
        return f"CAPTCHAs: manual entry ({_manual_reason or 'chosen in config'})"

    if not os.environ.get("OPENAI_API_KEY"):
        return "CAPTCHAs: manual entry (no OPENAI_API_KEY in the environment)"

    votes = f", best of {CAPTCHA_VOTES}" if CAPTCHA_VOTES > 1 else ""

    return f"CAPTCHAs: solved automatically by {OPENAI_MODEL}{votes}"


# ---------------------------------------------------------------
# Standalone check
# ---------------------------------------------------------------

def main():
    """
    Read image files given on the command line - handy for tuning.

        python captcha_solver.py                 read captcha.png
        python captcha_solver.py state/failed_captchas/*.png
        python captcha_solver.py --dry captcha.png   preprocess only

    `--dry` writes what the model would have been shown next to the
    original, so the upscale and denoise settings can be judged by eye
    without spending anything on the API.
    """

    args = [arg for arg in sys.argv[1:] if not arg.startswith("--")]
    dry_run = "--dry" in sys.argv

    paths = [Path(arg) for arg in args] or [Path(CAPTCHA_PATH)]

    for path in paths:

        if not path.exists():
            print(f"{path}: not found")
            continue

        print(f"\n{path}")

        raw = path.read_bytes()

        if dry_run:
            preview = path.with_name(path.stem + "_sent.png")
            preview.write_bytes(_preprocess(raw))

            print(f"  -> would send {preview}")
            continue

        answer = read(raw)

        print(f"  -> {answer or 'unreadable'}")


if __name__ == "__main__":
    main()
