import logging

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
console_handler = logging.StreamHandler()
# Create a formatter to define the format of the log messages
formatter = logging.Formatter(
    fmt="AccessTime: %(asctime)s.%(msecs)03d - LevelName: %(levelname)s - %(filename)s - %(funcName)s - %(lineno)d - "
        "Message:%(message)s - [PID: %(process)d] [Thread: %(threadName)s]",
    datefmt="%Y-%m-%d %H:%M:%S",
)
# Set the formatter for both the console and rotating file handlers
console_handler.setFormatter(formatter)
# Add the handlers to the logger
logger.addHandler(console_handler)
