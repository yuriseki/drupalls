from drupalls.context.class_context import ClassContext
from drupalls.context.types import DrupalClassType


# Mapping of Drupal base classes to class types
DRUPAL_BASE_CLASSES: dict[str, DrupalClassType] = {
    # Controllers
    "Drupal\\Core\\Controller\\ControllerBase": DrupalClassType.CONTROLLER,
    "ControllerBase": DrupalClassType.CONTROLLER,
    
    # Forms
    "Drupal\\Core\\Form\\FormBase": DrupalClassType.FORM,
    "Drupal\\Core\\Form\\ConfigFormBase": DrupalClassType.FORM,
    "Drupal\\Core\\Form\\ConfirmFormBase": DrupalClassType.FORM,
    "FormBase": DrupalClassType.FORM,
    "ConfigFormBase": DrupalClassType.FORM,
    
    # Entities
    "Drupal\\Core\\Entity\\ContentEntityBase": DrupalClassType.ENTITY,
    "Drupal\\Core\\Entity\\ConfigEntityBase": DrupalClassType.ENTITY,
    "Drupal\\Core\\Entity\\EntityBase": DrupalClassType.ENTITY,
    "ContentEntityBase": DrupalClassType.ENTITY,
    "ConfigEntityBase": DrupalClassType.ENTITY,
    
    # Plugins
    "Drupal\\Core\\Plugin\\PluginBase": DrupalClassType.PLUGIN,
    "Drupal\\Component\\Plugin\\PluginBase": DrupalClassType.PLUGIN,
    "PluginBase": DrupalClassType.PLUGIN,
    
    # Blocks (also plugins)
    "Drupal\\Core\\Block\\BlockBase": DrupalClassType.BLOCK,
    "BlockBase": DrupalClassType.BLOCK,
    
    # Field formatters/widgets
    "Drupal\\Core\\Field\\FormatterBase": DrupalClassType.FIELD_FORMATTER,
    "Drupal\\Core\\Field\\WidgetBase": DrupalClassType.FIELD_WIDGET,
    "FormatterBase": DrupalClassType.FIELD_FORMATTER,
    "WidgetBase": DrupalClassType.FIELD_WIDGET,
    
    # Migrations
    "Drupal\\migrate\\Plugin\\migrate\\source\\SourcePluginBase": DrupalClassType.MIGRATION,
    "Drupal\\migrate_drupal\\Plugin\\migrate\\source\\DrupalSqlBase": DrupalClassType.MIGRATION,
    
    # Queue workers
    "Drupal\\Core\\Queue\\QueueWorkerBase": DrupalClassType.QUEUE_WORKER,
    "QueueWorkerBase": DrupalClassType.QUEUE_WORKER,
    
    # Constraints
    "Symfony\\Component\\Validator\\Constraint": DrupalClassType.CONSTRAINT,
    "Drupal\\Core\\Validation\\Plugin\\Validation\\Constraint\\ConstraintBase": DrupalClassType.CONSTRAINT,
}

# Mapping of interfaces to class types
DRUPAL_INTERFACES: dict[str, DrupalClassType] = {
    "Symfony\\Component\\EventDispatcher\\EventSubscriberInterface": DrupalClassType.EVENT_SUBSCRIBER,
    "EventSubscriberInterface": DrupalClassType.EVENT_SUBSCRIBER,
    
    "Drupal\\Core\\Routing\\Access\\AccessInterface": DrupalClassType.ACCESS_CHECKER,
    "AccessInterface": DrupalClassType.ACCESS_CHECKER,
    
    "Drupal\\Core\\Form\\FormInterface": DrupalClassType.FORM,
    "FormInterface": DrupalClassType.FORM,
    
    "Drupal\\Core\\Entity\\EntityInterface": DrupalClassType.ENTITY,
    "EntityInterface": DrupalClassType.ENTITY,
    
    "Drupal\\Core\\Block\\BlockPluginInterface": DrupalClassType.BLOCK,
    "BlockPluginInterface": DrupalClassType.BLOCK,
}


class DrupalContextClassifier:
    """
    Classifies PHP classes into Drupal construct types.
    
    Uses parent class inheritance and interface implementation
    to determine what kind of Drupal construct a class represents.
    """
    
    def classify(self, context: ClassContext) -> DrupalClassType:
        """
        Classify a class context into a Drupal type.
        
        Priority:
        1. Check parent classes (more specific wins)
        2. Check interfaces
        3. Check namespace patterns
        4. Return UNKNOWN
        
        Args:
            context: ClassContext with parent/interface info
        
        Returns:
            DrupalClassType classification
        """
        # Check parent classes first (includes full hierarchy)
        for parent in context.parent_classes:
            # Check both full and short names
            if parent in DRUPAL_BASE_CLASSES:
                context.drupal_type = DRUPAL_BASE_CLASSES[parent]
                return context.drupal_type
            
            # Check short name
            short_parent = parent.split("\\")[-1]
            if short_parent in DRUPAL_BASE_CLASSES:
                context.drupal_type = DRUPAL_BASE_CLASSES[short_parent]
                return context.drupal_type
        
        # Check interfaces
        for interface in context.interfaces:
            if interface in DRUPAL_INTERFACES:
                context.drupal_type = DRUPAL_INTERFACES[interface]
                return context.drupal_type
            
            short_interface = interface.split("\\")[-1]
            if short_interface in DRUPAL_INTERFACES:
                context.drupal_type = DRUPAL_INTERFACES[short_interface]
                return context.drupal_type
        
        # Check namespace patterns as fallback
        drupal_type = self._classify_by_namespace(context.fqcn)
        context.drupal_type = drupal_type
        return drupal_type
    
    def _classify_by_namespace(self, fqcn: str) -> DrupalClassType:
        """
        Classify based on namespace patterns.
        
        This is a fallback for when parent class info isn't available.
        """
        fqcn_lower = fqcn.lower()
        
        patterns: dict[str, DrupalClassType] = {
            "\\controller\\": DrupalClassType.CONTROLLER,
            "\\form\\": DrupalClassType.FORM,
            "\\plugin\\block\\": DrupalClassType.BLOCK,
            "\\plugin\\field\\formatter\\": DrupalClassType.FIELD_FORMATTER,
            "\\plugin\\field\\widget\\": DrupalClassType.FIELD_WIDGET,
            "\\plugin\\migrate\\": DrupalClassType.MIGRATION,
            "\\plugin\\queueworker\\": DrupalClassType.QUEUE_WORKER,
            "\\plugin\\": DrupalClassType.PLUGIN,
            "\\entity\\": DrupalClassType.ENTITY,
            "\\eventsubscriber\\": DrupalClassType.EVENT_SUBSCRIBER,
            "\\access\\": DrupalClassType.ACCESS_CHECKER,
        }
        
        for pattern, dtype in patterns.items():
            if pattern in fqcn_lower:
                return dtype
        
        return DrupalClassType.UNKNOWN
    
    def is_service_class(self, context: ClassContext) -> bool:
        """
        Determine if the class is likely a Drupal service.
        
        Services typically:
        - Implement ContainerInjectionInterface
        - Have a create() method
        - Are registered in services.yml
        """
        # ContainerInjectionInterface is a strong indicator
        if context.has_container_injection:
            return True
        
        # create() static method is another indicator
        if "create" in context.methods:
            return True
        
        # Some types are always services
        service_types = {
            DrupalClassType.EVENT_SUBSCRIBER,
            DrupalClassType.ACCESS_CHECKER,
        }
        
        return context.drupal_type in service_types
