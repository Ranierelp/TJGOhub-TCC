from django.contrib import admin

from apps.kanban.models import KanbanColumn


@admin.register(KanbanColumn)
class KanbanColumnAdmin(admin.ModelAdmin):
    list_display = ['name', 'color', 'order', 'project', 'is_active']
    list_filter = ['project', 'is_active']
    ordering = ['project', 'order']
