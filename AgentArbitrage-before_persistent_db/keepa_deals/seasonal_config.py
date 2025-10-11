# keepa_deals/seasonal_config.py

SEASONAL_KEYWORD_MAP = {
    "Textbook": {
        "keywords": [
            "textbook", "student edition", "instructor's edition", "college", 
            "university", "school", "academic", "study guide"
        ],
        "peak_season": "Aug-Sep, Jan-Feb",
        "trough_season": "Apr-May"
    },
    "Gardening": {
        "keywords": ["gardening", "horticulture", "planting", "landscaping", "garden"],
        "peak_season": "Mar-Apr",
        "trough_season": "Sep-Oct"
    },
    "Law School": {
        "keywords": ["law school", "lsat", "bar exam", "legal writing", "casebook"],
        "peak_season": "May-Jul",
        "trough_season": "Nov-Dec"
    },
    "Holiday": {
        "keywords": [
            "holiday", "christmas", "xmas", "hanukkah", "halloween", "easter", 
            "advent", "thanksgiving"
        ],
        "peak_season": "Oct-Dec",
        "trough_season": "Jan-Feb"
    },
    "Grilling & BBQ": {
        "keywords": ["grilling", "barbecue", "bbq", "smoker", "outdoor cooking"],
        "peak_season": "May-Jul",
        "trough_season": "Nov-Jan"
    }
}
