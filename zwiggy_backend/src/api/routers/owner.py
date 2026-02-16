from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.api.db import get_db
from src.api.deps import require_role
from src.api.models import MenuItem, Order, OrderStatusHistory, Restaurant, UserRole
from src.api.schemas import (
    APIMessage,
    MenuItemCreateRequest,
    MenuItemResponse,
    MenuItemUpdateRequest,
    OwnerUpdateOrderStatusRequest,
    OrderResponse,
    RestaurantCreateRequest,
    RestaurantResponse,
    RestaurantUpdateRequest,
)

router = APIRouter(prefix="/owner", tags=["Owner"])


def _ensure_owner_restaurant(db: Session, owner_id: int, restaurant_id: int) -> Restaurant:
    restaurant = db.get(Restaurant, restaurant_id)
    if not restaurant or restaurant.owner_id != owner_id:
        raise HTTPException(status_code=404, detail="Restaurant not found")
    return restaurant


@router.get(
    "/restaurants",
    response_model=List[RestaurantResponse],
    summary="List my restaurants",
    description="Owner lists restaurants they own.",
)
def list_my_restaurants(
    db: Session = Depends(get_db),
    owner=Depends(require_role(UserRole.OWNER)),
) -> List[RestaurantResponse]:
    stmt = select(Restaurant).where(Restaurant.owner_id == owner.id).order_by(Restaurant.created_at.desc())
    restaurants = list(db.scalars(stmt).all())
    return [RestaurantResponse.model_validate(r) for r in restaurants]


@router.post(
    "/restaurants",
    response_model=RestaurantResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create restaurant",
    description="Owner creates a new restaurant.",
)
def create_restaurant(
    payload: RestaurantCreateRequest,
    db: Session = Depends(get_db),
    owner=Depends(require_role(UserRole.OWNER)),
) -> RestaurantResponse:
    restaurant = Restaurant(
        owner_id=owner.id,
        name=payload.name,
        description=payload.description,
        address=payload.address,
        is_open=payload.is_open,
    )
    db.add(restaurant)
    db.commit()
    db.refresh(restaurant)
    return RestaurantResponse.model_validate(restaurant)


@router.patch(
    "/restaurants/{restaurant_id}",
    response_model=RestaurantResponse,
    summary="Update restaurant",
    description="Owner updates a restaurant they own.",
)
def update_restaurant(
    restaurant_id: int,
    payload: RestaurantUpdateRequest,
    db: Session = Depends(get_db),
    owner=Depends(require_role(UserRole.OWNER)),
) -> RestaurantResponse:
    restaurant = _ensure_owner_restaurant(db, owner.id, restaurant_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(restaurant, field, value)
    db.commit()
    db.refresh(restaurant)
    return RestaurantResponse.model_validate(restaurant)


@router.delete(
    "/restaurants/{restaurant_id}",
    response_model=APIMessage,
    summary="Delete restaurant",
    description="Owner deletes a restaurant they own (cascades menu items).",
)
def delete_restaurant(
    restaurant_id: int,
    db: Session = Depends(get_db),
    owner=Depends(require_role(UserRole.OWNER)),
) -> APIMessage:
    restaurant = _ensure_owner_restaurant(db, owner.id, restaurant_id)
    db.delete(restaurant)
    db.commit()
    return APIMessage(message="Deleted")


@router.post(
    "/restaurants/{restaurant_id}/menu",
    response_model=MenuItemResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create menu item",
    description="Owner adds a menu item to their restaurant.",
)
def create_menu_item(
    restaurant_id: int,
    payload: MenuItemCreateRequest,
    db: Session = Depends(get_db),
    owner=Depends(require_role(UserRole.OWNER)),
) -> MenuItemResponse:
    _ensure_owner_restaurant(db, owner.id, restaurant_id)
    item = MenuItem(
        restaurant_id=restaurant_id,
        name=payload.name,
        description=payload.description,
        price=payload.price,
        is_available=payload.is_available,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return MenuItemResponse.model_validate(item)


@router.patch(
    "/menu/{menu_item_id}",
    response_model=MenuItemResponse,
    summary="Update menu item",
    description="Owner updates a menu item (must belong to one of their restaurants).",
)
def update_menu_item(
    menu_item_id: int,
    payload: MenuItemUpdateRequest,
    db: Session = Depends(get_db),
    owner=Depends(require_role(UserRole.OWNER)),
) -> MenuItemResponse:
    item = db.get(MenuItem, menu_item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Menu item not found")
    _ensure_owner_restaurant(db, owner.id, item.restaurant_id)

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(item, field, value)
    db.commit()
    db.refresh(item)
    return MenuItemResponse.model_validate(item)


@router.delete(
    "/menu/{menu_item_id}",
    response_model=APIMessage,
    summary="Delete menu item",
    description="Owner deletes a menu item.",
)
def delete_menu_item(
    menu_item_id: int,
    db: Session = Depends(get_db),
    owner=Depends(require_role(UserRole.OWNER)),
) -> APIMessage:
    item = db.get(MenuItem, menu_item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Menu item not found")
    _ensure_owner_restaurant(db, owner.id, item.restaurant_id)
    db.delete(item)
    db.commit()
    return APIMessage(message="Deleted")


@router.get(
    "/orders",
    response_model=List[OrderResponse],
    summary="List orders for my restaurants",
    description="Owner lists orders for all restaurants they own.",
)
def list_orders(
    db: Session = Depends(get_db),
    owner=Depends(require_role(UserRole.OWNER)),
) -> List[OrderResponse]:
    # Find owned restaurants
    restaurant_ids = list(db.scalars(select(Restaurant.id).where(Restaurant.owner_id == owner.id)).all())
    if not restaurant_ids:
        return []
    stmt = select(Order).where(Order.restaurant_id.in_(restaurant_ids)).order_by(Order.created_at.desc())
    orders = list(db.scalars(stmt).all())
    return [OrderResponse.model_validate(o) for o in orders]


@router.get(
    "/orders/{order_id}",
    response_model=OrderResponse,
    summary="Get order details (owner)",
    description="Owner fetches order details for an order belonging to their restaurant.",
)
def get_order(
    order_id: int,
    db: Session = Depends(get_db),
    owner=Depends(require_role(UserRole.OWNER)),
) -> OrderResponse:
    order = db.get(Order, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    _ensure_owner_restaurant(db, owner.id, order.restaurant_id)
    order.items  # noqa: B018
    order.status_history  # noqa: B018
    return OrderResponse.model_validate(order)


@router.post(
    "/orders/{order_id}/status",
    response_model=OrderResponse,
    summary="Update order status (owner)",
    description="Owner updates the status of an order for their restaurant; status changes are tracked in history.",
)
def update_order_status(
    order_id: int,
    payload: OwnerUpdateOrderStatusRequest,
    db: Session = Depends(get_db),
    owner=Depends(require_role(UserRole.OWNER)),
) -> OrderResponse:
    order = db.get(Order, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    _ensure_owner_restaurant(db, owner.id, order.restaurant_id)

    order.status = payload.status
    db.add(OrderStatusHistory(order_id=order.id, status=payload.status, note=payload.note))
    db.commit()
    db.refresh(order)
    order.items  # noqa: B018
    order.status_history  # noqa: B018
    return OrderResponse.model_validate(order)
