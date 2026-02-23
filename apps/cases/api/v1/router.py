from rest_framework.routers import DefaultRouter
from .viewsets import TestCaseViewSet

cases_router = DefaultRouter()
cases_router.register(r"test-cases", TestCaseViewSet, basename="test-case")
