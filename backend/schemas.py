from pydantic import BaseModel, EmailStr, Field, validator
from typing import Optional, List, Any, Dict
from datetime import datetime
from enum import Enum

# ============== User Schemas ==============
class UserBase(BaseModel):
    username: str
    email: EmailStr
    full_name: Optional[str] = None
    phone: Optional[str] = None

class UserCreate(UserBase):
    password: str
    role_id: Optional[int] = None

class UserUpdate(BaseModel):
    full_name: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[EmailStr] = None
    is_active: Optional[bool] = None
    role_id: Optional[int] = None

class UserInDB(UserBase):
    id: int
    is_active: bool
    is_superuser: bool
    role_id: Optional[int]
    role: Optional['RoleInDB'] = None
    created_at: datetime
    last_login: Optional[datetime]

    class Config:
        from_attributes = True

class UserLogin(BaseModel):
    username: str
    password: str

class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"

class TokenData(BaseModel):
    username: Optional[str] = None
    user_id: Optional[int] = None

# ============== Role va Permission Schemas ==============
class PermissionBase(BaseModel):
    code: str
    description: Optional[str] = None

class PermissionCreate(PermissionBase):
    pass

class PermissionInDB(PermissionBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True

class RoleBase(BaseModel):
    name: str
    description: Optional[str] = None

class RoleCreate(RoleBase):
    permission_ids: Optional[List[int]] = []

class RoleUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None

class RoleInDB(RoleBase):
    id: int
    permissions: List[PermissionInDB] = []
    created_at: datetime

    class Config:
        from_attributes = True

# ============== Category Schemas ==============
class CategoryBase(BaseModel):
    name: str
    description: Optional[str] = None
    parent_id: Optional[int] = None
    display_order: int = 0

class CategoryCreate(CategoryBase):
    pass

class CategoryUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    parent_id: Optional[int] = None
    display_order: Optional[int] = None
    is_active: Optional[bool] = None

class CategoryInDB(CategoryBase):
    id: int
    image_url: Optional[str] = None
    is_active: bool
    created_at: datetime
    updated_at: Optional[datetime] = None
    children: List['CategoryInDB'] = []

    class Config:
        from_attributes = True

# ============== Product Schemas ==============
class ProductBase(BaseModel):
    name: str
    description: Optional[str] = None
    price: float = Field(gt=0)
    cost_price: float = 0.0
    barcode: Optional[str] = None
    sku: Optional[str] = None
    category_id: int
    preparation_time: int = 10

class ProductCreate(ProductBase):
    pass

class ProductUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    price: Optional[float] = Field(None, gt=0)
    cost_price: Optional[float] = None
    barcode: Optional[str] = None
    sku: Optional[str] = None
    category_id: Optional[int] = None
    preparation_time: Optional[int] = None
    is_active: Optional[bool] = None
    is_available: Optional[bool] = None

class ProductInDB(ProductBase):
    id: int
    image_url: Optional[str] = None
    is_active: bool
    is_available: bool
    created_at: datetime
    updated_at: Optional[datetime] = None
    category: Optional[CategoryInDB] = None

    class Config:
        from_attributes = True

# ============== Table Schemas ==============
class TableBase(BaseModel):
    number: str
    name: Optional[str] = None
    capacity: int = 4
    section: Optional[str] = None
    position_x: Optional[int] = None
    position_y: Optional[int] = None

class TableCreate(TableBase):
    pass

class TableUpdate(BaseModel):
    name: Optional[str] = None
    capacity: Optional[int] = None
    section: Optional[str] = None
    status: Optional[str] = None
    position_x: Optional[int] = None
    position_y: Optional[int] = None

class TableInDB(TableBase):
    id: int
    status: str
    created_at: datetime
    updated_at: Optional[datetime] = None
    current_order: Optional['OrderInDB'] = None

    class Config:
        from_attributes = True

# ============== Order Schemas ==============
class OrderItemCreate(BaseModel):
    product_id: int
    quantity: int = Field(gt=0)
    notes: Optional[str] = None

class OrderItemUpdate(BaseModel):
    quantity: Optional[int] = Field(None, gt=0)
    notes: Optional[str] = None
    status: Optional[str] = None

class OrderItemInDB(BaseModel):
    id: int
    product_id: int
    product_name: str
    quantity: int
    unit_price: float
    total_price: float
    notes: Optional[str] = None
    status: str
    created_at: datetime

    class Config:
        from_attributes = True

class OrderCreate(BaseModel):
    table_id: Optional[int] = None
    customer_id: Optional[int] = None
    items: List[OrderItemCreate]
    notes: Optional[str] = None
    order_type: str = "dine-in"

class OrderUpdate(BaseModel):
    status: Optional[str] = None
    notes: Optional[str] = None
    discount_amount: Optional[float] = None

class OrderInDB(BaseModel):
    id: int
    order_number: str
    table_id: Optional[int] = None
    table_number: Optional[str] = None
    waiter_id: Optional[int] = None
    waiter_name: Optional[str] = None
    customer_id: Optional[int] = None
    customer_name: Optional[str] = None
    status: str
    total_amount: float
    discount_amount: float
    tax_amount: float
    final_amount: float
    notes: Optional[str] = None
    items: List[OrderItemInDB] = []
    created_at: datetime
    updated_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    class Config:
        from_attributes = True

# ============== Payment Schemas ==============
class PaymentCreate(BaseModel):
    order_id: int
    amount: float = Field(gt=0)
    method: str
    reference: Optional[str] = None
    cash_received: Optional[float] = None

class PaymentInDB(BaseModel):
    id: int
    order_id: int
    cashier_id: Optional[int] = None
    amount: float
    method: str
    status: str
    transaction_id: Optional[str] = None
    reference: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True

# ============== Customer Schemas ==============
class CustomerBase(BaseModel):
    name: str
    phone: Optional[str] = None
    email: Optional[EmailStr] = None
    birthday: Optional[datetime] = None

class CustomerCreate(CustomerBase):
    pass

class CustomerUpdate(BaseModel):
    name: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[EmailStr] = None
    birthday: Optional[datetime] = None

class CustomerInDB(CustomerBase):
    id: int
    total_visits: int
    total_spent: float
    points: int
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True

# ============== Shift Schemas ==============
class ShiftBase(BaseModel):
    user_id: int
    starting_cash: float = 0.0

class ShiftCreate(ShiftBase):
    pass

class ShiftUpdate(BaseModel):
    ending_cash: Optional[float] = None
    notes: Optional[str] = None

class ShiftInDB(ShiftBase):
    id: int
    start_time: datetime
    end_time: Optional[datetime] = None
    ending_cash: Optional[float] = None
    total_sales: float
    cash_sales: float
    card_sales: float
    notes: Optional[str] = None
    user: Optional[UserInDB] = None

    class Config:
        from_attributes = True

# ============== Reservation Schemas ==============
class ReservationBase(BaseModel):
    customer_id: int
    table_id: int
    reservation_time: datetime
    duration_minutes: int = 120
    guests_count: int = 2
    notes: Optional[str] = None

class ReservationCreate(ReservationBase):
    pass

class ReservationUpdate(BaseModel):
    status: Optional[str] = None
    notes: Optional[str] = None

class ReservationInDB(ReservationBase):
    id: int
    status: str
    created_at: datetime
    customer: Optional[CustomerInDB] = None
    table: Optional[TableInDB] = None

    class Config:
        from_attributes = True

# ============== Inventory Schemas ==============
class InventoryBase(BaseModel):
    product_id: int
    quantity: float = 0.0
    unit: str = "kg"
    min_threshold: float = 5.0
    max_threshold: float = 100.0

class InventoryCreate(InventoryBase):
    pass

class InventoryUpdate(BaseModel):
    quantity: Optional[float] = None
    min_threshold: Optional[float] = None
    max_threshold: Optional[float] = None

class InventoryInDB(InventoryBase):
    id: int
    last_restock: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    product: Optional[ProductInDB] = None

    class Config:
        from_attributes = True

# ============== Discount Schemas ==============
class DiscountBase(BaseModel):
    name: str
    type: str
    value: float
    product_id: Optional[int] = None
    category_id: Optional[int] = None
    min_order_amount: float = 0.0
    valid_from: Optional[datetime] = None
    valid_to: Optional[datetime] = None
    usage_limit: Optional[int] = None

class DiscountCreate(DiscountBase):
    pass

class DiscountInDB(DiscountBase):
    id: int
    is_active: bool
    used_count: int
    created_at: datetime

    class Config:
        from_attributes = True

# ============== Notification Schemas ==============
class NotificationBase(BaseModel):
    title: str
    message: str
    type: str = "system"
    data: Optional[Dict[str, Any]] = None

class NotificationCreate(NotificationBase):
    user_id: int

class NotificationInDB(NotificationBase):
    id: int
    user_id: int
    is_read: bool
    created_at: datetime

    class Config:
        from_attributes = True

# ============== Report Schemas ==============
class DailyReportData(BaseModel):
    date: str
    total_sales: float
    cash_sales: float
    card_sales: float
    orders_count: int
    completed_orders: int
    cancelled_orders: int
    avg_check: float

class SalesReportData(BaseModel):
    date_from: str
    date_to: str
    total_sales: float
    daily_sales: List[Dict[str, Any]]
    payment_methods: List[Dict[str, Any]]

# ============== API Response Schemas ==============
class PaginationParams(BaseModel):
    page: int = Field(1, ge=1)
    page_size: int = Field(20, ge=1, le=100)

class PaginatedResponse(BaseModel):
    items: List[Any]
    total: int
    page: int
    page_size: int
    total_pages: int

class MessageResponse(BaseModel):
    message: str
    success: bool = True

class ErrorResponse(BaseModel):
    detail: str
    error_code: Optional[str] = None

# ============== Analytics Schemas ==============
class DashboardData(BaseModel):
    total_revenue: float
    total_orders: int
    total_customers: int
    average_check: float
    revenue_trend: float
    orders_trend: float
    customers_trend: float
    avg_check_trend: float
    revenue_data: Dict[str, List]
    popular_products: List[Dict[str, Any]]
    categories_data: List[Dict[str, Any]]
    payment_methods: List[Dict[str, Any]]
    recent_orders: List[Dict[str, Any]]

# ============== Kitchen Schemas ==============
class KitchenOrderItem(BaseModel):
    id: int
    product_id: int
    product_name: str
    quantity: int
    notes: Optional[str] = None
    status: str

class KitchenOrder(BaseModel):
    id: int
    order_number: str
    table_number: Optional[str] = None
    order_type: str
    waiter_name: Optional[str] = None
    customer_name: Optional[str] = None
    created_at: datetime
    status: str
    notes: Optional[str] = None
    urgent: bool = False
    items: List[KitchenOrderItem]

class KitchenOrdersResponse(BaseModel):
    pending: List[KitchenOrder]
    preparing: List[KitchenOrder]
    ready: List[KitchenOrder]
    completed: List[KitchenOrder]