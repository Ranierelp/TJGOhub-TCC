from rest_framework.routers import DefaultRouter
from .viewsets import TagViewSet

tags_router = DefaultRouter()
tags_router.register(r"tags", TagViewSet, basename="tag")


