"""
Notification system for multi-channel alerts.

This package provides notification orchestration across:
- Toast (WebSocket)
- Email (SMTP)
- SMS (Twilio)
- Push (Web Push)

Story: 11.6 - Notification & Alert System
"""

from src.notifications.service import NotificationService

__all__ = ["NotificationService"]
