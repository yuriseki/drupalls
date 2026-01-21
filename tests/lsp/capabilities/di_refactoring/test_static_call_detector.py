"""
Tests for StaticCallDetector.

File: tests/lsp/capabilities/di_refactoring/test_static_call_detector.py
"""
from __future__ import annotations

import pytest
from drupalls.lsp.capabilities.di_refactoring.static_call_detector import (
    StaticCallDetector,
    StaticServiceCall,
    DRUPAL_SHORTCUTS,
)


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def detector() -> StaticCallDetector:
    """Create a fresh StaticCallDetector for each test."""
    return StaticCallDetector()


# ============================================================================
# Tests for detect_all
# ============================================================================

class TestDetectAll:
    """Tests for detect_all method."""

    def test_detect_service_call(self, detector: StaticCallDetector) -> None:
        """Test detection of Drupal::service() calls."""
        content = r"$manager = \Drupal::service('entity_type.manager');"
        calls = detector.detect_all(content)
        
        assert len(calls) == 1
        assert calls[0].service_id == "entity_type.manager"
        assert calls[0].call_type == "service"
        assert calls[0].line_number == 0

    def test_detect_service_call_double_quotes(self, detector: StaticCallDetector) -> None:
        """Test detection with double quotes."""
        content = r'$manager = \Drupal::service("entity_type.manager");'
        calls = detector.detect_all(content)
        
        assert len(calls) == 1
        assert calls[0].service_id == "entity_type.manager"

    def test_detect_container_get(self, detector: StaticCallDetector) -> None:
        """Test detection of getContainer()->get() calls."""
        content = r"$messenger = \Drupal::getContainer()->get('messenger');"
        calls = detector.detect_all(content)
        
        assert len(calls) == 1
        assert calls[0].service_id == "messenger"
        assert calls[0].call_type == "container"

    def test_detect_shortcut_method_entity_type_manager(
        self, detector: StaticCallDetector
    ) -> None:
        """Test detection of Drupal::entityTypeManager() shortcut."""
        content = r"$etm = \Drupal::entityTypeManager();"
        calls = detector.detect_all(content)
        
        assert len(calls) == 1
        assert calls[0].service_id == "entity_type.manager"
        assert calls[0].call_type == "shortcut"

    def test_detect_shortcut_method_database(
        self, detector: StaticCallDetector
    ) -> None:
        """Test detection of Drupal::database() shortcut."""
        content = r"$db = \Drupal::database();"
        calls = detector.detect_all(content)
        
        assert len(calls) == 1
        assert calls[0].service_id == "database"
        assert calls[0].call_type == "shortcut"

    def test_detect_shortcut_method_messenger(
        self, detector: StaticCallDetector
    ) -> None:
        """Test detection of Drupal::messenger() shortcut."""
        content = r"$msg = \Drupal::messenger();"
        calls = detector.detect_all(content)
        
        assert len(calls) == 1
        assert calls[0].service_id == "messenger"

    def test_detect_shortcut_method_current_user(
        self, detector: StaticCallDetector
    ) -> None:
        """Test detection of Drupal::currentUser() shortcut."""
        content = r"$user = \Drupal::currentUser();"
        calls = detector.detect_all(content)
        
        assert len(calls) == 1
        assert calls[0].service_id == "current_user"

    def test_detect_multiple_calls_same_line(
        self, detector: StaticCallDetector
    ) -> None:
        """Test detection of multiple calls on the same line."""
        content = r"$a = \Drupal::entityTypeManager(); $b = \Drupal::messenger();"
        calls = detector.detect_all(content)
        
        assert len(calls) == 2
        service_ids = {c.service_id for c in calls}
        assert service_ids == {"entity_type.manager", "messenger"}

    def test_detect_multiple_calls_different_lines(
        self, detector: StaticCallDetector
    ) -> None:
        """Test detection of multiple calls on different lines."""
        content = """
        $etm = \\Drupal::entityTypeManager();
        $messenger = \\Drupal::service('messenger');
        $db = \\Drupal::database();
        """
        calls = detector.detect_all(content)
        
        assert len(calls) == 3
        
    def test_detect_tracks_line_numbers(
        self, detector: StaticCallDetector
    ) -> None:
        """Test that line numbers are tracked correctly."""
        content = """line0
$etm = \\Drupal::entityTypeManager();
line2
$db = \\Drupal::database();
"""
        calls = detector.detect_all(content)
        
        assert len(calls) == 2
        assert calls[0].line_number == 1
        assert calls[1].line_number == 3

    def test_detect_tracks_column_positions(
        self, detector: StaticCallDetector
    ) -> None:
        """Test that column positions are tracked correctly."""
        content = r"    $etm = \Drupal::entityTypeManager();"
        calls = detector.detect_all(content)
        
        assert len(calls) == 1
        assert calls[0].column_start == 11  # After "    $etm = "

    def test_detect_no_calls_in_content(
        self, detector: StaticCallDetector
    ) -> None:
        """Test detection returns empty list when no calls present."""
        content = """
        $this->entityTypeManager->getStorage('node');
        $container->get('messenger');
        """
        calls = detector.detect_all(content)
        
        assert len(calls) == 0

    def test_detect_ignores_non_shortcut_methods(
        self, detector: StaticCallDetector
    ) -> None:
        """Test that non-shortcut Drupal:: methods are ignored."""
        content = r"$result = \Drupal::unknownMethod();"
        calls = detector.detect_all(content)
        
        assert len(calls) == 0

    def test_detect_service_with_spaces(
        self, detector: StaticCallDetector
    ) -> None:
        """Test detection with spaces around service ID."""
        content = r"$svc = \Drupal::service(  'my.service'  );"
        calls = detector.detect_all(content)
        
        assert len(calls) == 1
        assert calls[0].service_id == "my.service"

    def test_detect_empty_content(
        self, detector: StaticCallDetector
    ) -> None:
        """Test detection with empty content."""
        calls = detector.detect_all("")
        
        assert len(calls) == 0


# ============================================================================
# Tests for get_unique_services
# ============================================================================

class TestGetUniqueServices:
    """Tests for get_unique_services method."""

    def test_get_unique_services_groups_by_id(
        self, detector: StaticCallDetector
    ) -> None:
        """Test that calls are grouped by service ID."""
        content = """
        $etm1 = \\Drupal::entityTypeManager();
        $etm2 = \\Drupal::service('entity_type.manager');
        """
        calls = detector.detect_all(content)
        unique = detector.get_unique_services(calls)
        
        assert len(unique) == 1
        assert "entity_type.manager" in unique
        assert len(unique["entity_type.manager"]) == 2

    def test_get_unique_services_multiple_ids(
        self, detector: StaticCallDetector
    ) -> None:
        """Test grouping with multiple service IDs."""
        content = """
        $etm = \\Drupal::entityTypeManager();
        $msg = \\Drupal::messenger();
        $db = \\Drupal::database();
        $msg2 = \\Drupal::messenger();
        """
        calls = detector.detect_all(content)
        unique = detector.get_unique_services(calls)
        
        assert len(unique) == 3
        assert len(unique["messenger"]) == 2
        assert len(unique["entity_type.manager"]) == 1
        assert len(unique["database"]) == 1

    def test_get_unique_services_empty_list(
        self, detector: StaticCallDetector
    ) -> None:
        """Test get_unique_services with empty call list."""
        unique = detector.get_unique_services([])
        
        assert len(unique) == 0


# ============================================================================
# Tests for DRUPAL_SHORTCUTS constant
# ============================================================================

class TestDrupalShortcuts:
    """Tests for DRUPAL_SHORTCUTS mapping."""

    def test_shortcuts_is_dict(self) -> None:
        """Test that DRUPAL_SHORTCUTS is a dictionary."""
        assert isinstance(DRUPAL_SHORTCUTS, dict)

    def test_shortcuts_contains_common_services(self) -> None:
        """Test that common shortcuts are mapped."""
        expected_shortcuts = [
            "entityTypeManager",
            "database",
            "messenger",
            "currentUser",
            "config",
            "state",
            "logger",
        ]
        for shortcut in expected_shortcuts:
            assert shortcut in DRUPAL_SHORTCUTS, f"Missing shortcut: {shortcut}"

    def test_shortcuts_values_are_strings(self) -> None:
        """Test that all shortcut values are service ID strings."""
        for shortcut, service_id in DRUPAL_SHORTCUTS.items():
            assert isinstance(service_id, str), f"{shortcut} value is not a string"

    def test_entity_type_manager_mapping(self) -> None:
        """Test entityTypeManager maps to entity_type.manager."""
        assert DRUPAL_SHORTCUTS["entityTypeManager"] == "entity_type.manager"

    def test_database_mapping(self) -> None:
        """Test database maps to database."""
        assert DRUPAL_SHORTCUTS["database"] == "database"

    def test_config_mapping(self) -> None:
        """Test config maps to config.factory."""
        assert DRUPAL_SHORTCUTS["config"] == "config.factory"


# ============================================================================
# Tests for StaticServiceCall dataclass
# ============================================================================

class TestStaticServiceCall:
    """Tests for StaticServiceCall dataclass."""

    def test_create_static_service_call(self) -> None:
        """Test creating a StaticServiceCall instance."""
        call = StaticServiceCall(
            service_id="entity_type.manager",
            line_number=10,
            column_start=5,
            column_end=45,
            full_match=r"\Drupal::entityTypeManager()",
            call_type="shortcut",
        )
        
        assert call.service_id == "entity_type.manager"
        assert call.line_number == 10
        assert call.column_start == 5
        assert call.column_end == 45
        assert call.call_type == "shortcut"

    def test_static_service_call_equality(self) -> None:
        """Test that equal StaticServiceCall instances are equal."""
        call1 = StaticServiceCall(
            service_id="messenger",
            line_number=1,
            column_start=0,
            column_end=20,
            full_match=r"\Drupal::messenger()",
            call_type="shortcut",
        )
        call2 = StaticServiceCall(
            service_id="messenger",
            line_number=1,
            column_start=0,
            column_end=20,
            full_match=r"\Drupal::messenger()",
            call_type="shortcut",
        )
        
        assert call1 == call2
