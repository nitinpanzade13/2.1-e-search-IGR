import re
from typing import List, Dict

class CandidatePropertyParser:
    """
    A conservative regex-based parser designed ONLY to extract candidate 
    discovery identifiers (like survey number, plot number) from raw Marathi text.
    
    It intentionally does not fail or raise exceptions if the format is unrecognized,
    as this is non-authoritative phase-1 discovery data.
    """
    
    # Common patterns observed in IGR Maharashtra portal:
    # स. क्र. 20 हिस्सा क्र. 4 (Survey No 20 Hissa No 4)
    # सि.टी.सर्वे नं. 66 (CTS No 66)
    # प्लॉट क्र 12 (Plot No 12)
    # गट क्र. (Gut No)
    
    SURVEY_PATTERN = re.compile(r"(?:स\.?\s*क्र\.?|सर्वे\s*नं\.?|गट\s*क्र\.?|सि\.टी\.सर्वे\s*नं\.?)[\s(]*([\d/a-zA-Z]+)[\s)]*")
    PLOT_PATTERN = re.compile(r"(?:प्लॉट\s*क्र\.?|प्लॉट\s*नं\.?|प्लॉट\s*नंबर|प्लॉट\s*न\.)[\s(]*([\d/a-zA-Z]+)[\s)]*")
    HISSA_PATTERN = re.compile(r"(?:हिस्सा\s*क्र\.?|हिस्सा\s*नं\.?)[\s(]*([\d/a-zA-Z]+)[\s)]*")
    
    @classmethod
    def parse(cls, other_info_raw: str) -> List[Dict[str, str]]:
        if not other_info_raw:
            return []
            
        candidates = []
        try:
            surveys = cls.SURVEY_PATTERN.findall(other_info_raw)
            plots = cls.PLOT_PATTERN.findall(other_info_raw)
            hissas = cls.HISSA_PATTERN.findall(other_info_raw)
            
            # Simple grouping logic
            max_len = max(len(surveys), len(plots), 1)
            
            for i in range(max_len):
                candidate = {}
                if i < len(surveys):
                    candidate["survey"] = surveys[i]
                if i < len(plots):
                    candidate["plot"] = plots[i]
                if i < len(hissas):
                    candidate["hissa"] = hissas[i]
                    
                if candidate:
                    candidates.append(candidate)
                    
        except Exception:
            # Safe fallback: never crash registration persistence over discovery parsing
            pass
            
        return candidates
