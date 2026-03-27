import os
import logging

logger = logging.getLogger('platform_knowledge')

DOCS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'Documentation')
SELECTED_DOCS = [
    'Dashboard_Specification.md',
    'Data_Logic.md',
    'Feature_Deals_Dashboard.md',
    'INFERRED_PRICE_LOGIC.md'
]

KNOWLEDGE_CACHE = None
KNOWLEDGE_MTIME = {}

def get_platform_knowledge():
    """Reads the selected documentation files into a single context string."""
    global KNOWLEDGE_CACHE, KNOWLEDGE_MTIME

    # Check if we need to reload
    needs_reload = False
    current_mtimes = {}

    for doc in SELECTED_DOCS:
        filepath = os.path.join(DOCS_DIR, doc)
        if os.path.exists(filepath):
            mtime = os.path.getmtime(filepath)
            current_mtimes[doc] = mtime
            if doc not in KNOWLEDGE_MTIME or mtime > KNOWLEDGE_MTIME[doc]:
                needs_reload = True
        else:
            logger.warning(f"Platform knowledge doc not found: {doc}")

    if not needs_reload and KNOWLEDGE_CACHE is not None:
        return KNOWLEDGE_CACHE

    # Reload
    combined_knowledge = []
    for doc in SELECTED_DOCS:
        filepath = os.path.join(DOCS_DIR, doc)
        if os.path.exists(filepath):
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    content = f.read()
                    combined_knowledge.append(f"--- Document: {doc} ---\n{content}\n")
            except Exception as e:
                logger.error(f"Error reading platform knowledge doc {doc}: {e}")

    KNOWLEDGE_CACHE = "\n".join(combined_knowledge)
    KNOWLEDGE_MTIME = current_mtimes
    return KNOWLEDGE_CACHE
