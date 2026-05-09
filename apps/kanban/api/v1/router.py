from rest_framework.routers import DefaultRouter

from .viewsets import KanbanColumnViewSet

kanban_router = DefaultRouter()
kanban_router.register(r"kanban/columns", KanbanColumnViewSet, basename="kanban-column")
