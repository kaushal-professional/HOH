"""
Admin Login API endpoints.

This module provides CRUD operations and authentication for admin users.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

from app.core.database import get_db
from app.core.auth import get_password_hash, verify_password, create_access_token
from app.models.login import Login
from app.schemas.login import (
    LoginCreate,
    LoginUpdate,
    LoginOut,
    LoginAuth,
    LoginAuthResponse,
)

router = APIRouter(prefix="/admin", tags=["Admin Login"])


@router.post("/", response_model=LoginOut, status_code=status.HTTP_201_CREATED)
def create_admin(admin_data: LoginCreate, db: Session = Depends(get_db)):
    """
    Create a new admin user.

    Args:
        admin_data: Admin creation data with plain text password
        db: Database session

    Returns:
        Created admin information (without password)

    Raises:
        HTTPException 400: If email already exists
    """
    # Check if email already exists
    existing_admin = db.query(Login).filter(Login.email == admin_data.email).first()
    if existing_admin:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )

    # Hash the password
    hashed_password = get_password_hash(admin_data.password)

    # Create admin instance
    new_admin = Login(
        name=admin_data.name,
        email=admin_data.email,
        password=hashed_password
    )

    db.add(new_admin)
    db.commit()
    db.refresh(new_admin)

    return new_admin


@router.get("/", response_model=List[LoginOut])
def get_all_admins(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    """
    Get all admin users with pagination.

    Args:
        skip: Number of records to skip (default: 0)
        limit: Maximum number of records to return (default: 100)
        db: Database session

    Returns:
        List of admins (without passwords)
    """
    admins = db.query(Login).offset(skip).limit(limit).all()
    return admins


@router.get("/{admin_id}", response_model=LoginOut)
def get_admin_by_id(admin_id: int, db: Session = Depends(get_db)):
    """
    Get a specific admin by ID.

    Args:
        admin_id: Admin ID
        db: Database session

    Returns:
        Admin information (without password)

    Raises:
        HTTPException 404: If admin not found
    """
    admin = db.query(Login).filter(Login.id == admin_id).first()
    if not admin:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Admin with ID {admin_id} not found"
        )
    return admin


@router.put("/{admin_id}", response_model=LoginOut)
def update_admin(admin_id: int, admin_data: LoginUpdate, db: Session = Depends(get_db)):
    """
    Update an existing admin user.

    Args:
        admin_id: Admin ID to update
        admin_data: Updated admin data (all fields optional)
        db: Database session

    Returns:
        Updated admin information (without password)

    Raises:
        HTTPException 404: If admin not found
        HTTPException 400: If email already exists for another admin
    """
    # Find the admin
    admin = db.query(Login).filter(Login.id == admin_id).first()
    if not admin:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Admin with ID {admin_id} not found"
        )

    # Check if email is being updated and if it already exists
    if admin_data.email and admin_data.email != admin.email:
        existing_admin = db.query(Login).filter(Login.email == admin_data.email).first()
        if existing_admin:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered"
            )

    # Update fields if provided
    update_data = admin_data.model_dump(exclude_unset=True)

    # Hash password if it's being updated
    if "password" in update_data:
        update_data["password"] = get_password_hash(update_data["password"])

    for field, value in update_data.items():
        setattr(admin, field, value)

    db.commit()
    db.refresh(admin)

    return admin


@router.delete("/{admin_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_admin(admin_id: int, db: Session = Depends(get_db)):
    """
    Delete an admin user by ID.

    Args:
        admin_id: Admin ID to delete
        db: Database session

    Returns:
        None (204 No Content)

    Raises:
        HTTPException 404: If admin not found
    """
    admin = db.query(Login).filter(Login.id == admin_id).first()
    if not admin:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Admin with ID {admin_id} not found"
        )

    db.delete(admin)
    db.commit()

    return None


@router.post("/login", response_model=LoginAuthResponse)
def login_admin(login_data: LoginAuth, db: Session = Depends(get_db)):
    """
    Authenticate an admin user and return access token.

    Args:
        login_data: Login credentials (email and plain text password)
        db: Database session

    Returns:
        Access token and admin information

    Raises:
        HTTPException 401: If credentials are invalid
    """
    # Find admin by email
    admin = db.query(Login).filter(Login.email == login_data.email).first()
    if not admin:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Verify password
    if not verify_password(login_data.password, admin.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Create access token
    token_data = {
        "admin_id": admin.id,
        "email": admin.email,
        "name": admin.name,
    }
    access_token = create_access_token(data=token_data)

    return LoginAuthResponse(
        access_token=access_token,
        token_type="bearer",
        admin=admin
    )


@router.get("/email/{email}", response_model=LoginOut)
def get_admin_by_email(email: str, db: Session = Depends(get_db)):
    """
    Get an admin by email address.

    Args:
        email: Admin email address
        db: Database session

    Returns:
        Admin information (without password)

    Raises:
        HTTPException 404: If admin not found
    """
    admin = db.query(Login).filter(Login.email == email).first()
    if not admin:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Admin with email '{email}' not found"
        )
    return admin
