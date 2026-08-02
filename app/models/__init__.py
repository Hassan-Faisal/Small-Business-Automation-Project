"""ORM model registry for SQLAlchemy metadata import side effects."""

from app.models.admin_user import AdminUser
from app.models.conversation_state import ConversationStateRecord
from app.models.customer_subscription import CustomerSubscription
from app.models.meal_offering import MealOffering
from app.models.meal_skip import MealSkip
from app.models.order import Order
from app.models.order_item import OrderItem
from app.models.product import Product
from app.models.subscription_plan import SubscriptionPlan

__all__ = [
    "AdminUser",
    "Product",
    "Order",
    "OrderItem",
    "ConversationStateRecord",
    "MealOffering",
    "SubscriptionPlan",
    "CustomerSubscription",
    "MealSkip",
]
