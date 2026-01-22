"""
Tests for drupalls/workspace/classes_cache.py
"""

from pathlib import Path
from unittest.mock import Mock
import pytest

from drupalls.workspace.classes_cache import ClassesCache, ClassDefinition


@pytest.fixture
def workspace_cache():
    """Mock WorkspaceCache."""
    cache = Mock()
    cache.workspace_root = Path("/fake/project")
    cache.cache_dir = Path("/fake/project/.drupalls/cache")
    cache.server = None
    return cache


@pytest.fixture
def classes_cache(workspace_cache):
    """ClassesCache instance."""
    # Set mock properties before creating ClassesCache
    workspace_cache.project_root = Path("/fake/project")
    workspace_cache.workspace_root = Path("/fake/project")
    workspace_cache.file_info = {}
    return ClassesCache(workspace_cache)


class TestClassDefinition:
    """Tests for ClassDefinition dataclass."""

    def test_creation(self):
        """Test ClassDefinition creation."""
        class_def = ClassDefinition(
            id="\\Drupal\\Test\\TestClass",
            description="\\Drupal\\Test\\TestClass",
            file_path=Path("/path/to/file.php"),
            line_number=10,
            namespace="\\Drupal\\Test",
            class_name="TestClass",
            full_name="\\Drupal\\Test\\TestClass",
            methods=["method1", "method2"],
        )

        assert class_def.namespace == "\\Drupal\\Test"
        assert class_def.class_name == "TestClass"
        assert class_def.full_name == "\\Drupal\\Test\\TestClass"
        assert class_def.methods == ["method1", "method2"]
        assert class_def.file_path == Path("/path/to/file.php")
        assert class_def.line_number == 10

        # Test CachedDataBase compatibility
        assert class_def.id == "\\Drupal\\Test\\TestClass"
        assert class_def.description == "\\Drupal\\Test\\TestClass"


class TestClassesCache:
    """Tests for ClassesCache."""

    def test_initialization(self, classes_cache):
        """Test cache initialization."""
        assert classes_cache._classes == {}

    @pytest.mark.asyncio
    async def test_scan_finds_php_files(self, classes_cache, tmp_path, workspace_cache):
        """Test scanning finds PHP files."""
        # Update the workspace_root after ClassesCache creation
        classes_cache.workspace_root = tmp_path

        # Create test PHP files
        php_file1 = tmp_path / "TestClass.php"
        php_file1.write_text("""
<?php

namespace Drupal\\Test;

class TestClass {
    public function method1() {}
    public function method2() {}
}
""")

        php_file2 = tmp_path / "subdir" / "AnotherClass.php"
        php_file2.parent.mkdir()
        php_file2.write_text("""
<?php

class AnotherClass {
    public function test() {}
}
""")

        # Skip non-PHP files
        txt_file = tmp_path / "readme.txt"
        txt_file.write_text("not php")

        await classes_cache.scan()

        assert len(classes_cache._classes) == 2
        assert "Drupal\\Test\\TestClass" in classes_cache._classes
        assert "AnotherClass" in classes_cache._classes

    def test_parse_php_file_extracts_class_info(self, classes_cache, tmp_path):
        """Test parsing PHP file extracts class information."""
        php_file = tmp_path / "test.php"
        php_file.write_text("""
<?php

namespace Drupal\\Example;

class ExampleController {
    public function build() {}
    protected function helper() {}
    private function _private() {}
}

class AnotherClass {
    public function test() {}
}
""")

        classes_cache._parse_php_file(php_file)

        assert len(classes_cache._classes) == 2

        # Check first class
        controller = classes_cache._classes["Drupal\\Example\\ExampleController"]
        assert controller.namespace == "Drupal\\Example"
        assert controller.class_name == "ExampleController"
        assert controller.full_name == "Drupal\\Example\\ExampleController"
        assert "build" in controller.methods
        assert "helper" not in controller.methods  # protected
        assert "_private" not in controller.methods  # private
        assert controller.file_path == php_file
        assert controller.line_number > 0

        # Check second class
        another = classes_cache._classes["Drupal\\Example\\AnotherClass"]
        assert another.namespace == "Drupal\\Example"
        assert another.class_name == "AnotherClass"
        assert another.full_name == "Drupal\\Example\\AnotherClass"
        assert "test" in another.methods

    def test_get_methods(self, classes_cache):
        """Test getting methods for a class."""
        # Add test class
        classes_cache._classes["TestClass"] = ClassDefinition(
            id="TestClass",
            description="TestClass",
            file_path=Path("/test.php"),
            line_number=1,
            namespace="",
            class_name="TestClass",
            full_name="TestClass",
            methods=["method1", "method2"],
        )

        assert classes_cache.get_methods("TestClass") == ["method1", "method2"]
        assert classes_cache.get_methods("NonExistent") == []

    def test_search_methods(self, classes_cache):
        """Test searching methods in a class."""
        # Add test class
        classes_cache._classes["TestClass"] = ClassDefinition(
            id="TestClass",
            description="TestClass",
            file_path=Path("/test.php"),
            line_number=1,
            namespace="",
            class_name="TestClass",
            full_name="TestClass",
            methods=["build", "create", "delete", "view"],
        )

        results = classes_cache.search_methods("TestClass", "e")
        assert "create" in results
        assert "delete" in results
        assert "build" not in results  # doesn't contain 'e'

    def test_get_and_search(self, classes_cache):
        """Test get and search methods."""
        # Add test classes
        classes_cache._classes["\\Drupal\\Test\\Controller"] = ClassDefinition(
            id="\\Drupal\\Test\\Controller",
            description="\\Drupal\\Test\\Controller",
            file_path=Path("/controller.php"),
            line_number=1,
            namespace="\\Drupal\\Test",
            class_name="Controller",
            full_name="\\Drupal\\Test\\Controller",
            methods=["build"],
        )

        classes_cache._classes["\\Symfony\\Component\\HttpFoundation\\Request"] = ClassDefinition(
            id="\\Symfony\\Component\\HttpFoundation\\Request",
            description="\\Symfony\\Component\\HttpFoundation\\Request",
            file_path=Path("/request.php"),
            line_number=1,
            namespace="\\Symfony\\Component\\HttpFoundation",
            class_name="Request",
            full_name="\\Symfony\\Component\\HttpFoundation\\Request",
            methods=["get"],
        )

        # Test get
        controller = classes_cache.get("\\Drupal\\Test\\Controller")
        assert controller is not None
        assert controller.class_name == "Controller"

        # Test search
        results = classes_cache.search("Controller")
        assert len(results) == 1
        assert results[0].class_name == "Controller"

        results = classes_cache.search("Symfony")
        assert len(results) == 1
        assert "Symfony" in results[0].namespace

    def test_invalidate_file(self, classes_cache):
        """Test invalidating cache for a file."""
        # Add classes from different files
        classes_cache._classes["Class1"] = ClassDefinition(
            id="Class1", description="Class1",
            file_path=Path("/file1.php"), line_number=1,
            namespace="", class_name="Class1", full_name="Class1",
            methods=[]
        )
        classes_cache._classes["Class2"] = ClassDefinition(
            id="Class2", description="Class2",
            file_path=Path("/file2.php"), line_number=1,
            namespace="", class_name="Class2", full_name="Class2",
            methods=[]
        )

        classes_cache.invalidate_file(Path("/file1.php"))

        assert "Class1" not in classes_cache._classes
        assert "Class2" in classes_cache._classes

    @pytest.mark.asyncio
    async def test_disk_persistence(self, classes_cache, tmp_path):
        """Test loading and saving to disk."""
        # Set up cache directory
        cache_dir = tmp_path / ".drupalls" / "cache"
        classes_cache.workspace_cache.cache_dir = cache_dir

        # Add test class
        classes_cache._classes["TestClass"] = ClassDefinition(
            id="\\Drupal\\Test\\TestClass",
            description="\\Drupal\\Test\\TestClass",
            file_path=Path("/path/to/file.php"),
            line_number=10,
            namespace="\\Drupal\\Test",
            class_name="TestClass",
            full_name="\\Drupal\\Test\\TestClass",
            methods=["method1", "method2"],
        )

        # Save to disk
        await classes_cache.save_to_disk()

        # Clear memory
        classes_cache._classes.clear()

        # Load from disk
        loaded = await classes_cache.load_from_disk()
        assert loaded is True
        assert "TestClass" in classes_cache._classes

        loaded_class = classes_cache._classes["TestClass"]
        assert loaded_class.namespace == "\\Drupal\\Test"
        assert loaded_class.methods == ["method1", "method2"]