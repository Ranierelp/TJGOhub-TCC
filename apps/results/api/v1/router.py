from rest_framework.routers import DefaultRouter
from .viewsets import TestResultViewSet

results_router = DefaultRouter()
results_router.register(r"results", TestResultViewSet, basename="result")
