from enum import Enum


class DrupalClassType(Enum):
    """Classification of Drupal PHP class types."""
    
    CONTROLLER = "controller"       # extends ControllerBase
    FORM = "form"                   # extends FormBase, ConfigFormBase
    PLUGIN = "plugin"               # has @Plugin annotation or extends PluginBase
    ENTITY = "entity"               # extends ContentEntityBase, ConfigEntityBase
    SERVICE = "service"             # registered in services.yml
    EVENT_SUBSCRIBER = "subscriber" # implements EventSubscriberInterface
    ACCESS_CHECKER = "access"       # implements AccessInterface
    BLOCK = "block"                 # extends BlockBase (also a plugin)
    FIELD_FORMATTER = "formatter"   # extends FormatterBase
    FIELD_WIDGET = "widget"         # extends WidgetBase
    MIGRATION = "migration"         # extends MigrationBase
    QUEUE_WORKER = "queue_worker"   # extends QueueWorkerBase
    CONSTRAINT = "constraint"       # extends Constraint
    UNKNOWN = "unknown"
