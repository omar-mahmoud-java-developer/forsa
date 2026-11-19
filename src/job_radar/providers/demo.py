# SPDX-License-Identifier: MIT
# Copyright (c) 2026 [YOUR NAME OR GITHUB HANDLE]
"""Offline demo source: synthetic jobs for trying the agent without any account or network."""

from __future__ import annotations

from ..models import Job
from .base import Provider, register

DEMO_JOBS = [
    Job("demo-1", "demo", "Senior Backend Engineer", "Acme Robotics", "Berlin, Germany",
        "https://example.com/jobs/1", "We build services in Python and PostgreSQL on AWS. 4+ years of experience. "
        "Docker and Kubernetes. Hybrid in Berlin.", "1 day ago", "hybrid", True),
    Job("demo-2", "demo", "Backend Developer (Python)", "Globex", "Remote",
        "https://example.com/jobs/2", "Remote-first team. Python, Django, REST APIs. 2 years of experience.",
        "2 days ago", "remote", True),
    Job("demo-3", "demo", "Principal Architect", "Initech", "Munich, Germany",
        "https://example.com/jobs/3", "Lead architecture across teams. 12+ years of experience required.",
        "3 days ago", "onsite", False),
    Job("demo-4", "demo", "Sales Manager", "Umbrella Trading", "Hamburg, Germany",
        "https://example.com/jobs/4", "Grow our sales team. 5 years of experience in sales.", "1 day ago", "onsite",
        False),
    Job("demo-5", "demo", "Data Engineer", "Hooli", "Berlin, Germany",
        "https://example.com/jobs/5", "Python pipelines, Airflow, Kafka. Do you have experience with Kafka? "
        "3 years of experience.", "1 day ago", "hybrid", True),
]


@register("demo")
class DemoProvider(Provider):
    name = "demo"
    description = "synthetic jobs for a first run"

    def search(self, search_cfg: dict) -> list[Job]:
        return [Job(**{**j.__dict__, "extra": {}}) for j in DEMO_JOBS]
