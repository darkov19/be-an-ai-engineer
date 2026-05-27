import logging
import sys
import copy
import structlog

def task_log_processor(logger, name, event_dict):
    from backend.utils.tasks import active_task_id, task_manager
    try:
        t_id = active_task_id.get()
    except LookupError:
        t_id = ""

    if t_id:
        # Create a deep copy of the event dict to ensure we queue a clean snapshot
        # before any serializing or destructive processors run.
        log_copy = copy.deepcopy(event_dict)
        task_manager.enqueue_log(t_id, log_copy)
    return event_dict

def setup_logging():
    # Setup root logger to pass-through info level logs
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=logging.INFO,
    )

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.StackInfoRenderer(),
            structlog.dev.set_exc_info,
            structlog.processors.TimeStamper(fmt="iso"),
            task_log_processor,
            structlog.processors.JSONRenderer()
        ],
        wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )
