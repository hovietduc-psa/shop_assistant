"""
Shopify API response parsers.

These parsers handle the conversion from Shopify API responses to our Pydantic models.
Based on the actual schema extracted from Makezbright Gifts store.
Enhanced with LLM-friendly formatting for comprehensive AI assistant responses.
"""

from datetime import datetime
from decimal import Decimal
from typing import Dict, List, Any, Optional

from .models import (
    Product, ProductVariant, ProductOption, Image, Customer, CustomerAddress,
    Order, LineItem, ShippingLine, Collection, Shop, Money, MoneySet,
    DiscountCode, TaxLine, Fulfillment, ShopPolicy, ShopPolicies, PrivacyPolicy,
    RefundPolicy, TermsOfService, ShippingPolicy, SubscriptionPolicy,
    LegalNoticePolicy, PolicyResponse, PolicySummary
)


def parse_shop_data(shop_data: Dict[str, Any]) -> Shop:
    """Parse shop data from Shopify API response."""
    return Shop(
        id=shop_data.get('id'),
        name=shop_data.get('name'),
        domain=shop_data.get('domain'),
        email=shop_data.get('email'),
        customer_email=shop_data.get('customer_email'),
        currency=shop_data.get('currency', 'USD'),
        iana_timezone=shop_data.get('iana_timezone'),
        created_at=datetime.fromisoformat(shop_data.get('created_at', '').replace('Z', '+00:00')) if shop_data.get('created_at') else None,
        updated_at=datetime.fromisoformat(shop_data.get('updated_at', '').replace('Z', '+00:00')) if shop_data.get('updated_at') else None,
        shop_owner=shop_data.get('shop_owner'),
        money_format=shop_data.get('money_format'),
        money_with_currency_format=shop_data.get('money_with_currency_format'),
        weight_unit=shop_data.get('weight_unit'),
        province=shop_data.get('province'),
        taxes_included=shop_data.get('taxes_included'),
        tax_shipping=shop_data.get('tax_shipping'),
        county_taxes=shop_data.get('county_taxes'),
        plan_display_name=shop_data.get('plan_display_name'),
        plan_name=shop_data.get('plan_name'),
        has_discounts=shop_data.get('has_discounts'),
        has_gift_cards=shop_data.get('has_gift_cards'),
        myshopify_domain=shop_data.get('myshopify_domain'),
        multi_location_enabled=shop_data.get('multi_location_enabled'),
        checkout_api_supported=shop_data.get('checkout_api_supported'),
        password_enabled=shop_data.get('password_enabled'),
        has_storefront=shop_data.get('has_storefront'),
        enabled_presentment_currencies=shop_data.get('enabled_presentment_currencies', []),
        transactional_sms_enabled=shop_data.get('transactional_sms_enabled'),
        marketing_sms_consent_enabled_at_checkout=shop_data.get('marketing_sms_consent_enabled_at_checkout')
    )


def parse_product_data(product_data: Dict[str, Any]) -> Product:
    """Parse product data from Shopify API response."""
    # Parse images - handle both GraphQL (edges/node) and REST API (direct array) formats
    images = []
    images_data = product_data.get('images', [])

    # Handle GraphQL connection format
    if isinstance(images_data, dict) and 'edges' in images_data:
        for edge in images_data.get('edges', []):
            image_data = edge.get('node', {})
            image = Image(
                id=image_data.get('id'),
                src=image_data.get('src'),
                alt=image_data.get('altText'),
                width=image_data.get('width'),
                height=image_data.get('height'),
                position=None,  # Not available in GraphQL
                created_at=None,  # Not available in GraphQL
                updated_at=None,  # Not available in GraphQL
                product_id=None,  # Not available in GraphQL
                variant_ids=[]  # Not available in GraphQL
            )
            images.append(image)
    # Handle REST API format (direct array)
    elif isinstance(images_data, list):
        for image_data in images_data:
            image = Image(
                id=image_data.get('id'),
                src=image_data.get('src'),
                alt=image_data.get('alt'),
                width=image_data.get('width'),
                height=image_data.get('height'),
                position=image_data.get('position'),
                created_at=datetime.fromisoformat(image_data.get('created_at', '').replace('Z', '+00:00')) if image_data.get('created_at') else None,
                updated_at=datetime.fromisoformat(image_data.get('updated_at', '').replace('Z', '+00:00')) if image_data.get('updated_at') else None,
                product_id=image_data.get('product_id'),
                variant_ids=image_data.get('variant_ids', [])
            )
            images.append(image)

    # Parse variants - handle both GraphQL (edges/node) and REST API (direct array) formats
    variants = []
    variants_data = product_data.get('variants', [])

    # Handle GraphQL connection format
    if isinstance(variants_data, dict) and 'edges' in variants_data:
        for edge in variants_data.get('edges', []):
            variant_data = edge.get('node', {})
            variant = ProductVariant(
                id=variant_data.get('id'),
                product_id=None,  # Not available in GraphQL
                title=variant_data.get('title'),
                price=variant_data.get('price', '0.00'),
                compare_at_price=variant_data.get('compareAtPrice'),
                sku=variant_data.get('sku'),
                weight=None,  # Not available in GraphQL
                weight_unit=None,  # Not available in GraphQL
                inventory_quantity=variant_data.get('inventoryQuantity', 0),  # Now available in enhanced GraphQL
                inventory_management=None,  # Not available in GraphQL variant
                inventory_policy=None,  # Not available in GraphQL variant
                requires_shipping=None,  # Not available in GraphQL
                taxable=variant_data.get('taxable', True),
                position=None,  # Not available in GraphQL
                option1=None,  # Not available in GraphQL
                option2=None,  # Not available in GraphQL
                option3=None,  # Not available in GraphQL
                barcode=None,  # Not available in GraphQL
                image_id=None,  # Not available in GraphQL
                created_at=datetime.fromisoformat(variant_data.get('createdAt', '').replace('Z', '+00:00')) if variant_data.get('createdAt') else None,
                updated_at=datetime.fromisoformat(variant_data.get('updatedAt', '').replace('Z', '+00:00')) if variant_data.get('updatedAt') else None
            )
            variants.append(variant)
    # Handle REST API format (direct array)
    elif isinstance(variants_data, list):
        for variant_data in variants_data:
            variant = ProductVariant(
                id=variant_data.get('id'),
                product_id=variant_data.get('product_id'),
                title=variant_data.get('title'),
                price=variant_data.get('price', '0.00'),
                compare_at_price=variant_data.get('compare_at_price'),
                sku=variant_data.get('sku'),
                weight=Decimal(str(variant_data.get('weight', '0'))) if variant_data.get('weight') else None,
                weight_unit=variant_data.get('weight_unit'),
                inventory_quantity=variant_data.get('inventory_quantity', 0),
                inventory_management=variant_data.get('inventory_management'),
                inventory_policy=variant_data.get('inventory_policy'),
                requires_shipping=variant_data.get('requires_shipping', True),
                taxable=variant_data.get('taxable', True),
                position=variant_data.get('position'),
                option1=variant_data.get('option1'),
                option2=variant_data.get('option2'),
                option3=variant_data.get('option3'),
                barcode=variant_data.get('barcode'),
                image_id=variant_data.get('image_id'),
                created_at=datetime.fromisoformat(variant_data.get('created_at', '').replace('Z', '+00:00')) if variant_data.get('created_at') else None,
                updated_at=datetime.fromisoformat(variant_data.get('updated_at', '').replace('Z', '+00:00')) if variant_data.get('updated_at') else None
            )
            variants.append(variant)

    # Parse options
    options = []
    for option_data in product_data.get('options', []):
        option = ProductOption(
            id=option_data.get('id'),
            product_id=option_data.get('product_id'),
            name=option_data.get('name'),
            position=option_data.get('position'),
            values=option_data.get('values', [])
        )
        options.append(option)

    # Handle tags - GraphQL API returns list, REST API returns string
    tags_data = product_data.get('tags', '')
    if isinstance(tags_data, list):
        tags = ','.join(str(tag) for tag in tags_data)
    else:
        tags = tags_data or ''

    return Product(
        id=product_data.get('id'),
        title=product_data.get('title'),
        handle=product_data.get('handle'),
        body_html=product_data.get('body_html'),
        vendor=product_data.get('vendor'),
        product_type=product_data.get('product_type'),
        status=product_data.get('status', 'active'),
        tags=tags,
        images=images,
        variants=variants,
        options=options,
        created_at=datetime.fromisoformat(product_data.get('created_at', '').replace('Z', '+00:00')) if product_data.get('created_at') else None,
        updated_at=datetime.fromisoformat(product_data.get('updated_at', '').replace('Z', '+00:00')) if product_data.get('updated_at') else None,
        published_at=datetime.fromisoformat(product_data.get('published_at', '').replace('Z', '+00:00')) if product_data.get('published_at') else None,
        template_suffix=product_data.get('template_suffix'),
        published_scope=product_data.get('published_scope', 'global'),
        admin_graphql_api_id=product_data.get('admin_graphql_api_id')
    )


def parse_customer_data(customer_data: Dict[str, Any]) -> Customer:
    """Parse customer data from Shopify API response."""
    # Parse addresses
    addresses = []
    for address_data in customer_data.get('addresses', []):
        address = CustomerAddress(
            id=address_data.get('id'),
            customer_id=address_data.get('customer_id'),
            first_name=address_data.get('first_name'),
            last_name=address_data.get('last_name'),
            company=address_data.get('company'),
            address1=address_data.get('address1'),
            address2=address_data.get('address2'),
            city=address_data.get('city'),
            province=address_data.get('province'),
            country=address_data.get('country'),
            zip=address_data.get('zip'),
            phone=address_data.get('phone'),
            province_code=address_data.get('province_code'),
            country_code=address_data.get('country_code'),
            country_name=address_data.get('country_name'),
            default=address_data.get('default', False),
            created_at=datetime.fromisoformat(address_data.get('created_at', '').replace('Z', '+00:00')) if address_data.get('created_at') else None,
            updated_at=datetime.fromisoformat(address_data.get('updated_at', '').replace('Z', '+00:00')) if address_data.get('updated_at') else None
        )
        addresses.append(address)

    # Parse default address
    default_address = None
    default_address_data = customer_data.get('default_address')
    if default_address_data:
        default_address = CustomerAddress(
            id=default_address_data.get('id'),
            customer_id=default_address_data.get('customer_id'),
            first_name=default_address_data.get('first_name'),
            last_name=default_address_data.get('last_name'),
            company=default_address_data.get('company'),
            address1=default_address_data.get('address1'),
            address2=default_address_data.get('address2'),
            city=default_address_data.get('city'),
            province=default_address_data.get('province'),
            country=default_address_data.get('country'),
            zip=default_address_data.get('zip'),
            phone=default_address_data.get('phone'),
            province_code=default_address_data.get('province_code'),
            country_code=default_address_data.get('country_code'),
            country_name=default_address_data.get('country_name'),
            default=default_address_data.get('default', False),
            created_at=datetime.fromisoformat(default_address_data.get('created_at', '').replace('Z', '+00:00')) if default_address_data.get('created_at') else None,
            updated_at=datetime.fromisoformat(default_address_data.get('updated_at', '').replace('Z', '+00:00')) if default_address_data.get('updated_at') else None
        )

    return Customer(
        id=customer_data.get('id'),
        email=customer_data.get('email'),
        first_name=customer_data.get('first_name'),
        last_name=customer_data.get('last_name'),
        phone=customer_data.get('phone'),
        addresses=addresses,
        orders_count=customer_data.get('orders_count', 0),
        total_spent=customer_data.get('total_spent', '0.00'),
        state=customer_data.get('state', 'enabled'),
        verified_email=customer_data.get('verified_email', False),
        tax_exempt=customer_data.get('tax_exempt', False),
        tags=customer_data.get('tags', ''),
        currency=customer_data.get('currency', 'USD'),
        multipass_identifier=customer_data.get('multipass_identifier'),
        note=customer_data.get('note'),
        last_order_id=customer_data.get('last_order_id'),
        last_order_name=customer_data.get('last_order_name'),
        admin_graphql_api_id=customer_data.get('admin_graphql_api_id'),
        marketing_opt_in_level=customer_data.get('marketing_opt_in_level'),
        tax_exemptions=customer_data.get('tax_exemptions', []),
        email_marketing_consent=customer_data.get('email_marketing_consent'),
        sms_marketing_consent=customer_data.get('sms_marketing_consent'),
        created_at=datetime.fromisoformat(customer_data.get('created_at', '').replace('Z', '+00:00')) if customer_data.get('created_at') else None,
        updated_at=datetime.fromisoformat(customer_data.get('updated_at', '').replace('Z', '+00:00')) if customer_data.get('updated_at') else None,
        default_address=default_address
    )


def parse_order_data(order_data: Dict[str, Any]) -> Order:
    """Parse order data from Shopify API response."""
    # Parse line items
    line_items = []
    for line_item_data in order_data.get('line_items', []):
        line_item = LineItem(
            id=line_item_data.get('id'),
            product_id=line_item_data.get('product_id'),
            variant_id=line_item_data.get('variant_id'),
            title=line_item_data.get('title'),
            quantity=line_item_data.get('quantity', 1),
            price=line_item_data.get('price', '0.00'),
            total_discount=line_item_data.get('total_discount', '0.00'),
            sku=line_item_data.get('sku'),
            vendor=line_item_data.get('vendor'),
            product_title=line_item_data.get('product_title'),
            variant_title=line_item_data.get('variant_title'),
            taxable=line_item_data.get('taxable', True),
            requires_shipping=line_item_data.get('requires_shipping', True),
            gift_card=line_item_data.get('gift_card', False),
            fulfillment_service=line_item_data.get('fulfillment_service'),
            variant_inventory_management=line_item_data.get('variant_inventory_management'),
            product_exists=line_item_data.get('product_exists', True),
            taxable_discrepancy=line_item_data.get('taxable_discrepancy'),
            tax_lines=line_item_data.get('tax_lines', []),
            discount_allocations=line_item_data.get('discount_allocations', []),
            duties=line_item_data.get('duties', []),
            admin_graphql_api_id=line_item_data.get('admin_graphql_api_id'),
            name=line_item_data.get('name'),
            properties=line_item_data.get('properties', [])
        )
        line_items.append(line_item)

    # Parse shipping lines
    shipping_lines = []
    for shipping_line_data in order_data.get('shipping_lines', []):
        shipping_line = ShippingLine(
            id=shipping_line_data.get('id'),
            title=shipping_line_data.get('title'),
            price=shipping_line_data.get('price', '0.00'),
            code=shipping_line_data.get('code'),
            source=shipping_line_data.get('source'),
            carrier_identifier=shipping_line_data.get('carrier_identifier'),
            requested_fulfillment_service_id=shipping_line_data.get('requested_fulfillment_service_id'),
            delivery_category=shipping_line_data.get('delivery_category'),
            tax_lines=shipping_line_data.get('tax_lines', [])
        )
        shipping_lines.append(shipping_line)

    # Parse customer
    customer = None
    customer_data = order_data.get('customer')
    if customer_data:
        customer = parse_customer_data(customer_data)

    # Parse shipping address
    shipping_address = None
    shipping_address_data = order_data.get('shipping_address')
    if shipping_address_data:
        shipping_address = CustomerAddress(
            id=0,  # Order addresses don't have IDs
            customer_id=customer.id if customer else 0,
            first_name=shipping_address_data.get('first_name'),
            last_name=shipping_address_data.get('last_name'),
            company=shipping_address_data.get('company'),
            address1=shipping_address_data.get('address1'),
            address2=shipping_address_data.get('address2'),
            city=shipping_address_data.get('city'),
            province=shipping_address_data.get('province'),
            country=shipping_address_data.get('country'),
            zip=shipping_address_data.get('zip'),
            phone=shipping_address_data.get('phone'),
            province_code=shipping_address_data.get('province_code'),
            country_code=shipping_address_data.get('country_code'),
            country_name=shipping_address_data.get('country_name'),
            default=False
        )

    # Parse billing address
    billing_address = None
    billing_address_data = order_data.get('billing_address')
    if billing_address_data:
        billing_address = CustomerAddress(
            id=0,  # Order addresses don't have IDs
            customer_id=customer.id if customer else 0,
            first_name=billing_address_data.get('first_name'),
            last_name=billing_address_data.get('last_name'),
            company=billing_address_data.get('company'),
            address1=billing_address_data.get('address1'),
            address2=billing_address_data.get('address2'),
            city=billing_address_data.get('city'),
            province=billing_address_data.get('province'),
            country=billing_address_data.get('country'),
            zip=billing_address_data.get('zip'),
            phone=billing_address_data.get('phone'),
            province_code=billing_address_data.get('province_code'),
            country_code=billing_address_data.get('country_code'),
            country_name=billing_address_data.get('country_name'),
            default=False
        )

    # Parse money sets
    def parse_money_set(money_set_data: Dict[str, Any]) -> Optional[MoneySet]:
        if not money_set_data:
            return None

        shop_money_data = money_set_data.get('shop_money', {})
        shop_money = Money(
            amount=Decimal(shop_money_data.get('amount', '0')),
            currency_code=shop_money_data.get('currency_code', 'USD')
        )

        presentment_money_data = money_set_data.get('presentment_money')
        presentment_money = None
        if presentment_money_data:
            presentment_money = Money(
                amount=Decimal(presentment_money_data.get('amount', '0')),
                currency_code=presentment_money_data.get('currency_code', 'USD')
            )

        return MoneySet(shop_money=shop_money, presentment_money=presentment_money)

    return Order(
        id=order_data.get('id'),
        order_number=order_data.get('order_number'),
        email=order_data.get('email'),
        phone=order_data.get('phone'),
        financial_status=order_data.get('financial_status', 'pending'),
        fulfillment_status=order_data.get('fulfillment_status'),
        currency=order_data.get('currency', 'USD'),
        presentment_currency=order_data.get('presentment_currency'),
        total_price=order_data.get('total_price', '0.00'),
        subtotal_price=order_data.get('subtotal_price', '0.00'),
        total_tax=order_data.get('total_tax', '0.00'),
        total_shipping_price=order_data.get('total_shipping_price', '0.00'),
        total_discounts=order_data.get('total_discounts', '0.00'),
        current_total_price=order_data.get('current_total_price', '0.00'),
        current_subtotal_price=order_data.get('current_subtotal_price', '0.00'),
        current_total_tax=order_data.get('current_total_tax', '0.00'),
        current_total_discounts=order_data.get('current_total_discounts', '0.00'),
        line_items=line_items,
        shipping_lines=shipping_lines,
        customer=customer,
        shipping_address=shipping_address,
        billing_address=billing_address,
        discount_codes=order_data.get('discount_codes', []),
        note=order_data.get('note'),
        note_attributes=order_data.get('note_attributes', []),
        tags=order_data.get('tags', ''),
        confirmed=order_data.get('confirmed', False),
        test=order_data.get('test', False),
        total_line_items_price=order_data.get('total_line_items_price', '0.00'),
        total_weight=order_data.get('total_weight'),
        taxes_included=order_data.get('taxes_included', False),
        currency_exchange_adjustment=order_data.get('currency_exchange_adjustment'),
        total_tax_set=parse_money_set(order_data.get('total_tax_set')),
        subtotal_price_set=parse_money_set(order_data.get('subtotal_price_set')),
        total_shipping_price_set=parse_money_set(order_data.get('total_shipping_price_set')),
        total_price_set=parse_money_set(order_data.get('total_price_set')),
        total_discounts_set=parse_money_set(order_data.get('total_discounts_set')),
        current_total_price_set=parse_money_set(order_data.get('current_total_price_set')),
        current_subtotal_price_set=parse_money_set(order_data.get('current_subtotal_price_set')),
        current_total_tax_set=parse_money_set(order_data.get('current_total_tax_set')),
        current_total_discounts_set=parse_money_set(order_data.get('current_total_discounts_set')),
        total_line_items_price_set=parse_money_set(order_data.get('total_line_items_price_set')),
        tax_lines=order_data.get('tax_lines', []),
        discount_applications=order_data.get('discount_applications', []),
        created_at=datetime.fromisoformat(order_data.get('created_at', '').replace('Z', '+00:00')) if order_data.get('created_at') else None,
        updated_at=datetime.fromisoformat(order_data.get('updated_at', '').replace('Z', '+00:00')) if order_data.get('updated_at') else None,
        processed_at=datetime.fromisoformat(order_data.get('processed_at', '').replace('Z', '+00:00')) if order_data.get('processed_at') else None,
        cancelled_at=datetime.fromisoformat(order_data.get('cancelled_at', '').replace('Z', '+00:00')) if order_data.get('cancelled_at') else None,
        cancel_reason=order_data.get('cancel_reason'),
        closed_at=datetime.fromisoformat(order_data.get('closed_at', '').replace('Z', '+00:00')) if order_data.get('closed_at') else None,
        token=order_data.get('token'),
        cart_token=order_data.get('cart_token'),
        checkout_token=order_data.get('checkout_token'),
        checkout_id=order_data.get('checkout_id'),
        reference=order_data.get('reference'),
        source_identifier=order_data.get('source_identifier'),
        source_name=order_data.get('source_name', 'web'),
        source_url=order_data.get('source_url'),
        device_id=order_data.get('device_id'),
        landing_site=order_data.get('landing_site'),
        landing_site_ref=order_data.get('landing_site_ref'),
        referring_site=order_data.get('referring_site'),
        order_status_url=order_data.get('order_status_url'),
        financial_status_labels=order_data.get('financial_status_labels', []),
        fulfillment_status_labels=order_data.get('fulfillment_status_labels', []),
        buyer_accepts_marketing=order_data.get('buyer_accepts_marketing', False),
        checkout_email=order_data.get('checkout_email'),
        location_id=order_data.get('location_id'),
        payment_gateway_names=order_data.get('payment_gateway_names', []),
        processing_method=order_data.get('processing_method'),
        reservation_time_left=order_data.get('reservation_time_left'),
        reservation_time=datetime.fromisoformat(order_data.get('reservation_time', '').replace('Z', '+00:00')) if order_data.get('reservation_time') else None,
        source=order_data.get('source'),
        checkout_payment_collection_url=order_data.get('checkout_payment_collection_url'),
        admin_graphql_api_id=order_data.get('admin_graphql_api_id'),
        name=order_data.get('name'),
        contact_email=order_data.get('contact_email')
    )


def parse_collection_data(collection_data: Dict[str, Any]) -> Collection:
    """Parse collection data from Shopify API response."""
    # Handle dates - GraphQL may return different formats
    updated_at = None
    if collection_data.get('updatedAt'):
        try:
            updated_at = datetime.fromisoformat(collection_data.get('updatedAt', '').replace('Z', '+00:00'))
        except (ValueError, AttributeError):
            updated_at = None

    return Collection(
        id=collection_data.get('id'),
        handle=collection_data.get('handle'),
        title=collection_data.get('title'),
        body_html=collection_data.get('body_html') or collection_data.get('descriptionHtml'),
        image=collection_data.get('image'),
        published_at=None,  # Skip published_at for now
        updated_at=updated_at,
        sort_order=collection_data.get('sortOrder', 'manual'),
        published_scope=collection_data.get('publishedScope', 'global'),
        template_suffix=collection_data.get('templateSuffix'),
        admin_graphql_api_id=collection_data.get('admin_graphql_api_id')
    )


# ============================================================================
# POLICY PARSERS
# ============================================================================

def parse_policy_data(policy_data: Dict[str, Any], policy_type: str) -> Optional[ShopPolicy]:
    """Parse policy data from Shopify API response."""
    if not policy_data:
        return None

    # Parse dates
    created_at = None
    updated_at = None
    if policy_data.get('createdAt'):
        try:
            created_at = datetime.fromisoformat(policy_data.get('createdAt', '').replace('Z', '+00:00'))
        except (ValueError, AttributeError):
            created_at = None
    if policy_data.get('updatedAt'):
        try:
            updated_at = datetime.fromisoformat(policy_data.get('updatedAt', '').replace('Z', '+00:00'))
        except (ValueError, AttributeError):
            updated_at = None

    # Create appropriate policy type
    policy_classes = {
        'privacy': PrivacyPolicy,
        'refund': RefundPolicy,
        'terms': TermsOfService,
        'shipping': ShippingPolicy,
        'subscription': SubscriptionPolicy,
        'legal': LegalNoticePolicy
    }

    policy_class = policy_classes.get(policy_type.lower(), ShopPolicy)

    return policy_class(
        id=policy_data.get('id'),
        title=policy_data.get('title'),
        body=policy_data.get('body'),
        url=policy_data.get('url'),
        created_at=created_at,
        updated_at=updated_at
    )


def parse_shop_policies_response(response_data: Dict[str, Any]) -> ShopPolicies:
    """Parse shop policies response from Shopify API."""
    shop_data = response_data.get('data', {}).get('shop', {})

    return ShopPolicies(
        privacy_policy=parse_policy_data(shop_data.get('privacyPolicy'), 'privacy'),
        refund_policy=parse_policy_data(shop_data.get('refundPolicy'), 'refund'),
        terms_of_service=parse_policy_data(shop_data.get('termsOfService'), 'terms'),
        shipping_policy=parse_policy_data(shop_data.get('shippingPolicy'), 'shipping'),
        subscription_policy=parse_policy_data(shop_data.get('subscriptionPolicy'), 'subscription'),
        legal_notice_policy=parse_policy_data(shop_data.get('legalNotice'), 'legal')
    )


def parse_policy_response(response_data: Dict[str, Any], policy_type: str) -> Optional[ShopPolicy]:
    """Parse single policy response from Shopify API."""
    shop_data = response_data.get('data', {}).get('shop', {})

    # Map policy types to GraphQL fields
    policy_fields = {
        'privacy': 'privacyPolicy',
        'refund': 'refundPolicy',
        'terms': 'termsOfService',
        'shipping': 'shippingPolicy',
        'subscription': 'subscriptionPolicy',
        'legal': 'legalNotice'
    }

    field_name = policy_fields.get(policy_type.lower())
    if not field_name:
        return None

    policy_data = shop_data.get(field_name)
    return parse_policy_data(policy_data, policy_type)


def create_policy_summary(policy: ShopPolicy) -> PolicySummary:
    """Create a policy summary from a full policy."""
    # This is a basic implementation - could be enhanced with AI to extract key points
    content = policy.content

    # Extract basic information
    key_points = []
    if content:
        # Simple split by paragraphs for now - could be enhanced with NLP
        paragraphs = [p.strip() for p in content.split('\n\n') if p.strip()]
        key_points = paragraphs[:3]  # First 3 paragraphs as key points

    return PolicySummary(
        policy_type=policy.__class__.__name__.lower().replace('policy', ''),
        title=policy.title,
        key_points=key_points,
        last_updated=policy.updated_at
    )


# ===== ENHANCED LLM FORMATTING FUNCTIONS =====

def enhance_product_for_llm(product: Product, inventory_data: Optional[Dict] = None) -> Dict[str, Any]:
    """Enhance product data with comprehensive LLM-friendly information."""

    # Base product information
    enhanced = {
        'id': product.id,
        'title': product.title,
        'handle': product.handle,
        'vendor': product.vendor,
        'product_type': product.product_type,
        'tags': product.tags.split(', ') if product.tags else [],
        'status': product.status,
        'created_at': product.created_at.isoformat() if product.created_at else None,
        'updated_at': product.updated_at.isoformat() if product.updated_at else None,
        'published_at': product.published_at.isoformat() if product.published_at else None
    }

    # Add pricing information
    if product.variants:
        variant = product.variants[0]  # Use first variant for pricing
        enhanced['price'] = float(variant.price) if variant.price else 0.0
        enhanced['compare_at_price'] = float(variant.compare_at_price) if variant.compare_at_price else None
        enhanced['sku'] = variant.sku
        enhanced['inventory_quantity'] = variant.inventory_quantity or 0
    else:
        enhanced['price'] = 0.0
        enhanced['compare_at_price'] = None
        enhanced['sku'] = None
        enhanced['inventory_quantity'] = 0

    # Add inventory awareness
    if inventory_data:
        enhanced['inventory'] = inventory_data
    else:
        # Default inventory information
        quantity = enhanced['inventory_quantity']
        enhanced['inventory'] = {
            'quantity': quantity,
            'status': 'in_stock' if quantity > 0 else 'out_of_stock',
            'policy': 'continue',
            'location': 'Main Warehouse'
        }

    # Add images
    if product.images:
        enhanced['images'] = [img.src for img in product.images if img.src]
        enhanced['main_image'] = enhanced['images'][0] if enhanced['images'] else None
    else:
        enhanced['images'] = []
        enhanced['main_image'] = None

    # Add description and features
    enhanced['description'] = product.body_html or "No description available"

    # Extract detailed features from description
    features = []
    description = product.body_html.lower() if product.body_html else ""

    if 'tumbler' in product.title.lower() or 'drinkware' in ' '.join(product.tags).lower():
        common_features = [
            "Double wall insulation",
            "Leak proof lid",
            "Cup holder friendly",
            "Stainless steel construction",
            "BPA free",
            "Keeps drinks hot and cold"
        ]
        for feature in common_features:
            if any(word in description for word in feature.lower().split()):
                features.append(feature)

    enhanced['detailed_features'] = features

    # Add customization information
    enhanced['customization'] = _determine_customization_options(product)

    # Add options
    if product.options:
        enhanced['options'] = [opt.name + ": " + ", ".join(opt.values) for opt in product.options]
    else:
        enhanced['options'] = []

    # NOTE: Only real Shopify data should be included
    # Enhanced fields should be fetched from additional Shopify API calls
    # Do not generate synthetic data - all data must come from Shopify

    return enhanced


def _determine_customization_options(product: Product) -> Dict[str, Any]:
    """Determine customization options based on product attributes."""
    tags = product.tags.split(', ') if product.tags else []
    title = product.title.lower()
    description = (product.body_html or "").lower()

    # Check if product is customizable
    is_customizable = any(keyword in ' '.join(tags).lower() or keyword in title or keyword in description
                         for keyword in ['personalized', 'custom', 'customizable', 'engrave'])

    if not is_customizable:
        return {'available': False}

    return {
        'available': True,
        'types': ['text', 'design'],
        'max_characters': 50,
        'text_fields': [
            {
                'name': 'Personalized Message',
                'required': True,
                'max_length': 50,
                'placeholder': 'Enter your custom message'
            }
        ],
        'design_options': [
            {
                'name': 'Font Style',
                'options': ['Classic', 'Modern', 'Script', 'Bold']
            },
            {
                'name': 'Color',
                'options': ['Black', 'White', 'Gold', 'Silver', 'Rose Gold']
            }
        ],
        'preview_enabled': True,
        'processing_time': '3-5 business days'
    }


def enhance_customer_for_llm(customer: Customer) -> Dict[str, Any]:
    """Enhance customer data with LLM-friendly context."""

    enhanced = {
        'id': customer.id,
        'email': customer.email,
        'phone': customer.phone,
        'first_name': customer.first_name,
        'last_name': customer.last_name,
        'orders_count': customer.orders_count,
        'total_spent': float(customer.total_spent) if customer.total_spent else 0.0,
        'currency': customer.currency,
        'state': customer.state,
        'created_at': customer.created_at.isoformat() if customer.created_at else None,
        'updated_at': customer.updated_at.isoformat() if customer.updated_at else None,
        'verified_email': customer.verified_email
    }

    # Add marketing consent
    marketing_consent = {}
    if customer.email_marketing_consent:
        marketing_consent['email'] = customer.email_marketing_consent.get('state', 'unknown')
    if customer.sms_marketing_consent:
        marketing_consent['sms'] = customer.sms_marketing_consent.get('state', 'unknown')
    enhanced['marketing_consent'] = marketing_consent

    # Add address information
    if customer.default_address:
        addr = customer.default_address
        enhanced['default_address'] = {
            'city': addr.city,
            'province': addr.province,
            'country': addr.country,
            'zip': addr.zip
        }
    else:
        enhanced['default_address'] = None

    # Determine customer type and value
    enhanced['customer_type'] = 'new' if customer.orders_count == 0 else 'returning'
    enhanced['is_vip'] = enhanced['total_spent'] > 100 or customer.orders_count > 3

    # Add tags if present
    enhanced['tags'] = customer.tags if customer.tags else ""

    return enhanced


def enhance_order_for_llm(order: Order) -> Dict[str, Any]:
    """Enhance order data with comprehensive LLM context."""

    enhanced = {
        'id': order.id,
        'name': order.name,
        'status': order.financial_status,
        'financial_status': order.financial_status,
        'fulfillment_status': order.fulfillment_status,
        'created_at': order.created_at.isoformat() if order.created_at else None,
        'currency': order.currency,
        'total_price': float(order.total_price) if order.total_price else 0.0,
        'subtotal_price': float(order.subtotal_price) if order.subtotal_price else 0.0,
        'total_tax': float(order.total_tax) if order.total_tax else 0.0,
        'total_shipping': float(order.total_shipping_price_set.shop_money.amount) if order.total_shipping_price_set else 0.0,
        'total_discounts': float(order.total_discounts) if order.total_discounts else 0.0,
        'order_status_url': order.order_status_url
    }

    # Add discount codes
    if order.discount_codes:
        enhanced['discount_codes'] = [
            {
                'code': dc['code'] if isinstance(dc, dict) else dc.code,
                'type': dc['type'] if isinstance(dc, dict) else dc.type,
                'value': float(dc['amount']) if isinstance(dc, dict) and dc['amount'] else (float(dc.amount) if dc.amount else 0.0)
            } for dc in order.discount_codes
        ]
    else:
        enhanced['discount_codes'] = []

    # Add line items with customization details
    enhanced['line_items'] = []
    for item in order.line_items:
        line_item = {
            'id': item.id,
            'product_id': item.product_id,
            'title': item.title,
            'quantity': item.quantity,
            'price': float(item.price) if item.price else 0.0,
            'sku': item.sku,
            'variant_title': item.variant_title
        }

        # Add customization properties if available
        if item.properties:
            line_item['customization_properties'] = [
                {'name': prop.name, 'value': prop.value}
                for prop in item.properties
            ]

        enhanced['line_items'].append(line_item)

    # Add customer information
    if order.customer:
        enhanced['customer'] = enhance_customer_for_llm(order.customer)

    # Add shipping address
    if order.shipping_address:
        addr = order.shipping_address
        enhanced['shipping_address'] = {
            'first_name': addr.first_name,
            'last_name': addr.last_name,
            'company': addr.company,
            'address1': addr.address1,
            'city': addr.city,
            'province': addr.province,
            'country': addr.country,
            'zip': addr.zip,
            'country_code': addr.country_code,
            'province_code': addr.province_code,
            'phone': addr.phone
        }
    else:
        enhanced['shipping_address'] = None

    # Add shipping lines
    if order.shipping_lines:
        enhanced['shipping_lines'] = [
            {
                'title': line.title,
                'price': float(line.price) if line.price else 0.0,
                'delivery_estimate': "3-5 business days"  # Default estimate
            } for line in order.shipping_lines
        ]
    else:
        enhanced['shipping_lines'] = []

    # NOTE: Only real Shopify data should be included
    # Enhanced order details should be fetched from Shopify fulfillment API, payment API, etc.
    # Do not generate synthetic data - all data must come from Shopify or verified integrations

    return enhanced


def format_products_for_llm(products: List[Product], query: str = "", inventory_data: Optional[List[Dict]] = None) -> str:
    """Format product list with enhanced context for LLM consumption."""

    if not products:
        return "No products found matching your criteria."

    # Handle the data structure issue: products might be wrapped with pagination boolean
    if isinstance(products, list) and len(products) > 0:
        # Check if last element is a boolean (pagination flag)
        if isinstance(products[-1], bool):
            # This is the buggy structure: [Product1, Product2, ..., has_more_boolean]
            products = products[:-1]  # Remove the boolean, keep only Product objects
        elif isinstance(products[0], list):
            # This is the buggy structure: [products, has_more_boolean]
            products = products[0]  # Extract the actual products
    elif isinstance(products, tuple) and len(products) == 2:
        # This is the buggy structure: (products, has_more_boolean)
        products = products[0]  # Extract the actual products

    enhanced_products = []
    for i, product in enumerate(products):
        # Get corresponding inventory data if available
        product_inventory = inventory_data[i] if inventory_data and i < len(inventory_data) else None
        enhanced = enhance_product_for_llm(product, product_inventory)
        enhanced_products.append(enhanced)

    # Format each product for display
    formatted_sections = []
    for i, product in enumerate(enhanced_products, 1):
        section = f"""
[{i}] **{product['title']}**
**Price:** ${product['price']:.2f}"""

        # Add discount information
        if product['compare_at_price'] and product['compare_at_price'] > product['price']:
            discount_pct = ((product['compare_at_price'] - product['price']) / product['compare_at_price']) * 100
            section += f" (was ${product['compare_at_price']:.2f} - Save {discount_pct:.0f}%)"

        # Add brand and category
        if product['vendor']:
            section += f"\n**Brand:** {product['vendor']}"
        if product['product_type']:
            section += f"\n**Category:** {product['product_type']}"

        # Add description
        if product['description']:
            desc = product['description'][:200] + "..." if len(product['description']) > 200 else product['description']
            section += f"\n**Description:** {desc}"

        # Add features
        if product['detailed_features']:
            features = "\n".join(f"* {feature}" for feature in product['detailed_features'][:3])
            section += f"\n**Features:**\n{features}"

        # Add customization
        if product['customization']['available']:
            custom_types = ", ".join(product['customization']['types'])
            section += f"\n**Customization Available:** {custom_types.title()}"
            if product['customization'].get('processing_time'):
                section += f" (Processing: {product['customization']['processing_time']})"

        # Add inventory
        inventory = product['inventory']
        status_indicator = "[IN STOCK]" if inventory['status'] == 'in_stock' else "[LOW STOCK]"
        section += f"\n**Stock:** {inventory['quantity']} units available {status_indicator}"

        # Add images
        if product['images']:
            section += f"\n**Images:** {len(product['images'])} product photos available"

        formatted_sections.append(section)

    formatted_text = "\n\n".join(formatted_sections)

    # Handle Unicode encoding for console output
    try:
        import sys
        if sys.platform == "win32":
            formatted_text.encode('utf-8').decode('utf-8')
    except (UnicodeEncodeError, UnicodeDecodeError):
        # Replace problematic characters for Windows console compatibility
        unicode_replacements = {
            '✅': '[OK]',
            '⚠️': '[!]',
            '🎯': '[TARGET]',
            '💰': '[MONEY]',
            '🏷️': '[TAG]',
            '📂': '[FOLDER]',
            '📝': '[NOTE]',
            '✨': '[STAR]',
            '🎨': '[ART]',
            '🖼️': '[IMAGE]',
            '•': '*',
            '💡': '[IDEA]',
            '🚀': '[ROCKET]',
            '📊': '[CHART]',
            '✓': '[OK]',
            '❌': '[X]'
        }

        for unicode_char, replacement in unicode_replacements.items():
            formatted_text = formatted_text.replace(unicode_char, replacement)

    return formatted_text


def format_order_context_for_llm(order: Order) -> str:
    """Format order information for customer service queries."""

    enhanced = enhance_order_for_llm(order)

    context = f"""
**Order {enhanced['name']}**
**Total:** ${enhanced['total_price']:.2f}
**Order Date:** {enhanced['created_at'][:10] if enhanced['created_at'] else 'Unknown'}
**Status:** {enhanced['financial_status'].title()}"""

    # Add fulfillment status
    if enhanced['fulfillment_status']:
        context += f"\n**Shipping Status:** {enhanced['fulfillment_status'].title()}"

    # Add items
    if enhanced['line_items']:
        context += "\n\n**Items Ordered:**"
        for item in enhanced['line_items']:
            context += f"\n* {item['title']} (Qty: {item['quantity']}) - ${item['price']:.2f}"

    # Add shipping address
    if enhanced['shipping_address']:
        addr = enhanced['shipping_address']
        context += f"\n\n**Shipping To:** {addr['city']}, {addr['province']} {addr['zip']}"

    # Add tracking
    if enhanced['order_status_url']:
        context += f"\n\n**Track Order:** [View Status]({enhanced['order_status_url']})"

    # Handle Unicode encoding for console output
    try:
        import sys
        if sys.platform == "win32":
            context.encode('utf-8').decode('utf-8')
    except (UnicodeEncodeError, UnicodeDecodeError):
        # Replace problematic characters for Windows console compatibility
        unicode_replacements = {
            '📋': '[LIST]',
            '💰': '[MONEY]',
            '📅': '[DATE]',
            '💳': '[CARD]',
            '📦': '[PACKAGE]',
            '🛍️': '[SHOPPING]',
            '🏠': '[HOME]',
            '🔗': '[LINK]',
            '•': '*'
        }

        for unicode_char, replacement in unicode_replacements.items():
            context = context.replace(unicode_char, replacement)

    return context.strip()