from __future__ import annotations

import re
from datetime import date, timedelta
from typing import Iterable

CANONICAL_INTENTS = ["greeting", "today_menu", "weekly_menu", "breakfast_menu", "lunch_menu", "dinner_menu", "add_item", "remove_item", "change_quantity", "clear_cart", "view_cart", "search_menu", "provide_address", "confirm_order", "track_order", "cancel_order", "modify_order", "subscription_plans", "create_subscription", "subscription_status", "pause_subscription", "resume_subscription", "cancel_subscription", "skip_meal", "bulk_order", "delivery_area", "delivery_timing", "payment_methods", "faq", "human_handoff", "fallback"]
WEEKDAY_ALIASES = {"monday": {"monday", "mon", "peer", "pir", "somwar"}, "tuesday": {"tuesday", "tue", "mangal", "mangalwar"}, "wednesday": {"wednesday", "wed", "budh", "budhwar"}, "thursday": {"thursday", "thu", "jumeraat", "jumerat"}, "friday": {"friday", "fri", "jumma", "juma"}, "saturday": {"saturday", "sat", "hafta"}, "sunday": {"sunday", "sun", "itwar", "aitwar"}}
RELATIVE_DAY_ALIASES = {"today": {"today", "aaj", "aj"}, "tomorrow": {"tomorrow", "kal"}, "day_after_tomorrow": {"day after tomorrow", "parson"}}
MEAL_ALIASES = {"breakfast": {"breakfast", "nashta", "nashtay", "subah ka khana"}, "lunch": {"lunch", "dopahar", "dopehar"}, "dinner": {"dinner", "raat ka khana", "rat ka khana", "shaam ka khana"}}
NUMBER_WORDS = {"zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10, "ek": 1, "aik": 1, "do": 2, "teen": 3, "char": 4, "chaar": 4, "paanch": 5, "che": 6, "saat": 7, "aath": 8, "nau": 9, "das": 10}
POSITION_WORDS = {"first": 1, "second": 2, "third": 3, "last": -1}


def normalize_text(text: str) -> str:
    normalized = " ".join(text.strip().lower().split())
    replacements = {"mujhay": "mujhe", "mjhe": "mujhe", "mujhko": "mujhe", "chaheye": "chahiye", "chahye": "chahiye", "krdo": "kar do", "karo": "kar do", "kia": "kya", "mai": "mein"}
    for source, target in replacements.items():
        normalized = re.sub(rf"(?<!\w){re.escape(source)}(?!\w)", target, normalized)
    return normalized


def _phrase_in_text(text: str, phrase: str) -> bool:
    return re.search(rf"(?<!\w){re.escape(phrase)}(?!\w)", text) is not None


def contains_any(text: str, patterns: Iterable[str]) -> bool:
    return any(_phrase_in_text(text, pattern) for pattern in patterns)


def extract_explicit_weekday(text: str) -> str | None:
    normalized = normalize_text(text)
    for canonical_day, aliases in WEEKDAY_ALIASES.items():
        if contains_any(normalized, aliases):
            return canonical_day.title()
    return None


def extract_relative_day(text: str, *, base_date: date | None = None) -> str | None:
    normalized = normalize_text(text)
    base = base_date or date.today()
    if contains_any(normalized, RELATIVE_DAY_ALIASES["day_after_tomorrow"]):
        return (base + timedelta(days=2)).strftime("%A")
    if contains_any(normalized, RELATIVE_DAY_ALIASES["tomorrow"]):
        return (base + timedelta(days=1)).strftime("%A")
    if contains_any(normalized, RELATIVE_DAY_ALIASES["today"]):
        return base.strftime("%A")
    return None


def extract_day(text: str, *, base_date: date | None = None) -> str | None:
    return extract_explicit_weekday(text) or extract_relative_day(text, base_date=base_date)


def extract_meal_type(text: str) -> str | None:
    normalized = normalize_text(text)
    for meal_type, aliases in MEAL_ALIASES.items():
        if contains_any(normalized, aliases):
            return meal_type
    return None


DISCOVERY_FILLER_WORDS = {
    "a", "an", "and", "are", "can", "do", "for", "find", "get", "give", "have", "i", "in", "items", "item", "me", "meals", "meal", "my", "options", "option", "please", "show", "some", "something", "anything", "the", "to", "what", "which", "with", "without", "want", "you", "dishes", "dish", "related",
}
CONSTRAINT_BOUNDARY_WORDS = {"for", "on", "from", "please", "today", "tomorrow", "tonight"}
DISCOVERY_MARKERS = {"show", "find", "which", "options", "what do you have", "do you have", "what options", "what meals", "is available", "available"}
PURCHASE_MARKERS = {"order", "add", "i will have", "ill have", "give me", "get me", "can i get", "cart mein add", "cart me add"}


def _constraint_terms(segment: str) -> list[str]:
    terms: list[str] = []
    for token in re.findall(r"[a-z][a-z-]*", normalize_text(segment)):
        if token in DISCOVERY_FILLER_WORDS or token in CONSTRAINT_BOUNDARY_WORDS or token in {"no", "not", "excluding", "exclude"}:
            continue
        if token not in terms:
            terms.append(token)
    return terms


def extract_search_constraints(text: str) -> dict[str, list[str]]:
    """Extract reusable text constraints without asserting catalog attributes."""
    normalized = normalize_text(text)
    include_terms: list[str] = []
    exclude_terms: list[str] = []

    negative = re.search(r"\b(?:without|no|excluding|exclude|not)\s+(.+?)(?=\s+(?:for|on|from|please|today|tomorrow|tonight)\b|$)", normalized)
    if negative:
        exclude_terms.extend(_constraint_terms(negative.group(1)))

    positive = re.search(r"\bwith\s+(?!no\b|out\b)(.+?)(?=\s+(?:for|on|from|please|today|tomorrow|tonight)\b|$)", normalized)
    if positive:
        include_terms.extend(_constraint_terms(positive.group(1)))

    broad = re.search(r"\b(?:something|anything)\s+(.+?)(?=\s+(?:related|for|on|from|please)\b|$)", normalized)
    if broad:
        include_terms.extend(_constraint_terms(broad.group(1)))

    exclude_terms = list(dict.fromkeys(exclude_terms))
    return {
        "include_terms": [term for term in dict.fromkeys(include_terms) if term not in exclude_terms],
        "exclude_terms": list(dict.fromkeys(exclude_terms)),
    }


def extract_discovery_query(text: str) -> str:
    """Return catalog-search terms while leaving exact product resolution to services."""
    normalized = normalize_text(text)
    constraints = extract_search_constraints(normalized)
    excluded = set(constraints["include_terms"] + constraints["exclude_terms"])
    meal_type = extract_meal_type(normalized)
    day = extract_day(normalized)
    context_terms = {term for term in (meal_type, day.lower() if day else None) if term}

    tokens = [
        token for token in re.findall(r"[a-z][a-z-]*", normalized)
        if token not in DISCOVERY_FILLER_WORDS
        and token not in CONSTRAINT_BOUNDARY_WORDS
        and token not in excluded
        and token not in context_terms
        and token not in {"without", "no", "excluding", "exclude", "not"}
    ]
    return " ".join(dict.fromkeys(tokens))


def is_discovery_request(text: str) -> bool:
    normalized = normalize_text(text)
    if "cart" in normalized or "subscription" in normalized or "plan" in normalized:
        return False
    """Identify catalog discovery without deciding whether a product matches."""
    normalized = normalize_text(text)
    constraints = extract_search_constraints(normalized)
    has_marker = contains_any(normalized, DISCOVERY_MARKERS)
    is_broad = contains_any(normalized, {"something", "anything"})
    has_purchase_marker = contains_any(normalized, PURCHASE_MARKERS)
    # Broad preference requests are discovery unless the customer explicitly
    # asks to order/add a concrete item.
    broad_constraint = re.search(r"\b(?:with|without|no|excluding|exclude|not)\b", normalized) is not None
    return has_marker or (
        is_broad
        and not has_purchase_marker
        and broad_constraint
    ) or (
        is_broad
        and not has_purchase_marker
        and extract_meal_type(normalized) is not None
        and not normalized.startswith("i want")
    )

CURRENCY_MARKER_PATTERN = r"(?:rs\.?|pkr|rupees?|rup(?:ee|ay|aye)s?|\u20a8)"
MONEY_WORD_PATTERN = r"(?:zero|one|two|three|four|five|six|seven|eight|nine|ten|ek|aik|do|teen|char|chaar|paanch|che|saat|aath|nau|das)(?:\s+hundred)?"

def _monetary_spans(text: str) -> list[tuple[int, int]]:
    amount_pattern = rf"(?:\d[\d,]*(?:\.\d+)?|{MONEY_WORD_PATTERN})"
    patterns = (rf"{CURRENCY_MARKER_PATTERN}\s*{amount_pattern}", rf"{amount_pattern}\s*{CURRENCY_MARKER_PATTERN}")
    return [(match.start(), match.end()) for pattern in patterns for match in re.finditer(pattern, text)]

def extract_quantity(text: str) -> int | None:
    normalized = normalize_text(text)
    monetary_spans = _monetary_spans(normalized)
    for match in re.finditer(r"(?<!\d)-?\d+(?!\d)", normalized):
        if any(start <= match.start() and match.end() <= end for start, end in monetary_spans):
            continue
        return int(match.group(0))
    for word, value in NUMBER_WORDS.items():
        for word_match in re.finditer(rf"(?<!\w){re.escape(word)}(?!\w)", normalized):
            if any(start <= word_match.start() and word_match.end() <= end for start, end in monetary_spans):
                continue
            if word == "do" and re.search(r"(?:kar|karo|kr)\s*$", normalized[:word_match.start()]):
                continue
            return value
    return None


def extract_position_reference(text: str) -> int | None:
    normalized = normalize_text(text)
    for word, value in POSITION_WORDS.items():
        if _phrase_in_text(normalized, word):
            return value
    match = re.search(r"\bitem\s+(\d+)\b", normalized)
    return int(match.group(1)) if match else None


def extract_order_reference(text: str) -> str | None:
    match = re.search(r"\b(?:ORD|TF)-[A-Z0-9]+(?:-[A-Z0-9]+)*\b", text.upper())
    return match.group(0) if match else None


def infer_intent(text: str) -> str:
    normalized = normalize_text(text)
    if not normalized:
        return "fallback"
    if contains_any(normalized, {"talk to a person", "talk to human", "customer support", "connect me with an agent", "human please", "human", "agent", "representative"}):
        return "human_handoff"
    if contains_any(normalized, {"subscription status", "show my subscription", "show my plan", "what is my plan", "is my subscription active", "active subscription"}):
        return "subscription_status"
    if contains_any(normalized, {"cancel subscription", "cancel my subscription"}):
        return "cancel_subscription"
    if contains_any(normalized, {"pause my subscription", "pause subscription"}):
        return "pause_subscription"
    if contains_any(normalized, {"resume my subscription", "resume subscription"}):
        return "resume_subscription"
    if contains_any(normalized, {"skip tomorrow", "skip friday", "skip meal", "skip lunch", "skip dinner", "skip breakfast"}):
        return "skip_meal"
    if contains_any(normalized, {"bulk order", "large order", "boxes"}):
        return "bulk_order"
    if contains_any(normalized, {"cancel my order", "cancel order", "i do not want this order", "mujhay order cancel krna hai", "mujhe order cancel kar do", "mujhe order cancel krna hai", "mera order cancel kar do", "mera order cancel kro", "order cancel kar do"}):
        return "cancel_order"
    if _phrase_in_text(normalized, "order") and contains_any(normalized, {"change", "modify", "edit", "update"}):
        return "modify_order"
    if contains_any(normalized, {"track my order", "track order", "order status", "where is my order", "status of order", "mera order kahan hai", "mera order track kro", "order ka status batao"}) or (extract_order_reference(text) is not None and "cancel" not in normalized):
        return "track_order"
    if contains_any(normalized, {"my address is", "deliver to", "address:", "send to", "i live at", "location is", "delivery address", "ye address hai", "address hai", "address save kro"}):
        return "provide_address"
    if contains_any(normalized, {"confirm order", "order confirm", "confirm my order", "confirm the order", "place order", "place my order", "checkout", "proceed", "proceed with order", "mera order confirm kar do", "mera order confirm karo", "mera order confirm kro", "order confirm kar do", "order confirm karo", "order confirm kro", "mera order place kar do", "mera order place karo"}) or normalized in {"confirm", "yes"}:
        return "confirm_order"
    if contains_any(normalized, {"clear cart", "clear my cart", "empty cart", "empty my cart", "delete my cart", "cart clear", "cart khali"}):
        return "clear_cart"
    if contains_any(normalized, {"remove", "delete", "take out"}) or (re.search(r"\btake\b.*\bout\b", normalized) is not None):
        return "remove_item"
    if contains_any(normalized, {"today's menu", "today menu", "show today's menu", "what is available today", "what can i order today", "available today", "share menu", "menu please", "aaj menu mein kya hai", "aaj menu mai kia hai", "aaj khanay mein kya hai", "aaj kya khana hai", "aaj ka menu", "what is in menu"}):
        return "today_menu"
    if is_discovery_request(normalized):
        return "search_menu"
    if contains_any(normalized, {"add", "i want", "want to order", "get me", "give me", "can i get", "i need", "i'll have"}) and not contains_any(normalized, {"cancel", "confirm", "subscription", "plan"}):
        return "add_item"
    if _phrase_in_text(normalized, "order") and normalized not in {"what have i ordered", "where is my order"} and not contains_any(normalized, {"track", "status", "cancel", "confirm"}):
        return "add_item"
    if contains_any(normalized, {"view cart", "show my cart", "what is in my cart", "what's in my cart", "what is in cart", "what have i ordered", "show cart", "my cart", "cart please", "cart dikhao", "mera cart dikhao", "meri cart dikhao", "cart mein kya hai", "cart me kya hai", "mere cart mein kya hai", "mera cart", "meri cart mai kia hai", "cart check kro"}) or normalized in {"cart", "my cart", "cart please"}:
        return "view_cart"
    if contains_any(normalized, {"clear cart", "clear my cart", "empty cart", "empty my cart", "delete my cart", "cart clear", "cart khali"}):
        return "clear_cart"
    if contains_any(normalized, {"today's menu", "today menu", "show today's menu", "what is available today", "what can i order today", "available today", "share menu", "menu please", "aaj menu mein kya hai", "aaj menu mai kia hai", "aaj khanay mein kya hai", "aaj kya khana hai", "aaj ka menu", "what is in menu"}):
        return "today_menu"
    if contains_any(normalized, {"weekly menu", "show weekly menu", "this week's meals", "weekly plan", "what is available this week", "show me the menu", "is haftay ka menu"}):
        return "weekly_menu"
    if contains_any(normalized, {"today's menu", "today menu", "show today's menu", "what is available today", "what can i order today", "available today", "share menu", "menu please", "aaj menu mein kya hai", "aaj menu mai kia hai", "aaj khanay mein kya hai", "aaj kya khana hai", "aaj ka menu", "what is in menu"}):
        return "today_menu"
    if is_discovery_request(normalized):
        return "search_menu"
    if extract_quantity(normalized) is not None and contains_any(normalized, {"only", "actually", "just", "meant", "instead", "asked for"}):
        return "change_quantity"
    if extract_quantity(normalized) is not None and contains_any(normalized, {"make", "set", "change"}):
        return "change_quantity"
    if contains_any(normalized, {"make that", "change quantity", "increase", "decrease", "reduce", "add one more", "same one again"}):
        return "change_quantity"
    if contains_any(normalized, {"add", "order", "i want", "need", "get me", "send me", "chahiye", "cart mein add", "order kar do", "sath kar do", "saath kar do"}) and not contains_any(normalized, {"cancel", "confirm", "subscription", "plan"}):
        return "add_item"
    if extract_day(text) is not None and _phrase_in_text(normalized, "menu"):
        return "today_menu"
    meal_type = extract_meal_type(normalized)
    if meal_type is not None and (_phrase_in_text(normalized, "menu") or normalized in {"breakfast", "lunch", "dinner", "nashta"} or contains_any(normalized, {"kya hai", "kia hai"}) or extract_day(text) is not None):
        return f"{meal_type}_menu"
    if normalized in {"show breakfast", "breakfast menu"}:
        return "breakfast_menu"
    if normalized in {"show lunch", "lunch menu", "any lunch today", "what is for lunch"}:
        return "lunch_menu"
    if normalized in {"show dinner", "dinner menu", "what is for dinner"}:
        return "dinner_menu"
    if contains_any(normalized, {"subscription plans", "show subscription plans", "show subscriptions", "subscription options", "subscription options dikhao", "show plans", "what subscriptions do you offer", "tiffin plans"}) or normalized == "subscribe":
        return "subscription_plans"
    if contains_any(normalized, {"monthly plan", "weekly plan"}):
        return "subscription_plans"
    if (contains_any(normalized, {"weekly", "monthly"}) and _phrase_in_text(normalized, "plan")) or contains_any(normalized, {"start a", "select", "subscribe me"}) or bool(re.search(r"\bplan\s+\d+\b", normalized)):
        return "create_subscription"
    if contains_any(normalized, {"where do you deliver", "delivery area", "do you deliver to", "deliver to islamabad"}):
        return "delivery_area"
    if contains_any(normalized, {"delivery timings", "delivery timing", "what time do you deliver", "delivery window"}):
        return "delivery_timing"
    if contains_any(normalized, {"payment methods", "how can i pay", "cash on delivery", "bank transfer", "online transfer"}):
        return "payment_methods"
    if contains_any(normalized, {"refund policy", "refund", "policy", "policies", "allergies", "allergen", "cancel a meal", "food safety", "hours", "open", "operating hours"}):
        return "faq"
    if contains_any(normalized, {"hello", "hi", "hey", "start", "help", "salam", "salaam", "assalam o alaikum", "assalamualaikum", "assalamu alaikum"}):
        return "greeting"
    if _phrase_in_text(normalized, "menu"):
        return "weekly_menu"
    if contains_any(normalized, {"add", "order", "i want", "need", "get me", "send me", "add item number", "cart mai add kro", "order krna hai", "order karna hai", "chahiye"}):
        return "add_item"
    return "fallback"







