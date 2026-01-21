from dataclasses import dataclass, field
from pathlib import Path

from drupalls.context.types import DrupalClassType


@dataclass
class ClassContext:
    """
    Holds detected PHP class information at a cursor position.
    
    This dataclass contains everything needed to understand the current
    class context for intelligent LSP features.
    """
    
    # Fully qualified class name (e.g., "Drupal\\mymodule\\Controller\\MyController")
    fqcn: str
    
    # Short class name (e.g., "MyController")
    short_name: str
    
    # File path where the class is defined
    file_path: Path
    
    # Line number where class declaration starts (0-indexed)
    class_line: int
    
    # Parent classes in inheritance order (immediate parent first)
    parent_classes: list[str] = field(default_factory=list)
    
    # Implemented interfaces
    interfaces: list[str] = field(default_factory=list)
    
    # Used traits
    traits: list[str] = field(default_factory=list)
    
    # Drupal classification (set by DrupalContextClassifier)
    drupal_type: DrupalClassType = DrupalClassType.UNKNOWN
    
    # Whether the class uses ContainerInjectionInterface pattern
    has_container_injection: bool = False
    
    # Methods defined in this class
    methods: list[str] = field(default_factory=list)
    
    # Properties defined in this class
    properties: list[str] = field(default_factory=list)
    
    def has_parent(self, parent_fqcn: str) -> bool:
        """Check if class extends a specific parent (at any level)."""
        parent_lower = parent_fqcn.lower()
        return any(p.lower() == parent_lower for p in self.parent_classes)
    
    def implements_interface(self, interface_fqcn: str) -> bool:
        """Check if class implements a specific interface."""
        interface_lower = interface_fqcn.lower()
        return any(i.lower() == interface_lower for i in self.interfaces)
    
    def has_method(self, method_name: str) -> bool:
        """Check if class defines a specific method."""
        return method_name in self.methods

