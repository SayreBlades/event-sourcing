# Architecture Comparison: Event-Sourced vs API-Driven

This document provides a detailed comparison of the two notification architectures implemented in this project.

## Executive Summary

| Criteria                        | Event-Sourced    | API-Driven         | Winner        |
|---------------------------------|------------------|--------------------|---------------|
| Loose Coupling                  | ✅ Excellent     | ⚠️ Poor             | Event-Sourced |
| Single Responsibility           | ✅ Excellent     | ⚠️ Poor             | Event-Sourced |
| Explicit Control                | ⚠️ Implicit       | ✅ Explicit        | API-Driven    |
| Debugging Simple Cases          | ⚠️ Follow events  | ✅ Follow calls    | API-Driven    |
| Debugging Complex Cases         | ✅ Centralized   | ⚠️ Distributed      | Event-Sourced |
| Adding New Notifications        | ✅ One place     | ⚠️ Multiple places  | Event-Sourced |
| Notification Service Complexity | ⚠️ Higher         | ✅ Lower           | API-Driven    |
| Domain Service Complexity       | ✅ Lower         | ⚠️ Higher           | Event-Sourced |

**Recommendation**: For systems with complex, cross-cutting notification requirements, **event-sourced** is generally the better choice due to centralized logic and loose coupling.

---

## Detailed Comparison

### 1. Service Dependencies

#### Event-Sourced
```
OrderingService → EventBus
PricingService → EventBus
NotificationService → EventBus, DataStore, Channels
```

Domain services only depend on the event bus. They don't know about notifications.

#### API-Driven
```
OrderingService → NotificationAPI, DataStore
PricingService → NotificationAPI, DataStore (products, carts, customers, preferences!)
NotificationService → DataStore, Channels
```

Domain services depend on the notification API AND must query multiple data domains.

### 2. Where Does Logic Live?

#### Price Drop Alert Example

**Event-Sourced:**
```python
# PricingService (simple)
def update_price(self, product_id, new_price):
    self.data_store.update_product_price(product_id, new_price)
    self.event_bus.publish(price_changed(...))  # That's it!

# NotificationService (has all the logic)
def _handle_price_changed(self, event):
    carts = self.data_store.get_carts_containing_product(...)
    for cart in carts:
        customer = self.data_store.get_customer(...)
        prefs = self.data_store.get_notification_preferences(...)
        if eligible(customer, prefs):
            self.send_notification(...)
```

**API-Driven:**
```python
# PricingService (complex - has notification logic!)
def update_price(self, product_id, new_price):
    self.data_store.update_product_price(product_id, new_price)
    
    # Now pricing service must do all this:
    carts = self.data_store.get_carts_containing_product(...)
    for cart in carts:
        customer = self.data_store.get_customer(...)
        prefs = self.data_store.get_notification_preferences(...)
        if eligible(customer, prefs):
            self.notification_api.send(...)

# NotificationAPI (simple - just sends)
def send_notification(self, request):
    customer = self.data_store.get_customer(request.customer_id)
    self.render_and_send(...)
```

### 3. Adding a New Notification Type

**Scenario:** Notify customers when an item on their wishlist goes on sale.

#### Event-Sourced
1. Ensure promotions service publishes `PromotionCreated` events (may already exist)
2. Add wishlist data to data store
3. Add handler in NotificationService:
   ```python
   def _handle_promotion_created(self, event):
       wishlists = self.data_store.get_wishlists_with_product(...)
       # ... notification logic
   ```

**Changes:** 1 file (NotificationService)

#### API-Driven
1. Promotions service must query wishlist data (new dependency!)
2. Promotions service must query customer preferences (new dependency!)
3. Promotions service must implement eligibility logic
4. Promotions service must call notification API

**Changes:** PromotionsService gains significant new code and dependencies

### 4. Debugging "Why Wasn't I Notified?"

**Scenario:** Customer Carol didn't receive a price drop alert.

#### Event-Sourced
1. Check event log: Was `PriceChanged` published? ✓
2. Check NotificationService logs:
   - Was Carol's cart found? ✓
   - Was she in eligible segment? ✓
   - Did she have price alerts enabled? ❌ **Found it!**

**All debugging in one service.**

#### API-Driven
1. Check PricingService logs: Did it query carts? ✓
2. Check PricingService: Did it find Carol's cart? ✓
3. Check PricingService: Did it query her segment? ✓
4. Check PricingService: Did it query her preferences? ❌ **Bug in PricingService!**
5. Or was the NotificationAPI called but failed?

**Debugging spans multiple services.**

### 5. Code Complexity Metrics

#### Lines of Code by Component

| Component           | Event-Sourced | API-Driven               |
|---------------------|---------------|--------------------------|
| NotificationService | ~300          | ~150                     |
| OrderingService     | ~100          | ~180                     |
| PricingService      | ~80           | ~200                     |
| EventCorrelator     | ~100          | N/A (in OrderingService) |
| **Total**           | ~580          | ~530                     |

Note: Similar total LOC, but complexity is distributed differently.

#### Cross-Domain Queries

| Service                             | Event-Sourced | API-Driven |
|-------------------------------------|---------------|------------|
| OrderingService queries customers   | No            | No         |
| OrderingService queries preferences | No            | No         |
| PricingService queries carts        | No            | **Yes**    |
| PricingService queries customers    | No            | **Yes**    |
| PricingService queries preferences  | No            | **Yes**    |
| NotificationService queries all     | Yes           | Yes        |

### 6. State Management

#### Order Complete Tracking

**Event-Sourced:**
```python
# EventCorrelator (in notification service)
class EventCorrelator:
    _order_states: dict[str, OrderShipmentState]
    
    def process_line_item_shipped(self, ...):
        # Track shipments, detect completion
```

State is managed in the notification service where notification logic lives.

**API-Driven:**
```python
# OrderingService (domain service has notification state!)
class OrderingService:
    _order_shipment_state: dict[str, set[str]]
    
    def ship_line_item(self, ...):
        # Track shipments, decide when to notify
```

State is managed in the domain service, mixing concerns.

### 7. Team Autonomy

#### Event-Sourced
- **Pricing Team:** "We publish events. We don't care about notifications."
- **Notification Team:** "We handle all notification logic. Tell us what events you publish."

Clear boundaries, independent deployments.

#### API-Driven
- **Pricing Team:** "We need to query carts and customers to send notifications. Can you add this field?"
- **Notification Team:** "We just send what you tell us. You decide who to notify."

Blurred boundaries, coordination required.

---

## When to Use Each Approach

### Use Event-Sourced When:
- ✅ Multiple services need notification capabilities
- ✅ Complex eligibility rules (cross-domain)
- ✅ Rules change frequently
- ✅ You want centralized notification logic
- ✅ Team autonomy is important
- ✅ You need event replay for debugging

### Use API-Driven When:
- ✅ Simple, direct notifications (1 service, 1 notification type)
- ✅ Caller has all needed context already
- ✅ You want explicit control in the calling service
- ✅ Notification service should be "dumb" (just send)
- ✅ Immediate feedback on notification success is critical

---

## Conclusion

For an e-commerce/BSS platform with multiple domains (ordering, pricing, promotions, billing) that all need to trigger notifications with complex eligibility rules:

**Event-Sourced is the better choice** because:
1. Domain services stay focused on their core responsibility
2. All notification logic is in one place
3. Adding new notification types doesn't require changing domain services
4. Debugging complex scenarios is easier
5. Teams can work independently

The API-driven approach works well for simpler cases but creates significant coupling and distributed complexity when notification logic spans multiple domains.
