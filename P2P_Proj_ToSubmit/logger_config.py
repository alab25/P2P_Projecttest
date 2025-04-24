import logging
import os

def setup_logger(name):
    log_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), f"{name}.log")  
    # This ensures logs are saved in the same directory as `logger_config.py`

    logger = logging.getLogger(name)  # Unique logger per file
    logger.setLevel(logging.DEBUG)  # Capture all logs (DEBUG and above)

    # File handler (logs to file)
    file_handler = logging.FileHandler(log_file, mode='a')  
    file_handler.setLevel(logging.DEBUG)  

    # Console handler (logs to console)
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)  

    # Define log format
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)

    # Attach handlers to logger
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    return logger  # Return configured logger