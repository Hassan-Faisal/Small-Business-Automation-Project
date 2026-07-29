from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

__all__ = ["ProductCreate", "ProductUpdate", "ProductResponse"]


class ProductBase(BaseModel):
    name: str = Field(min_length=1, max_length=150)
    description: str | None = Field(default=None, max_length=10_000)
    price: Decimal = Field(ge=Decimal("0.00"))
    is_available: bool = True


class ProductCreate(ProductBase):
    pass


class ProductUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=150)
    description: str | None = Field(default=None, max_length=10_000)
    price: Decimal | None = Field(default=None, ge=Decimal("0.00"))
    is_available: bool | None = None


class ProductResponse(ProductBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
