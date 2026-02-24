from rest_framework.routers import DefaultRouter
from .viewsets import TestRunViewSet

runs_router = DefaultRouter()
runs_router.register(r"runs", TestRunViewSet, basename="run")
