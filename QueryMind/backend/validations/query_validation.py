# # input_sanitizer.py

# import re
# import unicodedata

# # ── Constants ──────────────────────────────────────────────────────────────────

MAX_QUESTION_LENGTH = 1000
# GENERIC_REJECTION_MESSAGE = "Your input could not be processed. Please rephrase your question."

# # ── Private helpers (single responsibility each) ───────────────────────────────

# def _normalize(text: str) -> str:
#     text = unicodedata.normalize("NFKC", text)
#     text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', text)
#     text = re.sub(r'[ \t]+', ' ', text).strip()
#     return text

def _check_length(text: str) -> tuple[bool, str]:
    if not text:
        return False, "Question cannot be empty."
    if len(text) > MAX_QUESTION_LENGTH:
        return False, f"Question too long. Please keep it under {MAX_QUESTION_LENGTH} characters."
    return True, "OK"

# def _check_structural_anomalies(text: str) -> tuple[bool, str]:
#     # if text.count(';') > 1:
#     #     return False, GENERIC_REJECTION_MESSAGE
#     # special_chars = sum(1 for c in text if not c.isalnum() and c not in " .,?'\"()-_/\\")
#     # if special_chars / max(len(text), 1) > 0.3:
#     #     return False, GENERIC_REJECTION_MESSAGE
#     if re.search(r'[A-Za-z0-9+/]{40,}={0,2}', text):
#         return False, GENERIC_REJECTION_MESSAGE
#     if text.count('\n') > 5:
#         return False, GENERIC_REJECTION_MESSAGE
#     return True, "OK"

# # ── Public API (only this is imported elsewhere) ───────────────────────────────

# def sanitize_input(raw_input: str) -> tuple[str, bool, str]:
#     """
#     Normalize and validate raw user input before it reaches the LLM.

#     Returns:
#         cleaned_text  : str   - normalized version of the input
#         is_safe       : bool  - True if input passed all checks
#         message       : str   - "OK" or a user-facing rejection reason
#     """
#     cleaned = _normalize(raw_input)

#     for check in (_check_length, _check_structural_anomalies):
#         ok, msg = check(cleaned)
#         if not ok:
#             return cleaned, False, msg
#     return cleaned, True, "OK"