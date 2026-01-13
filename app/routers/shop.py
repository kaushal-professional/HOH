"""
Shop API endpoints.

This module provides CRUD operations and authentication for shops.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

from app.core.database import get_db
from app.core.auth import get_password_hash, verify_password, create_access_token
from app.models.shop import Shop
from app.schemas.shop import (
    ShopCreate,
    ShopUpdate,
    ShopOut,
    ShopLogin,
    ShopLoginResponse,
)

router = APIRouter(prefix="/shops", tags=["Shops"])


@router.post("/", response_model=ShopOut, status_code=status.HTTP_201_CREATED)
def create_shop(shop_data: ShopCreate, db: Session = Depends(get_db)):
    """
    Create a new shop.

    Args:
        shop_data: Shop creation data with plain text password
        db: Database session

    Returns:
        Created shop information (without password)

    Raises:
        HTTPException 400: If email already exists
    """
    # Check if email already exists
    existing_shop = db.query(Shop).filter(Shop.email == shop_data.email).first()
    if existing_shop:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )

    # Hash the password
    hashed_password = get_password_hash(shop_data.password)

    # Create shop instance
    new_shop = Shop(
        company=shop_data.company,
        users=shop_data.users,
        pos_shop_name=shop_data.pos_shop_name,
        email=shop_data.email,
        password=hashed_password
    )

    db.add(new_shop)
    db.commit()
    db.refresh(new_shop)

    return new_shop


@router.get("/", response_model=List[ShopOut])
def get_all_shops(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    """
    Get all shops with pagination.

    Args:
        skip: Number of records to skip (default: 0)
        limit: Maximum number of records to return (default: 100)
        db: Database session

    Returns:
        List of shops (without passwords)
    """
    shops = db.query(Shop).offset(skip).limit(limit).all()
    return shops


@router.get("/{shop_id}", response_model=ShopOut)
def get_shop_by_id(shop_id: int, db: Session = Depends(get_db)):
    """
    Get a specific shop by ID.

    Args:
        shop_id: Shop ID
        db: Database session

    Returns:
        Shop information (without password)

    Raises:
        HTTPException 404: If shop not found
    """
    shop = db.query(Shop).filter(Shop.id == shop_id).first()
    if not shop:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Shop with ID {shop_id} not found"
        )
    return shop


@router.put("/{shop_id}", response_model=ShopOut)
def update_shop(shop_id: int, shop_data: ShopUpdate, db: Session = Depends(get_db)):
    """
    Update an existing shop.

    Args:
        shop_id: Shop ID to update
        shop_data: Updated shop data (all fields optional)
        db: Database session

    Returns:
        Updated shop information (without password)

    Raises:
        HTTPException 404: If shop not found
        HTTPException 400: If email already exists for another shop
    """
    # Find the shop
    shop = db.query(Shop).filter(Shop.id == shop_id).first()
    if not shop:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Shop with ID {shop_id} not found"
        )

    # Check if email is being updated and if it already exists
    if shop_data.email and shop_data.email != shop.email:
        existing_shop = db.query(Shop).filter(Shop.email == shop_data.email).first()
        if existing_shop:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered"
            )

    # Update fields if provided
    update_data = shop_data.model_dump(exclude_unset=True)

    # Hash password if it's being updated
    if "password" in update_data:
        update_data["password"] = get_password_hash(update_data["password"])

    for field, value in update_data.items():
        setattr(shop, field, value)

    db.commit()
    db.refresh(shop)

    return shop


@router.delete("/{shop_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_shop(shop_id: int, db: Session = Depends(get_db)):
    """
    Delete a shop by ID.

    Args:
        shop_id: Shop ID to delete
        db: Database session

    Returns:
        None (204 No Content)

    Raises:
        HTTPException 404: If shop not found
    """
    shop = db.query(Shop).filter(Shop.id == shop_id).first()
    if not shop:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Shop with ID {shop_id} not found"
        )

    db.delete(shop)
    db.commit()

    return None


@router.post("/login", response_model=ShopLoginResponse)
def login_shop(login_data: ShopLogin, db: Session = Depends(get_db)):
    """
    Authenticate a shop and return access token.

    Args:
        login_data: Login credentials (email and plain text password)
        db: Database session

    Returns:
        Access token and shop information

    Raises:
        HTTPException 401: If credentials are invalid
    """
    # Find shop by email
    shop = db.query(Shop).filter(Shop.email == login_data.email).first()
    if not shop:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Verify password
    if not verify_password(login_data.password, shop.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Create access token
    token_data = {
        "shop_id": shop.id,
        "email": shop.email,
        "company": shop.company,
        "pos_shop_name": shop.pos_shop_name,
    }
    access_token = create_access_token(data=token_data)

    return ShopLoginResponse(
        access_token=access_token,
        token_type="bearer",
        shop=shop
    )


@router.get("/email/{email}", response_model=ShopOut)
def get_shop_by_email(email: str, db: Session = Depends(get_db)):
    """
    Get a shop by email address.

    Args:
        email: Shop email address
        db: Database session

    Returns:
        Shop information (without password)

    Raises:
        HTTPException 404: If shop not found
    """
    shop = db.query(Shop).filter(Shop.email == email).first()
    if not shop:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Shop with email '{email}' not found"
        )
    return shop
