from rest_framework.routers import DefaultRouter
from .viewsets import ProjectViewSet

projects_router = DefaultRouter()
projects_router.register(r"projects", ProjectViewSet, basename="project")
