
from uuid import UUID
from decimal import Decimal

from fastapi import APIRouter, Query, HTTPException
from pydantic import BaseModel
from sqlalchemy import text

from database import engine

router = APIRouter(prefix="/products", tags=["Products"])


class ProductSummary(BaseModel):
    product_id: UUID
    name: str
    description: str | None
    price: Decimal
    stock_quantity: int
    is_active: bool



@router.get("", response_model=list[ProductSummary])
def get_products(
    search: str | None = Query(default=None, min_length=1),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0)
):
    query = """
        SELECT
            product_id,
            name,
            description,
            price,
            stock_quantity,
            is_active
        FROM products
        WHERE is_active = TRUE
    """

    params = {"limit": limit, "offset": offset}

    # Add search filter only when a keyword is provided
    if search is not None:
        query += " AND name ILIKE :pattern"
        params["pattern"] = f"%{search}%"

    query += """
        ORDER BY name, product_id
        LIMIT :limit OFFSET :offset
    """

    with engine.connect() as conn:
        products = conn.execute(
            text(query), params
        ).mappings().all()

    return [dict(product) for product in products]


@router.get("/{product_id}", response_model=ProductSummary)
def get_product_by_id(product_id: UUID):

    with engine.connect() as conn:
        product = conn.execute(
            text("""
                SELECT
                    product_id,
                    name,
                    description,
                    price,
                    stock_quantity,
                    is_active
                FROM products
                WHERE product_id = :product_id
            """),
            {"product_id": product_id}
        ).mappings().first()

    if product is None:
        raise HTTPException(
            status_code=404,
            detail="Product not found"
        )

    return dict(product)
