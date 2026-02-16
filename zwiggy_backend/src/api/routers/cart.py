from decimal import Decimal
from typing import List, Optional, Tuple

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from src.api.db import get_db
from src.api.deps import require_role
from src.api.models import CartItem, MenuItem, UserRole
from src.api.schemas import (
    APIMessage,
    CartAddItemRequest,
    CartItemResponse,
    CartSummaryItem,
    CartSummaryResponse,
    CartUpdateItemRequest,
)

router = APIRouter(prefix="/cart", tags=["Cart"])


def _get_cart_restaurant_id(db: Session, user_id: int) -> Optional[int]:
    stmt = (
        select(MenuItem.restaurant_id)
        .join(CartItem, CartItem.menu_item_id == MenuItem.id)
        .where(CartItem.user_id == user_id)
        .limit(1)
    )
    return db.scalar(stmt)


def _get_cart_summary(db: Session, user_id: int) -> Tuple[List[CartSummaryItem], Decimal, Optional[int]]:
    stmt = (
        select(CartItem, MenuItem)
        .join(MenuItem, MenuItem.id == CartItem.menu_item_id)
        .where(CartItem.user_id == user_id)
        .order_by(CartItem.created_at.asc())
    )

    rows = db.execute(stmt).all()
    items: List[CartSummaryItem] = []
    subtotal = Decimal("0.00")
    restaurant_id: Optional[int] = None

    for cart_item, menu_item in rows:
        price = Decimal(str(menu_item.price))
        line_total = price * cart_item.quantity
        subtotal += line_total
        restaurant_id = restaurant_id or menu_item.restaurant_id
        items.append(
            CartSummaryItem(
                menu_item_id=menu_item.id,
                restaurant_id=menu_item.restaurant_id,
                name=menu_item.name,
                price=price,
                quantity=cart_item.quantity,
                line_total=line_total,
            )
        )
    return items, subtotal, restaurant_id


@router.get(
    "",
    response_model=CartSummaryResponse,
    summary="Get current cart summary",
    description="Returns cart items with computed subtotal.",
)
def get_cart(
    db: Session = Depends(get_db),
    user=Depends(require_role(UserRole.CUSTOMER)),
) -> CartSummaryResponse:
    items, subtotal, restaurant_id = _get_cart_summary(db, user.id)
    return CartSummaryResponse(items=items, subtotal=subtotal, restaurant_id=restaurant_id)


@router.post(
    "/items",
    response_model=CartItemResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add an item to cart",
    description="Adds a menu item to cart (or increments quantity). Cart is constrained to a single restaurant.",
)
def add_to_cart(
    payload: CartAddItemRequest,
    db: Session = Depends(get_db),
    user=Depends(require_role(UserRole.CUSTOMER)),
) -> CartItemResponse:
    menu_item = db.get(MenuItem, payload.menu_item_id)
    if not menu_item or not menu_item.is_available:
        raise HTTPException(status_code=404, detail="Menu item not found or unavailable")

    existing_restaurant_id = _get_cart_restaurant_id(db, user.id)
    if existing_restaurant_id is not None and existing_restaurant_id != menu_item.restaurant_id:
        raise HTTPException(status_code=400, detail="Cart can contain items from only one restaurant at a time")

    cart_item = db.scalar(
        select(CartItem).where(CartItem.user_id == user.id, CartItem.menu_item_id == payload.menu_item_id)
    )
    if cart_item:
        cart_item.quantity = min(50, cart_item.quantity + payload.quantity)
    else:
        cart_item = CartItem(user_id=user.id, menu_item_id=payload.menu_item_id, quantity=payload.quantity)
        db.add(cart_item)

    db.commit()
    db.refresh(cart_item)
    return CartItemResponse.model_validate(cart_item)


@router.patch(
    "/items/{cart_item_id}",
    response_model=CartItemResponse,
    summary="Update cart item quantity",
    description="Updates the quantity of a specific cart item.",
)
def update_cart_item(
    cart_item_id: int,
    payload: CartUpdateItemRequest,
    db: Session = Depends(get_db),
    user=Depends(require_role(UserRole.CUSTOMER)),
) -> CartItemResponse:
    cart_item = db.get(CartItem, cart_item_id)
    if not cart_item or cart_item.user_id != user.id:
        raise HTTPException(status_code=404, detail="Cart item not found")
    cart_item.quantity = payload.quantity
    db.commit()
    db.refresh(cart_item)
    return CartItemResponse.model_validate(cart_item)


@router.delete(
    "/items/{cart_item_id}",
    response_model=APIMessage,
    summary="Remove item from cart",
    description="Deletes a cart item.",
)
def remove_cart_item(
    cart_item_id: int,
    db: Session = Depends(get_db),
    user=Depends(require_role(UserRole.CUSTOMER)),
) -> APIMessage:
    cart_item = db.get(CartItem, cart_item_id)
    if not cart_item or cart_item.user_id != user.id:
        raise HTTPException(status_code=404, detail="Cart item not found")
    db.delete(cart_item)
    db.commit()
    return APIMessage(message="Removed")


@router.delete(
    "",
    response_model=APIMessage,
    summary="Clear cart",
    description="Clears all cart items for the current user.",
)
def clear_cart(
    db: Session = Depends(get_db),
    user=Depends(require_role(UserRole.CUSTOMER)),
) -> APIMessage:
    db.execute(delete(CartItem).where(CartItem.user_id == user.id))
    db.commit()
    return APIMessage(message="Cart cleared")
