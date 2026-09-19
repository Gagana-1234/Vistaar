"""
services/cognee_service.py — Vistaar persistent business memory layer.

Wraps the Cognee SDK to give Vistaar long-term merchant memory.

PURPOSE:
  Cognee is NOT the analytics engine. It stores and retrieves merchant-specific
  context that enriches AI reasoning — things the backend can't calculate from
  numbers alone (merchant explanations, historical events, preferences).

MEMORY TYPES:
  MERCHANT_CONTEXT        — e.g. "Monday sales are low because market is closed"
  HISTORICAL_ALERT        — e.g. "Oil demand spiked in Sep last year → stock-out"
  PREVIOUS_RECOMMENDATION — e.g. "Recommended restocking cooking oil"
  MERCHANT_PREFERENCE     — e.g. "Merchant wants alerts only for high-priority items"
  BUSINESS_EVENT          — e.g. "Shop closed for local holiday"

GRACEFUL FALLBACK:
  If Cognee is unavailable (not installed, wrong config, API error), every
  function returns a safe empty default and logs a warning. The dashboard never
  crashes because of a Cognee failure.

ENVIRONMENT VARIABLES REQUIRED:
  COGNEE_LLM_PROVIDER        — LLM provider for Cognee (default: openai)
  COGNEE_LLM_API_KEY         — API key for Cognee's LLM
  COGNEE_LLM_MODEL           — Model name (default: gpt-4o-mini)
  COGNEE_EMBEDDING_PROVIDER  — Embedding provider (default: openai)
  COGNEE_EMBEDDING_API_KEY   — Embedding API key

  All are optional — if missing, Cognee is disabled and system falls back gracefully.
"""

import os
import logging
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

# Cognee reads these settings while it is imported, so configure its
# provider environment before loading the SDK.
_llm_api_key = os.getenv("COGNEE_LLM_API_KEY", "")
if _llm_api_key:
    os.environ["LLM_PROVIDER"] = os.getenv("COGNEE_LLM_PROVIDER", "groq")
    os.environ["LLM_API_KEY"]  = _llm_api_key
    os.environ["LLM_MODEL"]    = os.getenv("COGNEE_LLM_MODEL", "groq/llama-3.3-70b-versatile")
    os.environ["EMBEDDING_PROVIDER"] = os.getenv("COGNEE_EMBEDDING_PROVIDER", "groq")
    os.environ["EMBEDDING_API_KEY"]  = os.getenv("COGNEE_EMBEDDING_API_KEY", _llm_api_key)

# ── Set Cognee DB path to project data dir BEFORE importing the SDK.
# This avoids the LanceDB file-lock error that occurs when:
#   a) the DB is inside venv/ (permission issues on some Windows setups)
#   b) uvicorn --reload spawns overlapping processes that both open the same DB.
# Keeping the DB in backend/data/cognee_db/ ensures a stable single location.
_COGNEE_DB_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "cognee_db")
os.makedirs(_COGNEE_DB_DIR, exist_ok=True)
os.environ.setdefault("DATA_ROOT_DIRECTORY", _COGNEE_DB_DIR)

# ── Try to import Cognee. If not installed, disable gracefully.
_COGNEE_AVAILABLE = False
cognee = None

try:
    import cognee as _cognee_module
    cognee = _cognee_module
    _COGNEE_AVAILABLE = True
    logger.info("✅ Cognee SDK loaded successfully.")
except ImportError:
    logger.warning(
        "⚠️  Cognee SDK not installed. Memory features will be disabled. "
        "Run: pip install cognee"
    )

# ── Cognee dataset name (logical namespace for this merchant's memories)
COGNEE_DATASET = "vistaar_merchant"

# ── Initialisation flag (avoid re-running setup on every call)
_cognee_initialized = False


# ═══════════════════════════════════════════════════════════════════
# INITIALISATION
# ═══════════════════════════════════════════════════════════════════

def initialize_cognee() -> bool:
    """
    Configure Cognee using environment variables.
    Returns True if successfully initialized, False otherwise.
    
    Cognee uses its own LLM for graph construction. We configure it here
    from environment variables so no API keys are ever hardcoded.
    """
    global _cognee_initialized

    if not _COGNEE_AVAILABLE:
        return False

    if _cognee_initialized:
        return True

    try:
        llm_provider = os.getenv("COGNEE_LLM_PROVIDER", "google")
        llm_api_key  = os.getenv("COGNEE_LLM_API_KEY", "")
        llm_model    = os.getenv("COGNEE_LLM_MODEL", "gemini-3.6-flash")
        emb_provider = os.getenv("COGNEE_EMBEDDING_PROVIDER", "google")
        emb_api_key  = os.getenv("COGNEE_EMBEDDING_API_KEY", "")

        if not llm_api_key:
            logger.warning(
                "⚠️  COGNEE_LLM_API_KEY not set. "
                "Cognee memory features are disabled. "
                "Add COGNEE_LLM_API_KEY to backend/.env to enable them."
            )
            return False

        if llm_provider in ("google", "gemini") and not llm_model.startswith("gemini/"):
            llm_model = f"gemini/{llm_model}"

        # Set Cognee environment config via os.environ before calling SDK
        os.environ["LLM_PROVIDER"]        = llm_provider
        os.environ["LLM_API_KEY"]         = llm_api_key
        os.environ["LLM_MODEL"]           = llm_model
        os.environ["EMBEDDING_PROVIDER"]  = emb_provider
        os.environ["EMBEDDING_API_KEY"]   = emb_api_key

        _cognee_initialized = True
        logger.info(f"✅ Cognee configured: provider={llm_provider}, model={llm_model}")
        return True

    except Exception as e:
        logger.error(f"❌ Cognee initialization failed: {e}")
        return False


# ═══════════════════════════════════════════════════════════════════
# MEMORY STORAGE
# ═══════════════════════════════════════════════════════════════════

async def add_merchant_memory(
    text: str,
    memory_type: str = "MERCHANT_CONTEXT",
    merchant_id: str = "MERCHANT_001",
) -> dict:
    """
    Store a merchant memory in Cognee instantly.

    Uses cognee.add() only — no cognify() call.
    Cognee's built-in session memory means recall() works immediately
    after add(), without needing the slow LLM graph-build step.
    This keeps the endpoint fast (<1s response).
    """
    if not initialize_cognee():
        return {
            "success": False,
            "message": "Cognee not available. Memory not stored (system continues normally).",
        }

    try:
        tagged_text = f"[{memory_type}][{merchant_id}] {text}"

        # cognee.add() = fast ingestion only (no LLM, no graph build)
        # Session memory in cognee 1.5 makes this searchable immediately via recall()
        await cognee.add(tagged_text, dataset_name=COGNEE_DATASET)
        logger.info(f"💾 Memory saved [{memory_type}]: {text[:80]}")

        return {
            "success": True,
            "message": "Memory saved instantly.",
            "text": text,
        }

    except Exception as e:
        logger.error(f"❌ add_merchant_memory failed: {e}")
        return {"success": False, "message": f"Memory storage failed: {str(e)}"}


# ═══════════════════════════════════════════════════════════════════
# MEMORY RETRIEVAL
# ═══════════════════════════════════════════════════════════════════

async def search_merchant_memory(
    query: str,
    merchant_id: str = "MERCHANT_001",
    top_k: int = 5,
) -> list[dict]:
    """
    Search Cognee memory for context relevant to the given query.
    Uses cognee.recall() — cognee 1.5.4 API (no dataset_name kwarg).
    """
    if not initialize_cognee():
        return []

    try:
        # cognee 1.5.4: recall() takes query_text only — no dataset_name
        results = await cognee.recall(query_text=query)

        memories = []
        for r in (results or [])[:top_k]:
            text = getattr(r, "text", None) or (str(r) if r else "")
            if text:
                memories.append({"text": text, "score": getattr(r, "score", 1.0)})

        logger.info(f"🔍 Memory search '{query[:40]}' → {len(memories)} result(s)")
        return memories

    except Exception as e:
        logger.error(f"❌ search_merchant_memory failed: {e}")
        return []


async def get_relevant_context(
    query: str,
    merchant_id: str = "MERCHANT_001",
) -> str:
    """
    High-level helper: search Cognee and format results as a single
    context string ready to inject into an LLM prompt.

    Returns empty string "" if Cognee is unavailable or no results found.
    """
    memories = await search_merchant_memory(query, merchant_id=merchant_id)
    if not memories:
        return ""

    lines = []
    for i, m in enumerate(memories, 1):
        text = m["text"]
        # Strip the internal prefix tags before showing to LLM
        for tag in ["[MERCHANT_CONTEXT]", "[HISTORICAL_ALERT]", "[PREVIOUS_RECOMMENDATION]",
                    "[MERCHANT_PREFERENCE]", "[BUSINESS_EVENT]", f"[{merchant_id}]"]:
            text = text.replace(tag, "").strip()
        if text:
            lines.append(f"{i}. {text}")

    return "\n".join(lines) if lines else ""


# ═══════════════════════════════════════════════════════════════════
# DEMO SEED MEMORIES
# ═══════════════════════════════════════════════════════════════════

async def seed_demo_memories() -> dict:
    """
    Seed the Cognee knowledge graph with demo merchant memories.
    Call this once during setup or via /cognee/seed endpoint.

    These memories demonstrate Cognee's contribution to AI reasoning
    in the three demo scenarios.
    """
    if not initialize_cognee():
        return {
            "success": False,
            "message": "Cognee not available — seed skipped.",
            "seeded": 0,
        }

    demo_memories = [
        # For Scenario 1 (Normal) — this memory explains low Monday sales
        (
            "Monday sales are typically 15-20% lower than other weekdays "
            "because the nearby wholesale market is closed on Mondays. "
            "This is expected and not a cause for concern.",
            "MERCHANT_CONTEXT",
        ),
        # For Scenario 3 (Inventory Risk) — historical pattern
        (
            "Cooking oil demand spiked significantly in September last year "
            "and led to a stock-out that lasted 3 days. Customers had to be turned away. "
            "Restocking early is strongly recommended when oil demand increases.",
            "HISTORICAL_ALERT",
        ),
        # Merchant preference
        (
            "Merchant prefers to receive restock alerts only for HIGH priority situations. "
            "Low-priority nudges are less useful for this merchant.",
            "MERCHANT_PREFERENCE",
        ),
        # For Scenario 2 (Sales Anomaly) — business event context
        (
            "A new competing store opened 500 metres away in early August. "
            "This may be affecting beverage and snack sales as customers "
            "explore the new store's offerings.",
            "BUSINESS_EVENT",
        ),
        # Previous recommendation record
        (
            "Previously recommended: Restock cooking oil when stock falls below 30 units. "
            "Merchant acted on this recommendation and avoided a stock-out.",
            "PREVIOUS_RECOMMENDATION",
        ),
    ]

    seeded = 0
    errors = []
    for text, memory_type in demo_memories:
        result = await add_merchant_memory(text, memory_type=memory_type)
        if result.get("success"):
            seeded += 1
        else:
            errors.append(result.get("message", "unknown error"))

    return {
        "success": seeded > 0,
        "seeded": seeded,
        "total": len(demo_memories),
        "errors": errors,
        "message": f"Seeded {seeded}/{len(demo_memories)} demo memories into Cognee.",
    }


# ═══════════════════════════════════════════════════════════════════
# STATUS CHECK
# ═══════════════════════════════════════════════════════════════════

def get_cognee_status() -> dict:
    """Return current Cognee availability status (for /cognee/status endpoint)."""
    return {
        "available": _COGNEE_AVAILABLE,
        "initialized": _cognee_initialized,
        "dataset": COGNEE_DATASET,
        "message": (
            "Cognee is active and ready."
            if (_COGNEE_AVAILABLE and _cognee_initialized)
            else (
                "Cognee SDK not installed. Run: pip install cognee"
                if not _COGNEE_AVAILABLE
                else "Cognee installed but not yet initialized (missing COGNEE_LLM_API_KEY)."
            )
        ),
    }
