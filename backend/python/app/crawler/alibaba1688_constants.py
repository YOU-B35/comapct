"""1688 purchase crawl constants (Day0 placeholders).

STOCKOUT_KEYWORDS and PURCHASE_LIST_URL must be filled from a real buyer
Day0 probe (docs/superpowers/specs/attachments/1688-purchase-xhr.md)
before any Task 6 live sync claim. Do not invent keywords or URLs.
"""

STOCKOUT_KEYWORDS = [
    # filled from Day0, e.g. "缺货", "无货"
]

LOGIN_OK_URL_SUBSTRINGS = ["1688.com"]
PURCHASE_LIST_URL = ""  # from Day0
