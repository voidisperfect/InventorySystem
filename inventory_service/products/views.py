from rest_framework.views import APIView
from rest_framework.response import Response
from .models import Product


class ProductPriceList(APIView):
    def post(self, request):
        product_ids = request.data.get("product_ids", [])
        if not product_ids:
            return Response({"error": "No product_ids provided"}, status=400)

        products = Product.objects.filter(id__in=product_ids)
        # Returns stringified UUIDs mapped to decimal strings
        prices = {str(p.id): str(p.price) for p in products}

        return Response(prices)
