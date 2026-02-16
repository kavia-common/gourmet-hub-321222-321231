from decimal import Decimal
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from src.api.db import get_db
from src.api.deps import require_role
from src.api.models import CartItem, MenuItem, Order, OrderItem, OrderStatus, OrderStatusHistory, UserRole
from src.api.schemas import APIMessage, OrderResponse, PlaceOrderRequest

router = APIRouter(prefix="/orders", tags=["Orders"])


def _order_to_schema(order: Order) -> OrderResponse:
    return OrderResponse.model_validate(order)


@router.post(
    "",
    response_model=OrderResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Place an order from current cart",
    description="Creates an order from the current cart, records status history, and clears the cart.",
)
def place_order(
    payload: PlaceOrderRequest,
    db: Session = Depends(get_db),
    user=Depends(require_role(UserRole.CUSTOMER)),
) -> OrderResponse:
    stmt = (
        select(CartItem, MenuItem)
        .join(MenuItem, MenuItem.id == CartItem.menu_item_id)
        .where(CartItem.user_id == user.id)
        .order_by(CartItem.created_at.asc())
    )
    rows = db.execute(stmt).all()
    if not rows:
        raise HTTPException(status_code=400, detail="Cart is empty")

    restaurant_id = rows[0][1].restaurant_id
    for _, menu_item in rows:
        if menu_item.restaurant_id != restaurant_id:
            raise HTTPException(status_code=400, detail="Cart contains multiple restaurants (not allowed)")

    total = Decimal("0.00")
    order = Order(
        user_id=user.id,
        restaurant_id=restaurant_id,
        delivery_address=payload.delivery_address,
        total_amount=Decimal("0.00"),
        status=OrderStatus.PLACED,
    )
    db.add(order)
    db.flush()  # assign order.id

    for cart_item, menu_item in rows:
        if not menu_item.is_available:
            raise HTTPException(status_code=400, detail=f"Menu item unavailable: {menu_item.name}")
        price = Decimal(str(menu_item.price))
        line_total = price * cart_item.quantity
        total += line_total
        db.add(
            OrderItem(
                order_id=order.id,
                menu_item_id=menu_item.id,
                name_snapshot=menu_item.name,
                price_snapshot=price,
                quantity=cart_item.quantity,
            )
        )

    order.total_amount = total
    db.add(OrderStatusHistory(order_id=order.id, status=OrderStatus.PLACED, note="Order placed"))
    db.execute(delete(CartItem).where(CartItem.user_id == user.id))

    db.commit()
    db.refresh(order)
    # relationships may lazy-load; ensure they are available for response
    order.items  # noqa: B018
    order.status_history  # noqa: B018
    return _order_to_schema(order)


@router.get(
    "",
    response_model=List[OrderResponse],
    summary="List my orders (customer)",
    description="Returns orders for the authenticated customer.",
)
def list_my_orders(
    db: Session = Depends(get_db),
    user=Depends(require_role(UserRole.CUSTOMER)),
) -> List[OrderResponse]:
    stmt = select(Order).where(Order.user_id == user.id).order_by(Order.created_at.desc())
    orders = list(db.scalars(stmt).all())
    return [_order_to_schema(o) for o in orders]


@router.get(
    "/{order_id}",
    response_model=OrderResponse,
    summary="Get order details (customer)",
    description="Returns order details and status history for the authenticated customer.",
)
def get_my_order(
    order_id: int,
    db: Session = Depends(get_db),
    user=Depends(require_role(UserRole.CUSTOMER)),
) -> OrderResponse:
    order = db.get(Order, order_id)
    if not order or order.user_id != user.id:
        raise HTTPException(status_code=404, detail="Order not found")
    order.items  # noqa: B018
    order.status_history  # noqa: B018
    return _order_to_schema(order)


@router.post(
    "/{order_id}/cancel",
    response_model=APIMessage,
    summary="Cancel an order (customer)",
    description="Allows a customer to cancel an order only if it has not progressed beyond 'confirmed'.",
)
def cancel_order(
    order_id: int,
    db: Session = Depends(get_db),
    user=Depends(require_role(UserRole.CUSTOMER)),
) -> APIMessage:
    order = db.get(Order, order_id)
    if not order or order.user_id != user.id:
        raise HTTPException(status_code=404, detail="Order not found")

    if order.status not in (OrderStatus.PLACED, OrderStatus.CONFIRMED):
        raise HTTPException(status_code=400, detail="Order cannot be cancelled at current status")

    order.status = OrderStatus.CANCELLED
    db.add(OrderStatusHistory(order_id=order.id, status=OrderStatus.CANCELLED, note="Cancelled by customer"))
    db.commit()
    return APIMessage(message="Order cancelled")
