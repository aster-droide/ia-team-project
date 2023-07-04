import logging

# create a separate logger instance (rather than direct logging) to set
# up the log format for both modules. Exporting logs both to a file, and displaying in CLI.
# The compiled app runs through the CLI so it's easy to have the logs at hand there and not
# have to find the app.log file. Logging to file to keep historic logs.

# root logger to lowest level for debugging
logging.getLogger().setLevel(logging.DEBUG)

# instantiate logger
logger = logging.getLogger(__name__)

# handler log messages and set output (CLI & log file)
console_handler = logging.StreamHandler()
file_handler = logging.FileHandler('app.log')

# level of logging
console_handler.setLevel(logging.INFO)
file_handler.setLevel(logging.INFO)

# set formatting and add to handlers
log_format = logging.Formatter('%(asctime)s - %(levelname)s - %(agent)s - %(message)s')
console_handler.setFormatter(log_format)
file_handler.setFormatter(log_format)

# add handlers to logger
logger.addHandler(console_handler)
logger.addHandler(file_handler)

# ensure log messages will be logged
logging.getLogger().propagate = True