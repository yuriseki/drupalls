"""
Static call detector for Drupal service patterns.

File: drupalls/lsp/capabilities/di_refactoring/static_call_detector.py
"""
from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass
class StaticServiceCall:
    """Represents a detected static service call."""

    service_id: str
    line_number: int
    column_start: int
    column_end: int
    full_match: str
    call_type: str  # 'service', 'shortcut', 'container'


# Mapping of Drupal shortcuts to service IDs
DRUPAL_SHORTCUTS: dict[str, str] = {
    "entityTypeManager": "entity_type.manager",
    "database": "database",
    "config": "config.factory",
    "configFactory": "config.factory",
    "currentUser": "current_user",
    "messenger": "messenger",
    "logger": "logger.factory",
    "state": "state",
    "cache": "cache_factory",
    "token": "token",
    "languageManager": "language_manager",
    "moduleHandler": "module_handler",
    "time": "datetime.time",
    "request": "request_stack",
    "routeMatch": "current_route_match",
    "urlGenerator": "url_generator",
    "destination": "redirect.destination",
    "pathValidator": "path.validator",
    "httpClient": "http_client",
    "lock": "lock",
    "queue": "queue",
    "flood": "flood",
    "typedDataManager": "typed_data_manager",
    "transliteration": "transliteration",
    "keyValue": "keyvalue",
    "classResolver": "class_resolver",
}


class StaticCallDetector:
    """Detects static Drupal service calls in PHP code."""

    # Pattern for \Drupal::service('service_id')
    SERVICE_PATTERN = re.compile(
        r"\\Drupal::service\(\s*['\"]([^'\"]+)['\"]\s*\)"
    )

    # Pattern for \Drupal::getContainer()->get('service_id')
    CONTAINER_PATTERN = re.compile(
        r"\\Drupal::getContainer\(\)->get\(\s*['\"]([^'\"]+)['\"]\s*\)"
    )

    # Pattern for \Drupal::shortcutMethod()
    SHORTCUT_PATTERN = re.compile(r"\\Drupal::(\w+)\(\)")

    def detect_all(self, content: str) -> list[StaticServiceCall]:
        """Detect all static service calls in the content."""
        calls: list[StaticServiceCall] = []
        lines = content.split("\n")

        for line_num, line in enumerate(lines):
            calls.extend(self._detect_in_line(line, line_num))

        return calls

    def _detect_in_line(
        self, line: str, line_num: int
    ) -> list[StaticServiceCall]:
        """Detect static calls in a single line."""
        calls: list[StaticServiceCall] = []

        # Check for \Drupal::service('...')
        for match in self.SERVICE_PATTERN.finditer(line):
            calls.append(
                StaticServiceCall(
                    service_id=match.group(1),
                    line_number=line_num,
                    column_start=match.start(),
                    column_end=match.end(),
                    full_match=match.group(0),
                    call_type="service",
                )
            )

        # Check for \Drupal::getContainer()->get('...')
        for match in self.CONTAINER_PATTERN.finditer(line):
            calls.append(
                StaticServiceCall(
                    service_id=match.group(1),
                    line_number=line_num,
                    column_start=match.start(),
                    column_end=match.end(),
                    full_match=match.group(0),
                    call_type="container",
                )
            )

        # Check for \Drupal::shortcutMethod()
        for match in self.SHORTCUT_PATTERN.finditer(line):
            method_name = match.group(1)
            if method_name in DRUPAL_SHORTCUTS:
                calls.append(
                    StaticServiceCall(
                        service_id=DRUPAL_SHORTCUTS[method_name],
                        line_number=line_num,
                        column_start=match.start(),
                        column_end=match.end(),
                        full_match=match.group(0),
                        call_type="shortcut",
                    )
                )

        return calls

    def get_unique_services(
        self, calls: list[StaticServiceCall]
    ) -> dict[str, list[StaticServiceCall]]:
        """Group calls by unique service ID."""
        services: dict[str, list[StaticServiceCall]] = {}
        for call in calls:
            if call.service_id not in services:
                services[call.service_id] = []
            services[call.service_id].append(call)
        return services
