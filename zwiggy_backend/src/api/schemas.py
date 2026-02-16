from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import List, Optional

from pydantic import BaseModel, EmailStr, Field

from src.api.models import OrderStatus, UserRole


class APIMessage(BaseModel):
    message: str = Field(..., description="Human-readable message.")


# --------------------
# Auth
# --------------------
class SignUpRequest(BaseModel):
    email: EmailStr = Field(..., description="Unique email address.")
    password: str = Field(..., min_length=8, max_length=128, description="Password (min 8 chars).")
    role: UserRole = Field(..., description="User role: customer or owner.")
    full_name: Optional[str] = Field(None, max_length=200, description="Optional full name.")


class LoginRequest(BaseModel):
    email: EmailStr = Field(..., description="User email.")
    password: str = Field(..., min_length=1, max_length=128, description="User password.")


class TokenResponse(BaseModel):
    access_token: str = Field(..., description="JWT access token.")
    token_type: str = Field("bearer", description="Token type.")


class UserResponse(BaseModel):
    id: int
    email: EmailStr
    role: UserRole
    full_name: Optional[str] = None
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


# --------------------
# Restaurants + Menu
# --------------------
class RestaurantCreateRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=200, description="Restaurant name.")
    description: Optional[str] = Field(None, max_length=2000, description="Restaurant description.")
    address: Optional[str] = Field(None, max_length=500, description="Restaurant address.")
    is_open: bool = Field(True, description="Whether restaurant is currently open.")


class RestaurantUpdateRequest(BaseModel):
    name: Optional[str] = Field(None, min_length=2, max_length=200)
    description: Optional[str] = Field(None, max_length=2000)
    address: Optional[str] = Field(None, max_length=500)
    is_open: Optional[bool] = None


class RestaurantResponse(BaseModel):
    id: int
    owner_id: int
    name: str
    description: Optional[str] = None
    address: Optional[str] = None
    is_open: bool
    created_at: datetime

    class Config:
        from_attributes = True


class MenuItemCreateRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=200, description="Dish name.")
    description: Optional[str] = Field(None, max_length=2000, description="Dish description.")
    price: Decimal = Field(..., gt=0, description="Dish price.")
    is_available: bool = Field(True, description="Availability flag.")


class MenuItemUpdateRequest(BaseModel):
    name: Optional[str] = Field(None, min_length=2, max_length=200)
    description: Optional[str] = Field(None, max_length=2000)
    price: Optional[Decimal] = Field(None, gt=0)
    is_available: Optional[bool] = None


class MenuItemResponse(BaseModel):
    id: int
    restaurant_id: int
    name: str
    description: Optional[str] = None
    price: Decimal
    is_available: bool

    class Config:
        from_attributes = True


# --------------------
# Cart
# --------------------
class CartAddItemRequest(BaseModel):
    menu_item_id: int = Field(..., ge=1, description="Menu item id.")
    quantity: int = Field(1, ge=1, le=50, description="Quantity to add (1-50).")


class CartUpdateItemRequest(BaseModel):
    quantity: int = Field(..., ge=1, le=50, description="New quantity (1-50).")


class CartItemResponse(BaseModel):
    id: int
    user_id: int
    menu_item_id: int
    quantity: int
    created_at: datetime

    class Config:
        from_attributes = True


class CartSummaryItem(BaseModel):
    menu_item_id: int
    restaurant_id: int
    name: str
    price: Decimal
    quantity: int
    line_total: Decimal


class CartSummaryResponse(BaseModel):
    items: List[CartSummaryItem]
    subtotal: Decimal
    restaurant_id: Optional[int] = Field(None, description="If cart is constrained to a single restaurant, its id.")


# --------------------
# Orders
# --------------------
class PlaceOrderRequest(BaseModel):
    delivery_address: str = Field(..., min_length=5, max_length=500, description="Delivery address.")


class OrderItemResponse(BaseModel):
    id: int
    menu_item_id: int
    name_snapshot: str
    price_snapshot: Decimal
    quantity: int

    class Config:
        from_attributes = True


class OrderStatusHistoryResponse(BaseModel):
    id: int
    status: OrderStatus
    note: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class OrderResponse(BaseModel):
    id: int
    user_id: int
    restaurant_id: int
    delivery_address: str
    total_amount: Decimal
    status: OrderStatus
    created_at: datetime
    items: List[OrderItemResponse]
    status_history: List[OrderStatusHistoryResponse]

    class Config:
        from_attributes = True


class OwnerUpdateOrderStatusRequest(BaseModel):
    status: OrderStatus = Field(..., description="New order status.")
    note: Optional[str] = Field(None, max_length=500, description="Optional status note.")
