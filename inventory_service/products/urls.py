from django.urls import path
from .views import ProductPriceList

urlpatterns = [
    path("prices/", ProductPriceList.as_view(), name="product_prices"),
]
