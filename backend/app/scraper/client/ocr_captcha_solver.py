"""
OCR-based CAPTCHA solver using Tesseract as a fallback/alternative to OpenAI.
"""
import base64
import io
import re
from typing import Optional
import logging
from PIL import Image, ImageFilter, ImageOps

from app.scraper.client.captcha import CaptchaSolver
from app.core.config import settings

logger = logging.getLogger(__name__)

_JUNK = re.compile(r"[^A-Za-z0-9]")

class OCRCaptchaSolver(CaptchaSolver):
    """
    OCR-based CAPTCHA solver using Tesseract.
    This is a fallback when OpenAI API is rate-limited or unavailable.
    """
    def __init__(self):
        self._tesseract_available = self._check_tesseract()
        if not self._tesseract_available:
            logger.warning("Tesseract OCR not available. OCRCaptchaSolver will fail.")
    
    def _check_tesseract(self) -> bool:
        """Check if Tesseract OCR is available on the system."""
        try:
            import pytesseract
            # Try to get version to verify it's installed
            pytesseract.get_tesseract_version()
            return True
        except pytesseract.TesseractNotFoundError:
            logger.warning("Tesseract not found. Please install Tesseract OCR:")
            logger.warning("  Windows: Download from https://github.com/UB-Mannheim/tesseract/wiki")
            logger.warning("  Linux: sudo apt-get install tesseract-ocr")
            logger.warning("  macOS: brew install tesseract")
            return False
        except Exception as e:
            logger.warning(f"Tesseract check failed: {e}")
            return False
    
    def _preprocess(self, raw: bytes) -> Image.Image:
        """
        Preprocess CAPTCHA image for better OCR accuracy.
        Based on the original preprocessing from captcha_solver.py.
        """
        try:
            # Convert to grayscale
            image = Image.open(io.BytesIO(raw)).convert("L")
            
            # Denoise with median filter (removes background specks)
            image = image.filter(ImageFilter.MedianFilter(3))
            
            # Increase contrast
            image = ImageOps.autocontrast(image)
            
            # Upscale for better OCR (4x)
            width, height = image.size
            image = image.resize(
                (width * 4, height * 4),
                Image.LANCZOS,
            )
            
            # Apply threshold to make it black and white
            image = image.point(lambda x: 0 if x < 128 else 255)
            
            return image
        except Exception as e:
            logger.error(f"Image preprocessing failed: {e}")
            # Return original image if preprocessing fails
            return Image.open(io.BytesIO(raw)).convert("L")
    
    def solve(self, image_bytes: bytes) -> str:
        """
        Solve CAPTCHA using OCR.
        Returns 6-character string or raises ValueError.
        """
        if not image_bytes:
            raise ValueError("Empty image bytes")
        
        if not self._tesseract_available:
            raise RuntimeError("Tesseract OCR not available")
        
        try:
            import pytesseract
            
            # Preprocess image
            image = self._preprocess(image_bytes)
            
            # Configure Tesseract for alphanumeric text
            custom_config = r'--oem 3 --psm 8 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789'
            
            # Extract text
            text = pytesseract.image_to_string(image, config=custom_config)
            
            # Clean the text
            cleaned = _JUNK.sub("", text.strip())
            
            if len(cleaned) == 6:
                logger.info(f"OCR solved CAPTCHA: {cleaned}")
                return cleaned
            elif len(cleaned) > 6:
                # Take first 6 characters if OCR returned more
                result = cleaned[:6]
                logger.warning(f"OCR returned {len(cleaned)} chars, using first 6: {result}")
                return result
            else:
                raise ValueError(f"OCR returned {len(cleaned)} characters, expected 6. Text: '{cleaned}'")
                
        except ImportError:
            raise RuntimeError("pytesseract not installed. Install with: pip install pytesseract")
        except Exception as e:
            raise ValueError(f"OCR failed: {str(e)}")

class HybridCaptchaSolver(CaptchaSolver):
    """
    Hybrid CAPTCHA solver that tries multiple methods in order:
    1. First try OpenAI (if available)
    2. Fall back to OCR if OpenAI fails or is rate-limited
    3. Fall back to simple pattern matching as last resort
    """
    def __init__(self):
        self.ocr_solver = OCRCaptchaSolver()
        self.openai_solver = None
        
        # Try to create OpenAI solver, but don't fail if not available
        try:
            from app.scraper.client.openai_captcha_solver import OpenAICaptchaSolver
            self.openai_solver = OpenAICaptchaSolver()
            logger.info("HybridCaptchaSolver: OpenAI solver available")
        except Exception as e:
            logger.warning(f"HybridCaptchaSolver: OpenAI solver not available: {e}")
        
        # Check if at least one method is available
        if not self.openai_solver and not self.ocr_solver._tesseract_available:
            logger.error("HybridCaptchaSolver: No CAPTCHA solving methods available!")
            logger.error("  Install options:")
            logger.error("  1. Set OPENAI_API_KEY for OpenAI solving")
            logger.error("  2. Install Tesseract OCR for local solving")
            logger.error("  3. Use manual CAPTCHA entry mode")
    
    def solve(self, image_bytes: bytes) -> str:
        """Try multiple CAPTCHA solving methods."""
        methods_tried = []
        
        # Method 1: Try OpenAI first (if available)
        if self.openai_solver:
            try:
                methods_tried.append("OpenAI")
                result = self.openai_solver.solve(image_bytes)
                logger.info("CAPTCHA solved with OpenAI")
                return result
            except Exception as e:
                logger.warning(f"OpenAI CAPTCHA solver failed: {e}")
                # Check if it's a rate limit error
                if "rate limit" in str(e).lower() or "429" in str(e):
                    logger.info("OpenAI rate limited, falling back to OCR")
        
        # Method 2: Try OCR
        try:
            methods_tried.append("OCR")
            result = self.ocr_solver.solve(image_bytes)
            logger.info("CAPTCHA solved with OCR")
            return result
        except Exception as e:
            logger.warning(f"OCR CAPTCHA solver failed: {e}")
        
        # Method 3: Last resort - raise informative error
        methods_str = ", ".join(methods_tried)
        error_msg = f"All CAPTCHA solving methods failed ({methods_str})."
        error_msg += "\nSolutions:"
        error_msg += "\n  1. Install Tesseract OCR: https://github.com/UB-Mannheim/tesseract/wiki (Windows)"
        error_msg += "\n  2. Set OPENAI_API_KEY environment variable for OpenAI solving"
        error_msg += "\n  3. Implement manual CAPTCHA entry mode"
        raise ValueError(error_msg)