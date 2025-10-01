import re

def classify_seasonality(title, categories_sub, manufacturer):
    """
    Classifies a book's seasonality based on title, categories, and manufacturer.

    Args:
        title (str): The title of the book.
        categories_sub (str): The sub-category string.
        manufacturer (str): The manufacturer/publisher of the book.

    Returns:
        str: The classified season, or "General" if no specific season is found.
    """
    if not title: title = ""
    if not categories_sub: categories_sub = ""
    if not manufacturer: manufacturer = ""

    title_lower = title.lower()
    cat_lower = categories_sub.lower()
    mfr_lower = manufacturer.lower()

    # --- Textbook Classifications ---
    textbook_publishers = ['cengage', 'mcgraw-hill', 'pearson', 'wiley', 'macmillan', 'sage']
    is_textbook_publisher = any(pub in mfr_lower for pub in textbook_publishers)

    if "ap" in title_lower and ("high school" in cat_lower or is_textbook_publisher):
        return "High School AP Textbooks"
    if "college" in title_lower or "university" in title_lower or is_textbook_publisher:
        if "summer" in title_lower:
            return "Summer Textbook Season"
        if "winter" in title_lower:
            return "Winter Textbook Season"
        # General textbook seasons if not specified
        return "Summer Textbook Season" # Defaulting to most common

    # --- Niche Semesters ---
    if "law school" in cat_lower or "bar exam" in title_lower:
        return "Law School"
    if "nursing" in cat_lower or "nclex" in title_lower:
        return "Nursing School"
    if "medical school" in cat_lower or "mcat" in title_lower:
        return "Medical School"
    if "community college" in cat_lower:
        return "Community College"

    # --- General Seasonal ---
    if "gardening" in cat_lower or "gardening" in title_lower:
        return "Gardening"
    if "grilling" in cat_lower or "bbq" in title_lower or "barbecue" in title_lower:
        return "Grilling/BBQ"
    if "christmas" in title_lower or "holiday" in title_lower and "gift" in title_lower:
        return "Christmas"
    if "new year" in title_lower or "fitness" in title_lower or "diet" in title_lower or "self-help" in title_lower and "resolution" in title_lower:
        return "New Year/Fitness"
    if "tax" in title_lower and ("prep" in title_lower or "guide" in title_lower):
        return "Tax Prep"
    if "travel" in cat_lower or "travel" in title_lower:
        return "Travel"
    if "halloween" in title_lower:
        return "Halloween"
    if "thanksgiving" in title_lower:
        return "Thanksgiving"
    if "valentine" in title_lower or "romance" in cat_lower:
        return "Romance/Valentine's Day"

    return "General"