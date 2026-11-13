from enum import Enum


class OrderStatus(Enum):
    PAID = "Paid"
    PRINTFUL_DRAFT_CREATED = "Draft prepared"
    SUBMITTED_TO_PRINTFUL = "Submitted for fulfillment"
    IN_PRODUCTION = "In production"
    SHIPPED = "Shipped"
    DELIVERED = "Delivered"
    FAILED = "Failed"
