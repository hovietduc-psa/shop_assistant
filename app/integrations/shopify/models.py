"""
Shopify data models.
"""

from datetime import datetime
from decimal import Decimal
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, validator


class ShopifyError(Exception):
    """Custom exception for Shopify API errors."""

    def __init__(self, message: str, status_code: Optional[int] = None, response: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.status_code = status_code
        self.response = response


class ShopifyConfig(BaseModel):
    """Shopify configuration settings."""
    shop_domain: str
    access_token: str
    api_version: str = "2024-01"
    webhook_secret: Optional[str] = None
    app_secret: Optional[str] = None


class Money(BaseModel):
    """Money value with currency."""
    amount: Decimal
    currency_code: str

    @validator('amount', pre=True)
    def parse_amount(cls, v):
        if isinstance(v, str):
            return Decimal(v)
        return Decimal(str(v))


class MoneySet(BaseModel):
    """Money set with shop and presentment currencies."""
    shop_money: Money
    presentment_money: Optional[Money] = None


class Image(BaseModel):
    """Product image."""
    id: str
    src: str
    alt: Optional[str] = None  # Changed from alt_text to alt to match Shopify API
    width: Optional[int] = None
    height: Optional[int] = None
    position: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    product_id: Optional[str] = None
    variant_ids: List[str] = []


class ProductOption(BaseModel):
    """Product option (like Size, Color, etc.)."""
    id: str
    product_id: Optional[str] = None  # Made optional for GraphQL compatibility
    name: str
    position: Optional[int] = None  # Made optional for GraphQL compatibility
    values: List[str]


class ProductVariant(BaseModel):
    """Product variant information."""
    id: str
    product_id: Optional[str] = None
    title: str
    price: str  # Keep as string to match Shopify API, convert to Money when needed
    compare_at_price: Optional[str] = None
    sku: Optional[str] = None
    weight: Optional[Decimal] = None
    weight_unit: Optional[str] = None
    inventory_quantity: int = 0
    inventory_management: Optional[str] = None
    inventory_policy: Optional[str] = None
    requires_shipping: Optional[bool] = True  # Made optional for GraphQL compatibility
    taxable: Optional[bool] = True  # Made optional for GraphQL compatibility
    position: Optional[int] = None
    option1: Optional[str] = None
    option2: Optional[str] = None
    option3: Optional[str] = None
    barcode: Optional[str] = None
    image_id: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    @property
    def price_money(self) -> Money:
        """Get price as Money object."""
        return Money(amount=Decimal(self.price), currency_code="USD")

    @property
    def compare_at_price_money(self) -> Optional[Money]:
        """Get compare at price as Money object."""
        if self.compare_at_price:
            return Money(amount=Decimal(self.compare_at_price), currency_code="USD")
        return None


class Product(BaseModel):
    """Product information."""
    id: str
    title: str
    handle: str
    body_html: Optional[str] = None  # Changed from description_html to match Shopify API
    vendor: Optional[str] = None
    product_type: Optional[str] = None
    status: str  # active, archived, draft
    tags: str  # Shopify REST API returns tags as comma-separated string, GraphQL returns list (handled by parser)
    images: List[Image] = []
    variants: List[ProductVariant] = []
    options: List[ProductOption] = []
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    published_at: Optional[datetime] = None
    template_suffix: Optional[str] = None
    published_scope: str = "global"
    admin_graphql_api_id: Optional[str] = None

    # SEO fields
    meta_title: Optional[str] = None
    meta_description: Optional[str] = None

    @property
    def description(self) -> Optional[str]:
        """Get product description (alias for body_html without HTML tags)."""
        return self.body_html

    @property
    def tag_list(self) -> List[str]:
        """Get tags as a list."""
        if not self.tags:
            return []
        return [tag.strip() for tag in self.tags.split(',') if tag.strip()]

    @property
    def price_range(self) -> tuple[Decimal, Decimal]:
        """Get min and max price across all variants."""
        if not self.variants:
            return Decimal('0'), Decimal('0')

        prices = [variant.price.amount for variant in self.variants]
        return min(prices), max(prices)

    @property
    def in_stock(self) -> bool:
        """Check if any variant is in stock."""
        return any(variant.inventory_quantity > 0 for variant in self.variants)

    @property
    def primary_image(self) -> Optional[Image]:
        """Get the primary product image."""
        return self.images[0] if self.images else None


class InventoryLocation(BaseModel):
    """Inventory location information."""
    id: str
    name: str
    address1: Optional[str] = None
    address2: Optional[str] = None
    city: Optional[str] = None
    province: Optional[str] = None
    country: Optional[str] = None
    zip: Optional[str] = None
    active: bool = True


class InventoryLevel(BaseModel):
    """Inventory level for a variant at a location."""
    location_id: str
    inventory_item_id: str
    available: int
    updated_at: datetime


class CustomerAddress(BaseModel):
    """Customer address."""
    id: int
    customer_id: int
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    company: Optional[str] = None
    address1: Optional[str] = None
    address2: Optional[str] = None
    city: Optional[str] = None
    province: Optional[str] = None
    country: Optional[str] = None
    zip: Optional[str] = None
    phone: Optional[str] = None
    province_code: Optional[str] = None
    country_code: Optional[str] = None
    country_name: Optional[str] = None
    default: bool = False
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class Customer(BaseModel):
    """Customer information."""
    id: int
    email: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    phone: Optional[str] = None
    addresses: List[CustomerAddress] = []
    orders_count: int = 0
    total_spent: str  # Keep as string to match Shopify API
    state: str  # enabled, disabled, invited
    verified_email: bool = False
    tax_exempt: bool = False
    tags: str  # Shopify API returns tags as comma-separated string
    currency: str = "USD"
    multipass_identifier: Optional[str] = None
    note: Optional[str] = None
    last_order_id: Optional[int] = None
    last_order_name: Optional[str] = None
    admin_graphql_api_id: Optional[str] = None
    marketing_opt_in_level: Optional[str] = None
    tax_exemptions: List[str] = []
    email_marketing_consent: Optional[Dict[str, Any]] = None
    sms_marketing_consent: Optional[Dict[str, Any]] = None
    created_at: datetime
    updated_at: datetime
    default_address: Optional[CustomerAddress] = None

    @property
    def total_spent_money(self) -> Money:
        """Get total spent as Money object."""
        return Money(amount=Decimal(self.total_spent), currency_code=self.currency)

    @property
    def tag_list(self) -> List[str]:
        """Get tags as a list."""
        if not self.tags:
            return []
        return [tag.strip() for tag in self.tags.split(',') if tag.strip()]

    @property
    def full_name(self) -> str:
        """Get customer's full name."""
        if self.first_name and self.last_name:
            return f"{self.first_name} {self.last_name}"
        return self.first_name or self.last_name or ""


class ShippingLine(BaseModel):
    """Shipping line information."""
    id: int
    title: str
    price: str  # Keep as string to match Shopify API
    code: Optional[str] = None
    source: Optional[str] = None
    carrier_identifier: Optional[str] = None
    requested_fulfillment_service_id: Optional[str] = None
    delivery_category: Optional[str] = None
    tax_lines: Optional[List[Dict[str, Any]]] = None

    @property
    def price_money(self) -> Money:
        """Get price as Money object."""
        return Money(amount=Decimal(self.price), currency_code="USD")


class LineItem(BaseModel):
    """Order line item."""
    id: int
    product_id: Optional[int] = None
    variant_id: Optional[int] = None
    title: str
    quantity: int
    price: str  # Keep as string to match Shopify API
    total_discount: str = "0.00"
    sku: Optional[str] = None
    vendor: Optional[str] = None
    product_title: Optional[str] = None
    variant_title: Optional[str] = None
    taxable: bool = True
    requires_shipping: bool = True
    gift_card: bool = False
    fulfillment_service: Optional[str] = None
    variant_inventory_management: Optional[str] = None
    product_exists: bool = True
    taxable_discrepancy: Optional[str] = None
    tax_lines: Optional[List[Dict[str, Any]]] = None
    discount_allocations: Optional[List[Dict[str, Any]]] = None
    duties: Optional[List[Dict[str, Any]]] = None
    admin_graphql_api_id: Optional[str] = None
    name: Optional[str] = None
    properties: Optional[List[Dict[str, Any]]] = None

    @property
    def price_money(self) -> Money:
        """Get price as Money object."""
        return Money(amount=Decimal(self.price), currency_code="USD")

    @property
    def total_discount_money(self) -> Money:
        """Get total discount as Money object."""
        return Money(amount=Decimal(self.total_discount), currency_code="USD")


class Order(BaseModel):
    """Order information."""
    id: int
    order_number: int
    email: Optional[str] = None
    phone: Optional[str] = None
    financial_status: str  # pending, authorized, partially_paid, paid, partially_refunded, refunded, voided
    fulfillment_status: Optional[str] = None  # fulfilled, null, partially_fulfilled, restocked
    currency: str = "USD"
    presentment_currency: Optional[str] = None
    total_price: str  # Keep as string to match Shopify API
    subtotal_price: str
    total_tax: str = "0.00"
    total_shipping_price: str = "0.00"
    total_discounts: str = "0.00"
    current_total_price: str
    current_subtotal_price: str
    current_total_tax: str
    current_total_discounts: str
    line_items: List[LineItem] = []
    shipping_lines: List[ShippingLine] = []
    customer: Optional[Customer] = None
    shipping_address: Optional[CustomerAddress] = None
    billing_address: Optional[CustomerAddress] = None
    discount_codes: List[Dict[str, Any]] = []
    note: Optional[str] = None
    note_attributes: List[Dict[str, Any]] = []
    tags: str  # Shopify API returns tags as comma-separated string
    confirmed: bool = False
    test: bool = False
    total_line_items_price: str
    total_weight: Optional[int] = None
    taxes_included: bool = False
    currency_exchange_adjustment: Optional[Dict[str, Any]] = None
    total_tax_set: Optional[MoneySet] = None
    subtotal_price_set: Optional[MoneySet] = None
    total_shipping_price_set: Optional[MoneySet] = None
    total_price_set: Optional[MoneySet] = None
    total_discounts_set: Optional[MoneySet] = None
    current_total_price_set: Optional[MoneySet] = None
    current_subtotal_price_set: Optional[MoneySet] = None
    current_total_tax_set: Optional[MoneySet] = None
    current_total_discounts_set: Optional[MoneySet] = None
    total_line_items_price_set: Optional[MoneySet] = None
    tax_lines: List[Dict[str, Any]] = []
    discount_applications: List[Dict[str, Any]] = []
    created_at: datetime
    updated_at: datetime
    processed_at: Optional[datetime] = None
    cancelled_at: Optional[datetime] = None
    cancel_reason: Optional[str] = None
    closed_at: Optional[datetime] = None
    token: str
    cart_token: Optional[str] = None
    checkout_token: Optional[str] = None
    checkout_id: Optional[int] = None
    reference: Optional[str] = None
    source_identifier: Optional[str] = None
    source_name: str  # web, pos, etc.
    source_url: Optional[str] = None
    device_id: Optional[str] = None
    landing_site: Optional[str] = None
    landing_site_ref: Optional[str] = None
    referring_site: Optional[str] = None
    order_status_url: Optional[str] = None
    financial_status_labels: List[str] = []
    fulfillment_status_labels: List[str] = []
    buyer_accepts_marketing: bool = False
    cancel_reason: Optional[str] = None
    checkout_email: Optional[str] = None
    location_id: Optional[int] = None
    payment_gateway_names: List[str] = []
    processing_method: Optional[str] = None
    reservation_time_left: Optional[int] = None
    reservation_time: Optional[datetime] = None
    source: Optional[str] = None
    checkout_payment_collection_url: Optional[str] = None
    admin_graphql_api_id: Optional[str] = None
    name: str
    contact_email: Optional[str] = None

    @property
    def total_price_money(self) -> Money:
        """Get total price as Money object."""
        return Money(amount=Decimal(self.total_price), currency_code=self.currency)

    @property
    def subtotal_price_money(self) -> Money:
        """Get subtotal price as Money object."""
        return Money(amount=Decimal(self.subtotal_price), currency_code=self.currency)

    @property
    def total_tax_money(self) -> Money:
        """Get total tax as Money object."""
        return Money(amount=Decimal(self.total_tax), currency_code=self.currency)

    @property
    def total_shipping_price_money(self) -> Money:
        """Get total shipping price as Money object."""
        return Money(amount=Decimal(self.total_shipping_price), currency_code=self.currency)

    @property
    def total_discounts_money(self) -> Money:
        """Get total discounts as Money object."""
        return Money(amount=Decimal(self.total_discounts), currency_code=self.currency)

    @property
    def tag_list(self) -> List[str]:
        """Get tags as a list."""
        if not self.tags:
            return []
        return [tag.strip() for tag in self.tags.split(',') if tag.strip()]

    @property
    def is_paid(self) -> bool:
        """Check if order is paid."""
        return self.financial_status in ["PAID", "PARTIALLY_REFUNDED", "REFUNDED"]

    @property
    def is_fulfilled(self) -> bool:
        """Check if order is fulfilled."""
        return self.fulfillment_status == "FULFILLED"

    @property
    def is_cancelled(self) -> bool:
        """Check if order is cancelled."""
        return self.cancelled_at is not None


class Collection(BaseModel):
    """Product collection."""
    id: str  # GraphQL returns GIDs as strings
    handle: str
    title: str
    body_html: Optional[str] = None  # Changed from description_html to match Shopify API
    image: Optional[Dict[str, Any]] = None  # Shopify API returns collection images as dict
    published_at: Optional[datetime] = None
    updated_at: datetime
    sort_order: str = "manual"  # manual, alpha_asc, alpha_desc, best_selling, created, created_desc, price_asc, price_desc
    published_scope: str = "global"
    template_suffix: Optional[str] = None
    admin_graphql_api_id: Optional[str] = None

    @property
    def description(self) -> Optional[str]:
        """Get collection description (alias for body_html without HTML tags)."""
        return self.body_html

    @property
    def product_count(self) -> int:
        """Get the number of products in this collection."""
        # This would need to be populated from the API response
        return 0


class Shop(BaseModel):
    """Shop information."""
    id: int
    name: str
    domain: str
    email: str
    customer_email: Optional[str] = None
    currency: str = "USD"
    iana_timezone: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    shop_owner: Optional[str] = None
    money_format: Optional[str] = None
    money_with_currency_format: Optional[str] = None
    weight_unit: Optional[str] = None
    province: Optional[str] = None
    taxes_included: Optional[bool] = None
    auto_configure_tax_inclusivity: Optional[bool] = None
    tax_shipping: Optional[bool] = None
    county_taxes: Optional[bool] = None
    plan_display_name: Optional[str] = None
    plan_name: Optional[str] = None
    has_discounts: Optional[bool] = None
    has_gift_cards: Optional[bool] = None
    myshopify_domain: Optional[str] = None
    google_apps_domain: Optional[str] = None
    google_apps_login_enabled: Optional[bool] = None
    money_in_emails_format: Optional[str] = None
    money_with_currency_in_emails_format: Optional[str] = None
    eligible_for_payments: Optional[bool] = None
    requires_extra_payments_agreement: Optional[bool] = None
    password_enabled: Optional[bool] = None
    has_storefront: Optional[bool] = None
    eligible_for_card_reader_giveaway: Optional[bool] = None
    finances: Optional[bool] = None
    primary_location_id: Optional[int] = None
    checkout_api_supported: Optional[bool] = None
    multi_location_enabled: Optional[bool] = None
    setup_required: Optional[bool] = None
    pre_launch_enabled: Optional[bool] = None
    enabled_presentment_currencies: Optional[List[str]] = None
    transactional_sms_enabled: Optional[bool] = None
    marketing_sms_consent_enabled_at_checkout: Optional[bool] = None


class DiscountCode(BaseModel):
    """Discount code information."""
    id: int
    code: str
    amount: str
    type: str  # percentage, fixed_amount
    created_at: datetime


class TaxLine(BaseModel):
    """Tax line information."""
    price: str
    rate: float
    title: str


class Fulfillment(BaseModel):
    """Order fulfillment information."""
    id: int
    order_id: int
    status: str
    tracking_company: Optional[str] = None
    tracking_number: Optional[str] = None
    tracking_url: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class WebhookEvent(BaseModel):
    """Webhook event data."""
    id: str
    created_at: datetime
    topic: str
    shop_domain: str
    api_version: str
    payload: Dict[str, Any]


# ============================================================================
# POLICY MODELS
# ============================================================================

class ShopPolicy(BaseModel):
    """Base model for shop policies."""
    id: str
    title: str
    body: Optional[str] = None
    url: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    @property
    def content(self) -> str:
        """Get policy content."""
        return self.body or ""

    @property
    def is_active(self) -> bool:
        """Check if policy is active."""
        return self.body is not None and len(self.body.strip()) > 0


class PrivacyPolicy(ShopPolicy):
    """Privacy policy information."""
    pass


class RefundPolicy(ShopPolicy):
    """Refund policy information."""

    @property
    def refund_window_days(self) -> Optional[int]:
        """Extract refund window in days from policy content."""
        # This would use NLP to extract time periods from the policy text
        # For now, return None - can be enhanced with AI parsing
        return None

    @property
    def conditions_for_refund(self) -> List[str]:
        """Extract conditions for refund from policy content."""
        # This would use NLP to extract refund conditions
        # For now, return empty list - can be enhanced with AI parsing
        return []


class TermsOfService(ShopPolicy):
    """Terms of service information."""
    pass


class ShippingPolicy(ShopPolicy):
    """Shipping policy information."""

    @property
    def shipping_methods(self) -> List[str]:
        """Extract available shipping methods from policy content."""
        # This would use NLP to extract shipping methods
        # For now, return empty list - can be enhanced with AI parsing
        return []

    @property
    def delivery_timeframes(self) -> List[str]:
        """Extract delivery timeframes from policy content."""
        # This would use NLP to extract delivery timeframes
        # For now, return empty list - can be enhanced with AI parsing
        return []


class SubscriptionPolicy(ShopPolicy):
    """Subscription policy information."""
    pass


class LegalNoticePolicy(ShopPolicy):
    """Legal notice policy information."""
    pass


class ShopPolicies(BaseModel):
    """Container for all shop policies."""
    privacy_policy: Optional[PrivacyPolicy] = None
    refund_policy: Optional[RefundPolicy] = None
    terms_of_service: Optional[TermsOfService] = None
    shipping_policy: Optional[ShippingPolicy] = None
    subscription_policy: Optional[SubscriptionPolicy] = None
    legal_notice_policy: Optional[LegalNoticePolicy] = None

    @property
    def active_policies(self) -> Dict[str, ShopPolicy]:
        """Get all active policies."""
        policies = {}
        for name, policy in [
            ("privacy_policy", self.privacy_policy),
            ("refund_policy", self.refund_policy),
            ("terms_of_service", self.terms_of_service),
            ("shipping_policy", self.shipping_policy),
            ("subscription_policy", self.subscription_policy),
            ("legal_notice_policy", self.legal_notice_policy),
        ]:
            if policy and policy.is_active:
                policies[name] = policy
        return policies

    @property
    def policy_count(self) -> int:
        """Get count of active policies."""
        return len(self.active_policies)


class PolicyQuery(BaseModel):
    """Policy query request model."""
    query_type: str  # privacy, refund, shipping, terms, subscription, legal, all
    customer_context: Optional[Dict[str, Any]] = None
    order_context: Optional[Dict[str, Any]] = None
    product_context: Optional[Dict[str, Any]] = None
    specific_question: Optional[str] = None


class PolicyResponse(BaseModel):
    """Policy query response model."""
    policy_type: str
    policy_content: str
    relevant_sections: List[str] = []
    answer_to_question: Optional[str] = None
    confidence_score: Optional[float] = None
    additional_info: Optional[Dict[str, Any]] = None


class PolicySummary(BaseModel):
    """Policy summary for quick reference."""
    policy_type: str
    title: str
    key_points: List[str] = []
    important_dates: Optional[str] = None
    contact_info: Optional[str] = None
    last_updated: Optional[datetime] = None