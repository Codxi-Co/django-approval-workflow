"""Django admin configuration for approval workflow models."""

from django.contrib import admin

from .models import ApprovalFlow, ApprovalInstance


@admin.register(ApprovalFlow)
class ApprovalFlowAdmin(admin.ModelAdmin):
    """Admin interface for ApprovalFlow model."""
    
    list_display = ('id', 'content_type', 'object_id', 'created_at')
    list_filter = ('content_type', 'created_at')
    search_fields = ('object_id',)
    readonly_fields = ('created_at',)


@admin.register(ApprovalInstance)
class ApprovalInstanceAdmin(admin.ModelAdmin):
    """Admin interface for ApprovalInstance model."""
    
    list_display = (
        'id', 'flow', 'step_number', 'status', 'assigned_to',
        'action_user', 'started_at'
    )
    list_filter = ('status', 'started_at', 'updated_at')
    search_fields = ('comment', 'assigned_to__username', 'action_user__username')
    readonly_fields = ('started_at', 'updated_at')
    raw_id_fields = ('assigned_to', 'action_user', 'flow')
