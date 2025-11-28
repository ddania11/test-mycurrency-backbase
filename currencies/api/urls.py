from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import CurrencyConversionView, CurrencyViewSet, ExchangeRateViewSet

# Create router for viewsets
router = DefaultRouter()
router.register(r"currencies", CurrencyViewSet, basename="currency")
router.register(r"rates", ExchangeRateViewSet, basename="exchangerate")

urlpatterns = [
    path("convert/", CurrencyConversionView.as_view(), name="currency-convert"),
    # ViewSet routes
    path("", include(router.urls)),
]
