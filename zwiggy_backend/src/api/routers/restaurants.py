from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.api.db import get_db
from src.api.models import MenuItem, Restaurant
from src.api.schemas import MenuItemResponse, RestaurantResponse

router = APIRouter(prefix="/restaurants", tags=["Restaurants"])


@router.get(
    "",
    response_model=List[RestaurantResponse],
    summary="List restaurants",
    description="Browse restaurants. Optionally filter by text query and open status.",
)
def list_restaurants(
    q: Optional[str] = Query(None, description="Search term for restaurant name."),
    open_only: bool = Query(False, description="If true, return only currently open restaurants."),
    db: Session = Depends(get_db),
) -> List[RestaurantResponse]:
    stmt = select(Restaurant)
    if q:
        stmt = stmt.where(Restaurant.name.ilike(f"%{q}%"))
    if open_only:
        stmt = stmt.where(Restaurant.is_open.is_(True))
    stmt = stmt.order_by(Restaurant.created_at.desc())
    restaurants = list(db.scalars(stmt).all())
    return [RestaurantResponse.model_validate(r) for r in restaurants]


@router.get(
    "/{restaurant_id}",
    response_model=RestaurantResponse,
    summary="Get restaurant details",
    description="Fetch a restaurant by id.",
)
def get_restaurant(restaurant_id: int, db: Session = Depends(get_db)) -> RestaurantResponse:
    restaurant = db.get(Restaurant, restaurant_id)
    if not restaurant:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail="Restaurant not found")
    return RestaurantResponse.model_validate(restaurant)


@router.get(
    "/{restaurant_id}/menu",
    response_model=List[MenuItemResponse],
    summary="List a restaurant's menu items",
    description="Returns menu items for a restaurant (availability can be filtered).",
)
def list_menu_items(
    restaurant_id: int,
    available_only: bool = Query(True, description="If true, return only available items."),
    db: Session = Depends(get_db),
) -> List[MenuItemResponse]:
    stmt = select(MenuItem).where(MenuItem.restaurant_id == restaurant_id)
    if available_only:
        stmt = stmt.where(MenuItem.is_available.is_(True))
    stmt = stmt.order_by(MenuItem.id.asc())
    items = list(db.scalars(stmt).all())
    return [MenuItemResponse.model_validate(i) for i in items]
