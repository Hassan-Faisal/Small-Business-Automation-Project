from __future__ import annotations

import re
from datetime import date, timedelta
from typing import Iterable

INTENT_PRECEDENCE = [
    "track_order",
    "cancel_order",
    "skip_meal",
    "pause_subscription",
    "resume_subscription",
    "subscription_status",
    "create_subscription",
    "confirm_order",
    "update_order",
    "remove_item",
    "add_item",
    "view_cart",
    "menu",
    "delivery_area",
    "delivery_timing",
    "payment_methods",
    "faq",
    "human_escalation",
    "greeting",
    "fallback",
]

WEEKDAY_ALIASES = {
    "monday": {"monday", "mon", "peer", "pir", "somwar"},
    "tuesday": {"tuesday", "tue", "mangal", "mangalwar"},
    "wednesday": {"wednesday", "wed", "budh", "budhwar"},
    "thursday": {"thursday", "thu", "jumeraat", "jumerat"},
    "friday": {"friday", "fri", "jumma", "juma"},
    "saturday": {"saturday", "sat", "hafta"},
    "sunday": {"sunday", "sun", "itwar", "aitwar"},
}

RELATIVE_DAY_ALIASES = {
    "today": {"today", "aaj", "aj"},
    "tomorrow": {"tomorrow", "kal"},
    "day_after_tomorrow": {"day after tomorrow", "parson"},
}

MEAL_ALIASES = {
    "breakfast": {"breakfast", "nashta", "nashtay", "nashtay", "nashtay mein", "nashtay me"},
    "lunch": {"lunch", "dopahar", "dopehar"},
    "dinner": {"dinner", "raat ka khana", "rat ka khana", "raat ka khanay"},
}

ORDER_VERB_PATTERNS = (
    " order ",
    "add",
    "buy",
    "chahiye",
    "mangwa do",
    "mangwa dena",
    "bhej do",
    "laga do",
    "kar do",
    "kr do",
    "rakh do",
)
MENU_VERB_PATTERNS = (
    "show",
    "dikhao",
    "batao",
    "menu",
    "options",
    "kya hai",
    "kia hai",
)

HUMAN_ESCALATION_PATTERNS = (
    "refund",
    "wrong delivery",
    "missing delivery",
    "complaint",
    "damaged food",
    "custom pricing",
    "talk to owner",
    "talk to human",
    "agent",
    "human",
    "owner",
    "representative",
)

NUMBER_WORDS = {
    "zero": 0,
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
}
POSITION_WORDS = {"first": 1, "second": 2, "third": 3, "last": -1}


def normalize_text(text: str) -> str:
    return " ".join(text.strip().lower().split())


def contains_any(text: str, patterns: Iterable[str]) -> bool:
    return any(pattern in text for pattern in patterns)


def extract_explicit_weekday(text: str) -> str | None:
    normalized = normalize_text(text)
    for canonical_day, aliases in WEEKDAY_ALIASES.items():
        for alias in aliases:
            if re.search(rf"\b{re.escape(alias)}\b", normalized):
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
    explicit = extract_explicit_weekday(text)
    if explicit is not None:
        return explicit
    return extract_relative_day(text, base_date=base_date)


def extract_meal_type(text: str) -> str | None:
    normalized = normalize_text(text)
    for meal_type, aliases in MEAL_ALIASES.items():
        if contains_any(normalized, aliases):
            return meal_type
    return None


def extract_quantity(text: str) -> int | None:
    normalized = normalize_text(text)
    match = re.search(r"(?<!\d)(-?\d+)(?!\d)", normalized)
    if match is not None:
        return int(match.group(1))
    for word, value in NUMBER_WORDS.items():
        if re.search(rf"\b{word}\b", normalized):
            return value
    if contains_any(normalized, {"only one", "just one", "ek hi", "sirf ek"}):
        return 1
    return None


def extract_position_reference(text: str) -> int | None:
    normalized = normalize_text(text)
    for word, value in POSITION_WORDS.items():
        if re.search(rf"\b{word}\b", normalized):
            return value
    return None


def extract_order_reference(text: str) -> str | None:
    normalized = text.upper()
    match = re.search(r"\bORD-[A-Z0-9]+(?:-[A-Z0-9]+)*\b", normalized)
    return match.group(0) if match else None


def infer_intent(text: str) -> str:
    normalized = normalize_text(text)
    if not normalized:
        return "fallback"
    if contains_any(normalized, {"track", "status", "where is my order"}):
        return "track_order"
    if contains_any(normalized, {"cancel", "cancel order", "cancel my order"}):
        return "cancel_order"
    if contains_any(normalized, {"skip", "miss my meal", "meal skip"}):
        return "skip_meal"
    if contains_any(normalized, {"pause subscription", "pause my subscription", "pause"}):
        return "pause_subscription"
    if contains_any(normalized, {"resume subscription", "resume my subscription", "restart subscription", "resume"}):
        return "resume_subscription"
    if contains_any(normalized, {"subscription status", "my meal today", "my subscription", "active subscription"}):
        return "subscription_status"
    if contains_any(normalized, {"weekly plans", "monthly plans", "subscription plans", "packages", "plans"}):
        return "subscription_plans"
    if contains_any(normalized, {"lunch only", "lunch + dinner", "full day", "weekly full day plan", "weekly full-day plan", "monthly lunch", "weekly subscription", "monthly subscription"}):
        return "create_subscription"
    if contains_any(normalized, {"confirm", "place", "submit"}):
        return "confirm_order"
    if contains_any(normalized, {"address", "location", "deliver to", "live at", "my address", "send to", "located at"}):
        return "provide_address"
    if contains_any(normalized, {"change it to", "actually make it", "i only need", "replace", "update quantity", "make it", "only one"}):
        return "update_quantity"
    if contains_any(normalized, {"remove", "delete", "take out"}):
        return "remove_meal"
    if contains_any(normalized, {"add", "order", "buy", "get me", "i want", "need", "mangwa", "bhej", "laga", "rakh", "kar do", "kr do", "chahiye"}):
        return "add_meal"
    if contains_any(normalized, {"view cart", "show cart", "cart", "basket"}):
        return "view_cart"
    if contains_any(normalized, {"today's menu", "today menu", "aaj ka menu", "aaj menu", "what is today's menu", "what's today's menu", "aaj ka lunch", "aaj ka breakfast", "aaj ka dinner"}):
        return "today_menu"
    if contains_any(normalized, {"breakfast", "nashta", "nashtay", "subah ka khana"}):
        return "breakfast_menu"
    if contains_any(normalized, {"lunch", "dopeher", "dopahar", "lunch menu"}):
        return "lunch_menu"
    if contains_any(normalized, {"dinner", "raat ka khana", "shaam ka khana", "dinner menu"}):
        return "dinner_menu"
    if contains_any(normalized, {"menu", "available meals", "what's available", "what is available", "show", "dikhao", "batao", "options", "kya hai", "kia hai"}):
        return "weekly_menu"
    if contains_any(normalized, {"delivery area", "deliver to", "where do you deliver", "gulberg", "dha lahore", "johar town", "model town", "hostel", "office building"}):
        return "delivery_area"
    if contains_any(normalized, {"delivery timing", "timing", "what time", "delivery window"}):
        return "delivery_timing"
    if contains_any(normalized, {"payment methods", "cash on delivery", "bank transfer", "online transfer", "cod"}):
        return "payment_methods"
    if contains_any(normalized, HUMAN_ESCALATION_PATTERNS):
        return "human_handoff"
    if contains_any(normalized, {"faq", "policy", "hours", "open", "accept", "delivery", "cash", "card", "timing", "timings"}):
        return "faq"
    if contains_any(normalized, {"hi", "hello", "hey", "good morning", "good afternoon", "good evening", "assalam", "salaam", "salam"}):
        return "greeting"
    return "fallback"
