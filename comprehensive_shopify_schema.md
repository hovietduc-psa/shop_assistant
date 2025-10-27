# Comprehensive Shopify Store Schema Documentation

**Generated on:** 2025-10-24T17:05:48.901676
**Store:** Makezbright Gifts
**Domain:** makezbrightgifts.com
**Extraction Method:** direct_api_calls

## Store Information

| Property | Value |
|----------|-------|
| Store Name | Makezbright Gifts |
| Domain | makezbrightgifts.com |
| Store ID | 28003598418 |
| Currency | USD |
| Timezone | America/Los_Angeles |
| Created At | 2020-04-10T03:54:19-07:00 |
| Plan | Shopify Plus |
| Email | contact@makezbright.com |
| Country | VN |
| City | ho chi minh |
| Phone | 0979044325 |
| Has Discounts | Yes |
| Has Gift Cards | No |
| Multi-Location Enabled | Yes |
| Customer Accounts | Unknown |

## Schema Overview

- **Total Entities:** 5
- **Total Relationships:** 7
- **Extraction Method:** direct_api_calls

## Entity Details

### Product

**Description:** Products sold in the store
**Sample Count:** 5

**Fields:**

| Field Name | Data Type | Usage % | Always Present | Nullable | Sample Values |
|------------|-----------|---------|---------------|----------|---------------|
| body_html | datetime | 100.0% | Yes | No | <div>
    
    <ul>
        <li>Say goodbye to luk, <div>
    
    <ul>
        <li>
<b>DRINKS STAY HO |
| options | array | 100.0% | Yes | No | [{'id': 9299235209298, 'product_id': 7153939284050, [{'id': 9299604471890, 'product_id': 7154246975570 |
| variants | array | 100.0% | Yes | No | [{'id': 40517987762258, 'product_id': 715393928405, [{'id': 40518439075922, 'product_id': 715424697557 |
| status | datetime | 100.0% | Yes | No | active, active |
| handle | datetime | 100.0% | Yes | No | 20oz-i-love-you-the-most-personalized-tumbler, 20oz-sisters-she-to-my-nanigans-personalized-tumbl |
| title | datetime | 100.0% | Yes | No | "I Love You The Most" 20oz Personalized Stainless , "She" Nanigans - Customized 20oz Tumbler for Your  |
| images | array | 100.0% | Yes | No | [{'id': 31499773640786, 'alt': '"I Love You The Mo, [{'id': 31499773739090, 'alt': '"She" Nanigans - C |
| created_at | datetime | 100.0% | Yes | No | 2023-08-23T23:52:15-07:00, 2023-08-24T08:38:58-07:00 |
| updated_at | datetime | 100.0% | Yes | No | 2025-10-06T00:30:10-07:00, 2025-10-09T05:17:37-07:00 |
| published_at | datetime | 100.0% | Yes | No | 2023-08-24T01:09:45-07:00, 2023-08-30T00:54:10-07:00 |
| template_suffix | string | 100.0% | Yes | No | ,  |
| vendor | datetime | 100.0% | Yes | No | Makezbright, Makezbright |
| published_scope | string | 100.0% | Yes | No | global, global |
| product_type | datetime | 100.0% | Yes | No | Tumbler, Tumbler |
| id | integer | 100.0% | Yes | No | 7153939284050, 7154246975570 |
| image | object | 100.0% | Yes | No | {'id': 31499773640786, 'alt': '"I Love You The Mos, {'id': 31499773739090, 'alt': '"She" Nanigans - Cu |
| admin_graphql_api_id | datetime | 100.0% | Yes | No | gid://shopify/Product/7153939284050, gid://shopify/Product/7154246975570 |
| tags | datetime | 100.0% | Yes | No | "I, 20oz, clone, couple/upload, Drinkware_Tumbler,, "She", 20oz, Clipart_NV107, clone, Customized, Dri |

**Variant Analysis:**

- Total Variants: 5
- Average Variants per Product: 1.0
- Price Range: $29.99 - $29.99

**Image Analysis:**

- Total Images: 15
- Average Images per Product: 3.0

### Order

**Description:** Customer orders
**Sample Count:** 5

**Fields:**

| Field Name | Data Type | Usage % | Always Present | Nullable | Sample Values |
|------------|-----------|---------|---------------|----------|---------------|
| tax_lines | array | 100.0% | Yes | No | [{'price': '2.87', 'rate': 0.1, 'title': 'Federal , [{'price': '3.35', 'rate': 0.1, 'title': 'Federal  |
| buyer_accepts_marketing | boolean | 100.0% | Yes | No | True, False |
| created_at | datetime | 100.0% | Yes | No | 2025-10-23T23:52:58-07:00, 2025-10-23T23:24:43-07:00 |
| email | string | 100.0% | Yes | No | mrsbida@aol.com, mariafreckles57@gmail.com |
| discount_applications | array | 100.0% | Yes | No | [{'target_type': 'line_item', 'type': 'discount_co, [{'target_type': 'line_item', 'type': 'discount_co |
| merchant_business_entity_id | datetime | 100.0% | Yes | No | MTI4MDAzNTk4NDE4, MTI4MDAzNTk4NDE4 |
| current_total_discounts | string | 100.0% | Yes | No | 19.14, 14.34 |
| total_price_set | object | 100.0% | Yes | No | {'shop_money': {'amount': '38.36', 'currency_code', {'shop_money': {'amount': '43.19', 'currency_code' |
| presentment_currency | string | 100.0% | Yes | No | USD, USD |
| total_price | string | 100.0% | Yes | No | 38.36, 43.19 |
| checkout_id | integer | 100.0% | Yes | No | 34367134859346, 34372878499922 |
| checkout_token | string | 100.0% | Yes | No | e9afbbf20aea73e47f32bb4e90432653, e4c713593ee655116d9ca6f3b405dea8 |
| total_discounts_set | object | 100.0% | Yes | No | {'shop_money': {'amount': '19.14', 'currency_code', {'shop_money': {'amount': '14.34', 'currency_code' |
| customer_locale | datetime | 100.0% | Yes | No | en-US, en-US |
| total_tax | string | 100.0% | Yes | No | 4.66, 4.69 |
| current_subtotal_price | string | 100.0% | Yes | No | 28.71, 33.51 |
| financial_status | string | 100.0% | Yes | No | paid, paid |
| current_total_price | string | 100.0% | Yes | No | 38.36, 43.19 |
| shipping_address | object | 100.0% | Yes | No | {'first_name': 'JAN', 'address1': '803 Findlay Dr', {'first_name': 'Maria', 'address1': '1863 Cornelia |
| confirmed | boolean | 100.0% | Yes | No | True, True |
| total_cash_rounding_payment_adjustment_set | object | 100.0% | Yes | No | {'shop_money': {'amount': '0.00', 'currency_code':, {'shop_money': {'amount': '0.00', 'currency_code': |
| source_identifier | unknown | 100.0% | Yes | No | N/A |
| current_total_price_set | object | 100.0% | Yes | No | {'shop_money': {'amount': '38.36', 'currency_code', {'shop_money': {'amount': '43.19', 'currency_code' |
| id | integer | 100.0% | Yes | No | 6589808345170, 6589795532882 |
| reference | unknown | 100.0% | Yes | No | N/A |
| location_id | unknown | 100.0% | Yes | No | N/A |
| currency | string | 100.0% | Yes | No | USD, USD |
| landing_site_ref | unknown | 100.0% | Yes | No | N/A |
| payment_terms | unknown | 100.0% | Yes | No | N/A |
| tags | string | 100.0% | Yes | No | ,  |
| total_discounts | string | 100.0% | Yes | No | 19.14, 14.34 |
| contact_email | string | 100.0% | Yes | No | mrsbida@aol.com, mariafreckles57@gmail.com |
| total_shipping_price_set | object | 100.0% | Yes | No | {'shop_money': {'amount': '4.99', 'currency_code':, {'shop_money': {'amount': '4.99', 'currency_code': |
| billing_address | object | 100.0% | Yes | No | {'first_name': 'jan', 'address1': '803 Findlay Dr', {'first_name': 'Maria', 'address1': '1863 Cornelia |
| confirmation_number | string | 100.0% | Yes | No | 0DVCUJV0W, EHCHUYKYT |
| closed_at | unknown | 100.0% | Yes | No | N/A |
| customer | object | 100.0% | Yes | No | {'id': 8832137625682, 'created_at': '2025-09-25T06, {'id': 7449843269714, 'created_at': '2024-10-20T20 |
| app_id | integer | 100.0% | Yes | No | 580111, 580111 |
| source_url | unknown | 100.0% | Yes | No | N/A |
| note_attributes | array | 100.0% | Yes | No | [{'name': 'utm_data_source', 'value': 'checkout_pr, [] |
| original_total_duties_set | unknown | 100.0% | Yes | No | N/A |
| current_total_tax | string | 100.0% | Yes | No | 4.66, 4.69 |
| original_total_additional_fees_set | unknown | 100.0% | Yes | No | N/A |
| updated_at | datetime | 100.0% | Yes | No | 2025-10-23T23:53:00-07:00, 2025-10-24T01:40:14-07:00 |
| total_line_items_price_set | object | 100.0% | Yes | No | {'shop_money': {'amount': '47.85', 'currency_code', {'shop_money': {'amount': '47.85', 'currency_code' |
| current_total_duties_set | unknown | 100.0% | Yes | No | N/A |
| landing_site | datetime | 100.0% | Yes | No | /discount/vip30?utm_source=Klaviyo&utm_medium=emai, /discount/vip30 |
| payment_gateway_names | array | 100.0% | Yes | No | ['Stripe Card Payments'], ['Stripe Card Payments'] |
| source_name | string | 100.0% | Yes | No | web, web |
| number | integer | 100.0% | Yes | No | 922177, 922176 |
| token | string | 100.0% | Yes | No | 1f6ddff5a5dbcd54a8984e1b37eb463a, ff616ac525744beda1b4861da901e138 |
| fulfillments | array | 100.0% | Yes | No | [], [] |
| current_subtotal_price_set | object | 100.0% | Yes | No | {'shop_money': {'amount': '28.71', 'currency_code', {'shop_money': {'amount': '33.51', 'currency_code' |
| company | unknown | 100.0% | Yes | No | N/A |
| browser_ip | string | 100.0% | Yes | No | 107.199.195.222, 72.69.75.37 |
| total_cash_rounding_refund_adjustment_set | object | 100.0% | Yes | No | {'shop_money': {'amount': '0.00', 'currency_code':, {'shop_money': {'amount': '0.00', 'currency_code': |
| estimated_taxes | boolean | 100.0% | Yes | No | False, False |
| processed_at | datetime | 100.0% | Yes | No | 2025-10-23T23:52:57-07:00, 2025-10-23T23:24:42-07:00 |
| client_details | object | 100.0% | Yes | No | {'accept_language': 'en-US', 'browser_height': Non, {'accept_language': 'en-US', 'browser_height': Non |
| order_number | integer | 100.0% | Yes | No | 923177, 923176 |
| subtotal_price | string | 100.0% | Yes | No | 28.71, 33.51 |
| total_outstanding | string | 100.0% | Yes | No | 0.00, 0.00 |
| referring_site | datetime | 100.0% | Yes | No | https://l.facebook.com/ |
| current_total_discounts_set | object | 100.0% | Yes | No | {'shop_money': {'amount': '19.14', 'currency_code', {'shop_money': {'amount': '14.34', 'currency_code' |
| cancel_reason | unknown | 100.0% | Yes | No | N/A |
| note | unknown | 100.0% | Yes | No | N/A |
| subtotal_price_set | object | 100.0% | Yes | No | {'shop_money': {'amount': '28.71', 'currency_code', {'shop_money': {'amount': '33.51', 'currency_code' |
| name | datetime | 100.0% | Yes | No | #MZBs923177, #MZBs923176 |
| current_total_additional_fees_set | unknown | 100.0% | Yes | No | N/A |
| device_id | unknown | 100.0% | Yes | No | N/A |
| total_weight | integer | 100.0% | Yes | No | 0, 0 |
| duties_included | boolean | 100.0% | Yes | No | False, False |
| cancelled_at | unknown | 100.0% | Yes | No | N/A |
| admin_graphql_api_id | datetime | 100.0% | Yes | No | gid://shopify/Order/6589808345170, gid://shopify/Order/6589795532882 |
| order_status_url | datetime | 100.0% | Yes | No | https://makezbrightgifts.com/28003598418/orders/1f, https://makezbrightgifts.com/28003598418/orders/ff |
| refunds | array | 100.0% | Yes | No | [], [] |
| discount_codes | array | 100.0% | Yes | No | [{'code': 'vip40', 'amount': '19.14', 'type': 'per, [{'code': 'vip30', 'amount': '14.34', 'type': 'per |
| tax_exempt | boolean | 100.0% | Yes | No | False, False |
| cart_token | datetime | 100.0% | Yes | No | hWN3NvqPtE14ixpbtuXffV7h, hWN4TUXrQv29nzFA2HqeQxNJ |
| shipping_lines | array | 100.0% | Yes | No | [{'id': 5488698523730, 'carrier_identifier': None,, [{'id': 5488686760018, 'carrier_identifier': None, |
| fulfillment_status | unknown | 100.0% | Yes | No | N/A |
| total_tip_received | string | 100.0% | Yes | No | 0.00, 0.00 |
| current_total_tax_set | object | 100.0% | Yes | No | {'shop_money': {'amount': '4.66', 'currency_code':, {'shop_money': {'amount': '4.69', 'currency_code': |
| taxes_included | boolean | 100.0% | Yes | No | False, False |
| po_number | unknown | 100.0% | Yes | No | N/A |
| line_items | array | 100.0% | Yes | No | [{'id': 15907571105874, 'admin_graphql_api_id': 'g, [{'id': 15907540664402, 'admin_graphql_api_id': 'g |
| phone | string | 100.0% | Yes | No | +18177131345 |
| total_line_items_price | string | 100.0% | Yes | No | 47.85, 47.85 |
| merchant_of_record_app_id | unknown | 100.0% | Yes | No | N/A |
| user_id | unknown | 100.0% | Yes | No | N/A |
| total_tax_set | object | 100.0% | Yes | No | {'shop_money': {'amount': '4.66', 'currency_code':, {'shop_money': {'amount': '4.69', 'currency_code': |
| test | boolean | 100.0% | Yes | No | False, False |

**Line Item Analysis:**

- Total Line Items: 6
- Average Items per Order: 1.2
- Line Item Price Range: $15.95 - $15.95

**Financial Analysis:**

- Total Revenue: $245.83
- Total Tax: $29.41
- Average Order Value: $49.17

### Customer

**Description:** Store customers
**Sample Count:** 5

**Fields:**

| Field Name | Data Type | Usage % | Always Present | Nullable | Sample Values |
|------------|-----------|---------|---------------|----------|---------------|
| created_at | datetime | 100.0% | Yes | No | 2025-10-24T02:22:53-07:00, 2025-10-24T02:18:12-07:00 |
| multipass_identifier | unknown | 100.0% | Yes | No | N/A |
| updated_at | datetime | 100.0% | Yes | No | 2025-10-24T02:22:57-07:00, 2025-10-24T02:18:16-07:00 |
| email | datetime | 100.0% | Yes | No | kathleengeary29@yahoo.com, hazel1415@yahoo.com |
| sms_marketing_consent | object | 100.0% | Yes | No | {'state': 'subscribed', 'opt_in_level': 'unknown',, {'state': 'subscribed', 'opt_in_level': 'unknown', |
| id | integer | 100.0% | Yes | No | 8902846283858, 8902843531346 |
| admin_graphql_api_id | datetime | 100.0% | Yes | No | gid://shopify/Customer/8902846283858, gid://shopify/Customer/8902843531346 |
| currency | string | 100.0% | Yes | No | USD, USD |
| default_address | object | 40.0% | No | Yes | {'id': 9527637016658, 'customer_id': 8902733037650, {'id': 9527591141458, 'customer_id': 8902692864082 |
| verified_email | boolean | 100.0% | Yes | No | True, True |
| total_spent | string | 100.0% | Yes | No | 0.00, 0.00 |
| tax_exempt | boolean | 100.0% | Yes | No | False, False |
| last_name | string | 100.0% | Yes | No | Aguirre, Young |
| email_marketing_consent | object | 100.0% | Yes | No | {'state': 'subscribed', 'opt_in_level': 'unknown',, {'state': 'subscribed', 'opt_in_level': 'unknown', |
| last_order_name | datetime | 100.0% | Yes | No | #MZBs923175, #MZBs923174 |
| last_order_id | integer | 100.0% | Yes | No | 6589761159250, 6589717774418 |
| tags | string | 100.0% | Yes | No | ,  |
| orders_count | integer | 100.0% | Yes | No | 0, 0 |
| first_name | string | 100.0% | Yes | No | Paula, Nikki |
| tax_exemptions | array | 100.0% | Yes | No | [], [] |
| phone | string | 100.0% | Yes | No | +17746789409, +12406043278 |
| addresses | array | 100.0% | Yes | No | [], [] |
| note | unknown | 100.0% | Yes | No | N/A |
| state | string | 100.0% | Yes | No | disabled, disabled |

**Address Analysis:**

- Total Addresses: 2
- Average Addresses per Customer: 0.4

**Tags Analysis:**

- Total Tags: 0
- Unique Tags: 0

### Collection

**Description:** Product collections
**Sample Count:** 5

**Fields:**

| Field Name | Data Type | Usage % | Always Present | Nullable | Sample Values |
|------------|-----------|---------|---------------|----------|---------------|
| body_html | unknown | 100.0% | Yes | No | N/A |
| title | datetime | 100.0% | Yes | No | 1st Baby 30d Trending, 1st House 30d Trending |
| sort_order | string | 100.0% | Yes | No | manual, manual |
| updated_at | datetime | 100.0% | Yes | No | 2025-10-09T05:14:16-07:00, 2025-10-16T04:18:13-07:00 |
| published_at | datetime | 100.0% | Yes | No | 2023-05-12T02:53:38-07:00, 2023-05-12T02:53:39-07:00 |
| template_suffix | unknown | 100.0% | Yes | No | N/A |
| published_scope | string | 100.0% | Yes | No | global, global |
| handle | datetime | 100.0% | Yes | No | 1st-baby-30d-trending, 1st-house-30d-trending |
| id | integer | 100.0% | Yes | No | 271706882130, 271706849362 |
| admin_graphql_api_id | datetime | 100.0% | Yes | No | gid://shopify/Collection/271706882130, gid://shopify/Collection/271706849362 |

### ShopPolicies

**Description:** Store policies and configurations
**Sample Count:** 0

**Fields:**

| Field Name | Data Type | Usage % | Always Present | Nullable | Sample Values |
|------------|-----------|---------|---------------|----------|---------------|
| refund_policy | Refund policy information | - | - | - | - |
| privacy_policy | Privacy policy information | - | - | - | - |
| terms_of_service | Terms of service information | - | - | - | - |
| shipping_policy | Shipping policy information | - | - | - | - |
| subscription_policy | Subscription policy information | - | - | - | - |
| shop_policy | General shop policy information | - | - | - | - |

## Entity Relationships

| From Entity | To Entity | Relationship Type | Description | Foreign Key | Example |
|-------------|-----------|-------------------|-------------|-------------|---------|
| Product | Variant | one-to-many | Products have multiple variants | product_id | Product A -> Variant A1, Variant A2 |
| Product | Collection | many-to-many | Products can be in multiple collections | N/A | Product A -> Collection X, Collection Y |
| Order | Customer | many-to-one | Orders belong to customers | customer_id | Order 1, Order 2 -> Customer A |
| Order | Product | many-to-many | Orders contain multiple products via line items | N/A | Order A -> Product X, Product Y |
| Customer | Address | one-to-many | Customers can have multiple addresses | customer_id | Customer A -> Address 1, Address 2 |
| Product | Image | one-to-many | Products can have multiple images | product_id | Product A -> Image 1, Image 2 |
| Order | Address | one-to-many | Orders have shipping and billing addresses | order_id | Order A -> Shipping Address, Billing Address |

## Field Analysis

### Data Type Distribution

- **array:** 14 fields
- **boolean:** 9 fields
- **datetime:** 32 fields
- **integer:** 11 fields
- **object:** 20 fields
- **string:** 34 fields
- **unknown:** 24 fields

### Entity-Specific Fields

**Product:**
  - body_html
  - images
  - created_at
  - updated_at
  - published_scope
  - options
  - id
  - image
  - admin_graphql_api_id
  - variants
  - status
  - handle
  - title
  - published_at
  - template_suffix
  - vendor
  - product_type
  - tags

**Order:**
  - current_total_tax
  - tax_lines
  - buyer_accepts_marketing
  - created_at
  - original_total_additional_fees_set
  - updated_at
  - email
  - total_line_items_price_set
  - current_total_duties_set
  - landing_site
  - discount_applications
  - payment_gateway_names
  - merchant_business_entity_id
  - current_total_discounts
  - source_name
  - number
  - total_price_set
  - token
  - fulfillments
  - current_subtotal_price_set
  - company
  - browser_ip
  - presentment_currency
  - total_price
  - total_cash_rounding_refund_adjustment_set
  - estimated_taxes
  - processed_at
  - client_details
  - order_number
  - subtotal_price
  - total_outstanding
  - checkout_id
  - checkout_token
  - total_discounts_set
  - customer_locale
  - total_tax
  - referring_site
  - current_subtotal_price
  - financial_status
  - current_total_discounts_set
  - current_total_price
  - shipping_address
  - confirmed
  - total_cash_rounding_payment_adjustment_set
  - cancel_reason
  - note
  - subtotal_price_set
  - name
  - current_total_additional_fees_set
  - source_identifier
  - device_id
  - total_weight
  - duties_included
  - current_total_price_set
  - cancelled_at
  - id
  - reference
  - admin_graphql_api_id
  - location_id
  - currency
  - order_status_url
  - refunds
  - landing_site_ref
  - discount_codes
  - tax_exempt
  - payment_terms
  - cart_token
  - shipping_lines
  - fulfillment_status
  - total_tip_received
  - tags
  - current_total_tax_set
  - total_discounts
  - contact_email
  - total_shipping_price_set
  - taxes_included
  - billing_address
  - po_number
  - confirmation_number
  - line_items
  - phone
  - total_line_items_price
  - closed_at
  - customer
  - app_id
  - merchant_of_record_app_id
  - user_id
  - total_tax_set
  - source_url
  - note_attributes
  - test
  - original_total_duties_set

**Customer:**
  - tags
  - created_at
  - multipass_identifier
  - updated_at
  - email
  - sms_marketing_consent
  - first_name
  - id
  - admin_graphql_api_id
  - tax_exemptions
  - currency
  - state
  - phone
  - default_address
  - verified_email
  - total_spent
  - tax_exempt
  - last_name
  - addresses
  - email_marketing_consent
  - note
  - last_order_name
  - last_order_id
  - orders_count

**Collection:**
  - body_html
  - title
  - sort_order
  - updated_at
  - published_at
  - template_suffix
  - published_scope
  - handle
  - id
  - admin_graphql_api_id

**ShopPolicies:**
  - subscription_policy
  - privacy_policy
  - terms_of_service
  - shipping_policy
  - shop_policy
  - refund_policy

## Sample Data

*(Sample data shows actual structure from your store)*

### products Sample

```json
{
  "id": 7153939284050,
  "title": "\"I Love You The Most\" 20oz Personalized Stainless Steel Tumbler",
  "body_html": "<div>\n    \n    <ul>\n        <li>Say goodbye to lukewarm letdowns with double wall steel insulation designed to maintain temperature for hours on end.</li>\n    </ul>\n\n    <h2><b>LEAK PROOF</b></h2>\n    <ul>\n        <li>Compression sealing lid ensures a spill free system.</li>\n    </ul>\n\n    <h2><b>CUP HOLDER FRIENDLY</b></h2>\n    <ul>\n        <li>Fits perfectly in all standard cup holders for on the go convenience.</li>\n    </ul>\n\n    <h2><b>QUALITY YOU CAN COUNT ON</b></h2>\n    <ul>\n        <li>Durable stainless steel ready to withstand all life's daily chaos.</li>\n    </ul>\n\n    <h2><b>Product Details:</b></h2>\n    <ul>\n        <li>20oz Stainless Steel Tumbler</li>\n        <li>Keeps drinks hot + cold for hours</li>\n        <li>Spill proof suction</li>\n        <li>Durable stainless steel construction</li>\n        <li>Cup-holder friendly design</li>\n        <li>BPA free with no metallic taste</li>\n    </ul>\n\n    <h2><b>Join Our Hive</b></h2>\n    <p>Welcome to Make Z Bright - where laughs, cheers, and fun all tag along! We don't shy away from sipping and our joke-filled banter might be a bit spicy. But c'mon, why be serious when life's too short to be plain and PC? Enough chit-chat, let's talk about what you're really here for ~ our awesome drinkware! Our crew works tirelessly to print each pattern in our factory, so you know it's quality &amp; fine-tuned. So raise your Make Z Bright tumbler to the sky, take a slurp, and let your laughter fly!</p>\n</div>    <img height=\"773\" width=\"486\" alt=\"User picture\" src=\"https://judgeme.imgix.net/makezbright-gifts/1690664116__img_0898__original.jpeg?auto=format&amp;w=1024\" data-mce-fragment=\"1\" data-mce-src=\"https://judgeme.imgix.net/makezbright-gifts/1690664116__img_0898__original.jpeg?auto=format&amp;w=1024\">   <img src=\"https://cdn.discordapp.com/attachments/989274712590917653/1135041578524737556/sangnguyen_happy_face_women_showing_tumbler_just_buy_4bf251d5-eb24-4db4-9d6e-7c98cf97c846.png\" width=\"513\" height=\"513\">",
  "vendor": "Makezbright",
  "product_type": "Tumbler",
  "created_at": "2023-08-23T23:52:15-07:00",
  "handle": "20oz-i-love-you-the-most-personalized-tumbler",
  "updated_at": "2025-10-06T00:30:10-07:00",
  "published_at": "2023-08-24T01:09:45-07:00",
  "template_suffix": "",
  "published_scope": "global",
  "tags": "\"I, 20oz, clone, couple/upload, Drinkware_Tumbler, Love, Most\", Personalized, Stainless, Steel, The, Tumbler, You",
  "status": "active",
  "admin_graphql_api_id": "gid://shopify/Product/7153939284050",
  "variants": [
    {
      "id": 40517987762258,
      "product_id": 7153939284050,
      "title": "20oz",
      "price": "29.99",
      "position": 1,
      "inventory_policy": "continue",
      "compare_at_price": "59.99",
      "option1": "20oz",
      "option2": null,
      "option3": null,
      "created_at": "2023-08-23T23:52:15-07:00",
      "updated_at": "2025-05-31T12:20:32-07:00",
      "taxable": true,
      "barcode": null,
      "fulfillment_service": "manual",
      "grams": 0,
      "inventory_management": null,
      "requires_shipping": true,
      "sku": "HN152 - 20oz",
      "weight": 0.0,
      "weight_unit": "kg",
      "inventory_item_id": 42618843398226,
      "inventory_quantity": -26,
      "old_inventory_quantity": -26,
      "admin_graphql_api_id": "gid://shopify/ProductVariant/40517987762258",
      "image_id": null
    }
  ],
  "options": [
    {
      "id": 9299235209298,
      "product_id": 7153939284050,
      "name": "Size",
      "position": 1,
      "values": [
        "20oz"
      ]
    }
  ],
  "images": [
    {
      "id": 31499773640786,
      "alt": "\"I Love You The Most\" 20oz Personalized Stainless Steel Tumbler - Makezbright Gifts",
      "position": 1,
      "product_id": 7153939284050,
      "created_at": "2024-06-20T22:21:13-07:00",
      "updated_at": "2024-08-02T19:38:10-07:00",
      "admin_graphql_api_id": "gid://shopify/MediaImage/23884131860562",
      "width": 1200,
      "height": 1200,
      "src": "https://cdn.shopify.com/s/files/1/0280/0359/8418/files/i-love-you-the-most-20oz-personalized-stainless-steel-tumbler-996492.jpg?v=1718947273",
      "variant_ids": []
    },
    {
      "id": 31499773673554,
      "alt": "\"I Love You The Most\" 20oz Personalized Stainless Steel Tumbler - Makezbright Gifts",
      "position": 2,
      "product_id": 7153939284050,
      "created_at": "2024-06-20T22:21:13-07:00",
      "updated_at": "2024-08-02T19:38:10-07:00",
      "admin_graphql_api_id": "gid://shopify/MediaImage/23884131893330",
      "width": 1200,
      "height": 1200,
      "src": "https://cdn.shopify.com/s/files/1/0280/0359/8418/files/i-love-you-the-most-20oz-personalized-stainless-steel-tumbler-216962.jpg?v=1718947273",
      "variant_ids": []
    },
    {
      "id": 31499773706322,
      "alt": "\"I Love You The Most\" 20oz Personalized Stainless Steel Tumbler - Makezbright Gifts",
      "position": 3,
      "product_id": 7153939284050,
      "created_at": "2024-06-20T22:21:13-07:00",
      "updated_at": "2024-08-02T19:38:10-07:00",
      "admin_graphql_api_id": "gid://shopify/MediaImage/23884131926098",
      "width": 1200,
      "height": 1200,
      "src": "https://cdn.shopify.com/s/files/1/0280/0359/8418/files/i-love-you-the-most-20oz-personalized-stainless-steel-tumbler-270889.jpg?v=1718947273",
      "variant_ids": []
    }
  ],
  "image": {
    "id": 31499773640786,
    "alt": "\"I Love You The Most\" 20oz Personalized Stainless Steel Tumbler - Makezbright Gifts",
    "position": 1,
    "product_id": 7153939284050,
    "created_at": "2024-06-20T22:21:13-07:00",
    "updated_at": "2024-08-02T19:38:10-07:00",
    "admin_graphql_api_id": "gid://shopify/MediaImage/23884131860562",
    "width": 1200,
    "height": 1200,
    "src": "https://cdn.shopify.com/s/files/1/0280/0359/8418/files/i-love-you-the-most-20oz-personalized-stainless-steel-tumbler-996492.jpg?v=1718947273",
    "variant_ids": []
  }
}
```

### orders Sample

```json
{
  "id": 6589808345170,
  "admin_graphql_api_id": "gid://shopify/Order/6589808345170",
  "app_id": 580111,
  "browser_ip": "107.199.195.222",
  "buyer_accepts_marketing": true,
  "cancel_reason": null,
  "cancelled_at": null,
  "cart_token": "hWN3NvqPtE14ixpbtuXffV7h",
  "checkout_id": 34367134859346,
  "checkout_token": "e9afbbf20aea73e47f32bb4e90432653",
  "client_details": {
    "accept_language": "en-US",
    "browser_height": null,
    "browser_ip": "107.199.195.222",
    "browser_width": null,
    "session_hash": null,
    "user_agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.6 Safari/605.1.15"
  },
  "closed_at": null,
  "company": null,
  "confirmation_number": "0DVCUJV0W",
  "confirmed": true,
  "contact_email": "mrsbida@aol.com",
  "created_at": "2025-10-23T23:52:58-07:00",
  "currency": "USD",
  "current_subtotal_price": "28.71",
  "current_subtotal_price_set": {
    "shop_money": {
      "amount": "28.71",
      "currency_code": "USD"
    },
    "presentment_money": {
      "amount": "28.71",
      "currency_code": "USD"
    }
  },
  "current_total_additional_fees_set": null,
  "current_total_discounts": "19.14",
  "current_total_discounts_set": {
    "shop_money": {
      "amount": "19.14",
      "currency_code": "USD"
    },
    "presentment_money": {
      "amount": "19.14",
      "currency_code": "USD"
    }
  },
  "current_total_duties_set": null,
  "current_total_price": "38.36",
  "current_total_price_set": {
    "shop_money": {
      "amount": "38.36",
      "currency_code": "USD"
    },
    "presentment_money": {
      "amount": "38.36",
      "currency_code": "USD"
    }
  },
  "current_total_tax": "4.66",
  "current_total_tax_set": {
    "shop_money": {
      "amount": "4.66",
      "currency_code": "USD"
    },
    "presentment_money": {
      "amount": "4.66",
      "currency_code": "USD"
    }
  },
  "customer_locale": "en-US",
  "device_id": null,
  "discount_codes": [
    {
      "code": "vip40",
      "amount": "19.14",
      "type": "percentage"
    }
  ],
  "duties_included": false,
  "email": "mrsbida@aol.com",
  "estimated_taxes": false,
  "financial_status": "paid",
  "fulfillment_status": null,
  "landing_site": "/discount/vip30?utm_source=Klaviyo&utm_medium=email&_kx=Eqm8PsZayYf-hkaeZkoZi_yxHeRY9CWM-ITIroabtFw.XvGVEi",
  "landing_site_ref": null,
  "location_id": null,
  "merchant_business_entity_id": "MTI4MDAzNTk4NDE4",
  "merchant_of_record_app_id": null,
  "name": "#MZBs923177",
  "note": null,
  "note_attributes": [
    {
      "name": "utm_data_source",
      "value": "checkout_promotions_url_bar"
    },
    {
      "name": "utm_id",
      "value": "120230396523780224"
    },
    {
      "name": "utm_source",
      "value": "120230396523780224"
    },
    {
      "name": "utm_medium",
      "value": "paid"
    },
    {
      "name": "utm_campaign",
      "value": "120230396523900224"
    },
    {
      "name": "utm_term",
      "value": "120230396523820224"
    },
    {
      "name": "country",
      "value": "US"
    },
    {
      "name": "fbc",
      "value": "fb.1.1758806575268.IwY2xjawNCG3NleHRuA2FlbQEwAGFkaWQBqyTopaBScAEesokrCukzhj8CiXVAVyJ_YHi-dEjexqqv9pdXKdVRnmVQV9Uh-ETnURXfC2E_aem_sRhFB-Bu0-JnlCv8E0s0uQ"
    },
    {
      "name": "fbp",
      "value": "fb.1.1758805031025.607953656"
    },
    {
      "name": "host",
      "value": "https://makezbrightgifts.com"
    },
    {
      "name": "locale",
      "value": "en"
    },
    {
      "name": "sh",
      "value": "956"
    },
    {
      "name": "sw",
      "value": "1470"
    },
    {
      "name": "ttp",
      "value": "pWDsylpY3FiP9FHg4gKYTHHWaag.tt.0"
    },
    {
      "name": "utm_content",
      "value": "120230396523900224"
    },
    {
      "name": "kx",
      "value": "Eqm8PsZayYf-hkaeZkoZi6hukCz_4wvMFvMCIUp10D8FbJ4K39s5SlgBhZgqx3_k.XvGVEi"
    }
  ],
  "number": 922177,
  "order_number": 923177,
  "order_status_url": "https://makezbrightgifts.com/28003598418/orders/1f6ddff5a5dbcd54a8984e1b37eb463a/authenticate?key=9d70c669c91ff37a778edb3355fc8017",
  "original_total_additional_fees_set": null,
  "original_total_duties_set": null,
  "payment_gateway_names": [
    "Stripe Card Payments"
  ],
  "phone": "+18177131345",
  "po_number": null,
  "presentment_currency": "USD",
  "processed_at": "2025-10-23T23:52:57-07:00",
  "reference": null,
  "referring_site": null,
  "source_identifier": null,
  "source_name": "web",
  "source_url": null,
  "subtotal_price": "28.71",
  "subtotal_price_set": {
    "shop_money": {
      "amount": "28.71",
      "currency_code": "USD"
    },
    "presentment_money": {
      "amount": "28.71",
      "currency_code": "USD"
    }
  },
  "tags": "",
  "tax_exempt": false,
  "tax_lines": [
    {
      "price": "2.87",
      "rate": 0.1,
      "title": "Federal Tax",
      "price_set": {
        "shop_money": {
          "amount": "2.87",
          "currency_code": "USD"
        },
        "presentment_money": {
          "amount": "2.87",
          "currency_code": "USD"
        }
      },
      "channel_liable": false
    },
    {
      "price": "1.79",
      "rate": 0.0625,
      "title": "State Tax",
      "price_set": {
        "shop_money": {
          "amount": "1.79",
          "currency_code": "USD"
        },
        "presentment_money": {
          "amount": "1.79",
          "currency_code": "USD"
        }
      },
      "channel_liable": false
    }
  ],
  "taxes_included": false,
  "test": false,
  "token": "1f6ddff5a5dbcd54a8984e1b37eb463a",
  "total_cash_rounding_payment_adjustment_set": {
    "shop_money": {
      "amount": "0.00",
      "currency_code": "USD"
    },
    "presentment_money": {
      "amount": "0.00",
      "currency_code": "USD"
    }
  },
  "total_cash_rounding_refund_adjustment_set": {
    "shop_money": {
      "amount": "0.00",
      "currency_code": "USD"
    },
    "presentment_money": {
      "amount": "0.00",
      "currency_code": "USD"
    }
  },
  "total_discounts": "19.14",
  "total_discounts_set": {
    "shop_money": {
      "amount": "19.14",
      "currency_code": "USD"
    },
    "presentment_money": {
      "amount": "19.14",
      "currency_code": "USD"
    }
  },
  "total_line_items_price": "47.85",
  "total_line_items_price_set": {
    "shop_money": {
      "amount": "47.85",
      "currency_code": "USD"
    },
    "presentment_money": {
      "amount": "47.85",
      "currency_code": "USD"
    }
  },
  "total_outstanding": "0.00",
  "total_price": "38.36",
  "total_price_set": {
    "shop_money": {
      "amount": "38.36",
      "currency_code": "USD"
    },
    "presentment_money": {
      "amount": "38.36",
      "currency_code": "USD"
    }
  },
  "total_shipping_price_set": {
    "shop_money": {
      "amount": "4.99",
      "currency_code": "USD"
    },
    "presentment_money": {
      "amount": "4.99",
      "currency_code": "USD"
    }
  },
  "total_tax": "4.66",
  "total_tax_set": {
    "shop_money": {
      "amount": "4.66",
      "currency_code": "USD"
    },
    "presentment_money": {
      "amount": "4.66",
      "currency_code": "USD"
    }
  },
  "total_tip_received": "0.00",
  "total_weight": 0,
  "updated_at": "2025-10-23T23:53:00-07:00",
  "user_id": null,
  "billing_address": {
    "first_name": "jan",
    "address1": "803 Findlay Dr",
    "phone": null,
    "city": "Arlington",
    "zip": "76012",
    "province": "Texas",
    "country": "United States",
    "last_name": "BIDA",
    "address2": null,
    "company": null,
    "latitude": 32.7451355,
    "longitude": -97.16106169999999,
    "name": "jan BIDA",
    "country_code": "US",
    "province_code": "TX"
  },
  "customer": {
    "id": 8832137625682,
    "created_at": "2025-09-25T06:11:09-07:00",
    "updated_at": "2025-10-23T23:52:59-07:00",
    "first_name": "jan",
    "last_name": "BIDA",
    "state": "disabled",
    "note": null,
    "verified_email": true,
    "multipass_identifier": null,
    "tax_exempt": false,
    "email_marketing_consent": {
      "state": "subscribed",
      "opt_in_level": "unknown",
      "consent_updated_at": "2025-09-25T06:11:04-07:00"
    },
    "sms_marketing_consent": {
      "state": "subscribed",
      "opt_in_level": "unknown",
      "consent_updated_at": "2025-09-25T06:11:05-07:00",
      "consent_collected_from": "OTHER"
    },
    "tags": "",
    "email": "BFFLYER20@AOL.COM",
    "phone": "+18177131345",
    "currency": "USD",
    "tax_exemptions": [],
    "admin_graphql_api_id": "gid://shopify/Customer/8832137625682",
    "default_address": {
      "id": 9527668310098,
      "customer_id": 8832137625682,
      "first_name": "JAN",
      "last_name": "BIDA",
      "company": null,
      "address1": "803 Findlay Dr",
      "address2": null,
      "city": "Arlington",
      "province": "Texas",
      "country": "United States",
      "zip": "76012",
      "phone": "8177131345",
      "name": "JAN BIDA",
      "province_code": "TX",
      "country_code": "US",
      "country_name": "United States",
      "default": true
    }
  },
  "discount_applications": [
    {
      "target_type": "line_item",
      "type": "discount_code",
      "value": "40.0",
      "value_type": "percentage",
      "allocation_method": "across",
      "target_selection": "all",
      "code": "vip40"
    }
  ],
  "fulfillments": [],
  "line_items": [
    {
      "id": 15907571105874,
      "admin_graphql_api_id": "gid://shopify/LineItem/15907571105874",
      "attributed_staffs": [],
      "current_quantity": 3,
      "fulfillable_quantity": 3,
      "fulfillment_service": "manual",
      "fulfillment_status": null,
      "gift_card": false,
      "grams": 0,
      "name": "Family - The Greatest Gift Our Parents Gave Us Was Each Other - Personalized Christmas Ornament - 4\" x 2.75\"/ Acrylic",
      "price": "15.95",
      "price_set": {
        "shop_money": {
          "amount": "15.95",
          "currency_code": "USD"
        },
        "presentment_money": {
          "amount": "15.95",
          "currency_code": "USD"
        }
      },
      "product_exists": true,
      "product_id": 6994888523858,
      "properties": [
        {
          "name": "Quotes",
          "value": "The Greatest Gift Our Parents Gave Us Was Each Other"
        },
        {
          "name": "Number Of People",
          "value": "4"
        },
        {
          "name": "Choose Gender #1",
          "value": "Man"
        },
        {
          "name": "Man's Skin #1",
          "value": "1"
        },
        {
          "name": "Choose Color",
          "value": "1"
        },
        {
          "name": "Man's Hair #1",
          "value": "Older & Thin Hair"
        },
        {
          "name": "Older & Thin Hair",
          "value": "11"
        },
        {
          "name": "Man's Wings #1",
          "value": "No"
        },
        {
          "name": "Enter Name #1",
          "value": "Jack"
        },
        {
          "name": "Choose Gender #2",
          "value": "Man"
        },
        {
          "name": "Man's Skin #2",
          "value": "1"
        },
        {
          "name": "Man's Hair #2",
          "value": "Short Hair"
        },
        {
          "name": "Short Hair\u200b",
          "value": "40"
        },
        {
          "name": "Man's Wings #2",
          "value": "wing"
        },
        {
          "name": "Enter Name #2",
          "value": "David"
        },
        {
          "name": "Choose Gender #3",
          "value": "Woman"
        },
        {
          "name": "Woman's Skin #3",
          "value": "1"
        },
        {
          "name": "Choose Color\u200b",
          "value": "4"
        },
        {
          "name": "Woman's Hair #3",
          "value": "NECK LENGTH"
        },
        {
          "name": "NECK LENGTH",
          "value": "43"
        },
        {
          "name": "Woman's Wings #3",
          "value": "No"
        },
        {
          "name": "Enter Name 3",
          "value": "Janice"
        },
        {
          "name": "Choose Gender #4",
          "value": "Woman"
        },
        {
          "name": "Woman's Skin #4",
          "value": "1"
        },
        {
          "name": "Choose Color\u200b\u200b\u200b",
          "value": "2"
        },
        {
          "name": "Woman's Hair #4",
          "value": "NECK LENGTH"
        },
        {
          "name": "NECK LENGTH\u200b",
          "value": "19"
        },
        {
          "name": "Woman's Wings #4",
          "value": "No"
        },
        {
          "name": "Enter Name 4",
          "value": "Sharon"
        },
        {
          "name": "_customily-thumb-id",
          "value": "_thumb-id-1761141300826"
        },
        {
          "name": "_customily-preview",
          "value": "https://cdn.customily.com/shopify/assetFiles/previews/makezbright.myshopify.com/6947497c-2f1d-40a0-8491-9498cd913e83.jpeg"
        },
        {
          "name": "_customily-thumb",
          "value": "https://cdn.customily.com/shopify/assetFiles/thumbs/makezbright.myshopify.com/6947497c-2f1d-40a0-8491-9498cd913e83.jpeg"
        },
        {
          "name": "_customily-production-url",
          "value": "https://cdn.customily.com/ExportFile/leuleushop/69a0b54f-27f1-4436-9c16-d38a6b5245e4.png"
        },
        {
          "name": "_customily-personalization-id",
          "value": "_customily-id-503270f6-d4a4-4aaf-9c4c-6eb19337defa"
        }
      ],
      "quantity": 3,
      "requires_shipping": true,
      "sku": "HSC1 - Acrylic",
      "taxable": true,
      "title": "Family - The Greatest Gift Our Parents Gave Us Was Each Other - Personalized Christmas Ornament",
      "total_discount": "0.00",
      "total_discount_set": {
        "shop_money": {
          "amount": "0.00",
          "currency_code": "USD"
        },
        "presentment_money": {
          "amount": "0.00",
          "currency_code": "USD"
        }
      },
      "variant_id": 40537120407634,
      "variant_inventory_management": null,
      "variant_title": "4\" x 2.75\"/ Acrylic",
      "vendor": "Makezbright",
      "tax_lines": [
        {
          "channel_liable": false,
          "price": "2.87",
          "price_set": {
            "shop_money": {
              "amount": "2.87",
              "currency_code": "USD"
            },
            "presentment_money": {
              "amount": "2.87",
              "currency_code": "USD"
            }
          },
          "rate": 0.1,
          "title": "Federal Tax"
        },
        {
          "channel_liable": false,
          "price": "1.79",
          "price_set": {
            "shop_money": {
              "amount": "1.79",
              "currency_code": "USD"
            },
            "presentment_money": {
              "amount": "1.79",
              "currency_code": "USD"
            }
          },
          "rate": 0.0625,
          "title": "State Tax"
        }
      ],
      "duties": [],
      "discount_allocations": [
        {
          "amount": "19.14",
          "amount_set": {
            "shop_money": {
              "amount": "19.14",
              "currency_code": "USD"
            },
            "presentment_money": {
              "amount": "19.14",
              "currency_code": "USD"
            }
          },
          "discount_application_index": 0
        }
      ]
    }
  ],
  "payment_terms": null,
  "refunds": [],
  "shipping_address": {
    "first_name": "JAN",
    "address1": "803 Findlay Dr",
    "phone": "8177131345",
    "city": "Arlington",
    "zip": "76012",
    "province": "Texas",
    "country": "United States",
    "last_name": "BIDA",
    "address2": null,
    "company": null,
    "latitude": 32.7451355,
    "longitude": -97.16106169999999,
    "name": "JAN BIDA",
    "country_code": "US",
    "province_code": "TX"
  },
  "shipping_lines": [
    {
      "id": 5488698523730,
      "carrier_identifier": null,
      "code": "Standard Shipping",
      "discounted_price": "4.99",
      "discounted_price_set": {
        "shop_money": {
          "amount": "4.99",
          "currency_code": "USD"
        },
        "presentment_money": {
          "amount": "4.99",
          "currency_code": "USD"
        }
      },
      "is_removed": false,
      "phone": null,
      "price": "4.99",
      "price_set": {
        "shop_money": {
          "amount": "4.99",
          "currency_code": "USD"
        },
        "presentment_money": {
          "amount": "4.99",
          "currency_code": "USD"
        }
      },
      "requested_fulfillment_service_id": null,
      "source": "shopify",
      "title": "Standard Shipping",
      "tax_lines": [],
      "discount_allocations": []
    }
  ]
}
```

### customers Sample

```json
{
  "id": 8902846283858,
  "created_at": "2025-10-24T02:22:53-07:00",
  "updated_at": "2025-10-24T02:22:57-07:00",
  "first_name": null,
  "last_name": null,
  "orders_count": 0,
  "state": "disabled",
  "total_spent": "0.00",
  "last_order_id": null,
  "note": null,
  "verified_email": true,
  "multipass_identifier": null,
  "tax_exempt": false,
  "tags": "",
  "last_order_name": null,
  "email": "kathleengeary29@yahoo.com",
  "phone": "+17746789409",
  "currency": "USD",
  "addresses": [],
  "tax_exemptions": [],
  "email_marketing_consent": {
    "state": "subscribed",
    "opt_in_level": "unknown",
    "consent_updated_at": "2025-10-24T02:22:50-07:00"
  },
  "sms_marketing_consent": {
    "state": "subscribed",
    "opt_in_level": "unknown",
    "consent_updated_at": "2025-10-24T02:22:51-07:00",
    "consent_collected_from": "OTHER"
  },
  "admin_graphql_api_id": "gid://shopify/Customer/8902846283858"
}
```

### collections Sample

```json
{
  "id": 271706882130,
  "handle": "1st-baby-30d-trending",
  "title": "1st Baby 30d Trending",
  "updated_at": "2025-10-09T05:14:16-07:00",
  "body_html": null,
  "published_at": "2023-05-12T02:53:38-07:00",
  "sort_order": "manual",
  "template_suffix": null,
  "published_scope": "global",
  "admin_graphql_api_id": "gid://shopify/Collection/271706882130"
}
```

## Technical Notes

- Schema extracted using direct Shopify REST API calls
- Field usage percentages based on actual sample data analysis
- 'Always Present' indicates fields with 100% usage rate in samples
- Data types determined by analyzing actual field values
- Relationships based on Shopify's standard data model
- Sample data includes real (anonymized) data from your store

## API Endpoints Used

- `GET /admin/api/{version}/shop.json` - Store information
- `GET /admin/api/{version}/products.json` - Products
- `GET /admin/api/{version}/orders.json` - Orders
- `GET /admin/api/{version}/customers.json` - Customers
- `GET /admin/api/{version}/custom_collections.json` - Collections
