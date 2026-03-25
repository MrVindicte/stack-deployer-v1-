"""Celery application for async task processing."""

from celery import Celery
from app.core.config import get_settings

settings = get_settings()

celery_app = Celery(
    "stack_deployer",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="Europe/Paris",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,  # One task at a time per worker
    result_expires=3600 * 24,  # Results expire after 24h
)

celery_app.autodiscover_tasks(["app.services"])
