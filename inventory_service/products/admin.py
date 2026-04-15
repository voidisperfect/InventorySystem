from django.contrib import admin
from .models import Product, Reservation


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    # This makes the columns visible in the list
    list_display = ("name", "stock_quantity", "price", "id")
    search_fields = ("name",)


@admin.register(Reservation)
class ReservationAdmin(admin.ModelAdmin):
    list_display = ("product", "quantity", "status", "order_id", "created_at")
    list_filter = ("status",)
