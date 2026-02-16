from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.init_db import init_db
from src.api.routers import auth, cart, orders, owner, restaurants

openapi_tags = [
    {"name": "Auth", "description": "User registration, login, and profile."},
    {"name": "Restaurants", "description": "Browse restaurants and menus."},
    {"name": "Cart", "description": "Customer cart operations."},
    {"name": "Orders", "description": "Customer order placement and tracking."},
    {"name": "Owner", "description": "Restaurant owner management dashboard endpoints."},
]


app = FastAPI(
    title="Zwiggy Backend API",
    description=(
        "Zwiggy is a food ordering platform (Swiggy/Zomato-style) supporting customers and restaurant owners.\n\n"
        "Auth uses Bearer JWT tokens.\n"
        "- Customers: browse restaurants, manage cart, place & track orders.\n"
        "- Owners: manage restaurants/menu, view orders, update order statuses.\n"
    ),
    version="1.0.0",
    openapi_tags=openapi_tags,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Frontend container will call backend; tighten for production deployments.
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def _startup() -> None:
    """Initialize database tables on application startup."""
    init_db()


@app.get(
    "/",
    tags=["Auth"],
    summary="Health check",
    description="Basic service health check.",
)
def health_check():
    return {"message": "Healthy"}


# Routers
app.include_router(auth.router)
app.include_router(restaurants.router)
app.include_router(cart.router)
app.include_router(orders.router)
app.include_router(owner.router)
