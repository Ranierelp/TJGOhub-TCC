from rest_framework.routers import DefaultRouter
from .viewsets import EnvironmentViewSet

environments_router = DefaultRouter()
environments_router.register(r"environments", EnvironmentViewSet, basename="environment")
