"""
logging/logger.mojo — Structured JSON logger. Zero Python imports.

Outputs one JSON line per log call, similar to structlog:
  {"level":"info","logger":"engine","msg":"simulation_started","extra":"runs=10000"}

Log levels:
  0 = DEBUG
  1 = INFO
  2 = WARNING
  3 = ERROR

Public API:
  struct Logger:
    fn __init__(out self, name: String, level: Int = 1)
    fn debug(self, msg: String, extra: String = "")
    fn info(self, msg: String, extra: String = "")
    fn warning(self, msg: String, extra: String = "")
    fn error(self, msg: String, extra: String = "")
    fn log(self, level: Int, msg: String, extra: String = "")

  fn get_logger(name: String) -> Logger
"""

from json.writer import json_escape_string


# ── Level constants ──────────────────────────────────────────────────────────

comptime LOG_DEBUG = 0
comptime LOG_INFO = 1
comptime LOG_WARNING = 2
comptime LOG_ERROR = 3


# ── Level name lookup ────────────────────────────────────────────────────────


fn _level_name(level: Int) -> String:
    """Convert numeric level to string name."""
    if level == LOG_DEBUG:
        return "debug"
    if level == LOG_INFO:
        return "info"
    if level == LOG_WARNING:
        return "warning"
    if level == LOG_ERROR:
        return "error"
    return "unknown"


# ── Logger struct ────────────────────────────────────────────────────────────


struct Logger:
    """Structured JSON logger. Outputs one JSON line per log call.

    Usage:
        var log = Logger("engine", LOG_INFO)
        log.info("started", "runs=10000")
        # prints: {"level":"info","logger":"engine","msg":"started","extra":"runs=10000"}
    """

    var name: String
    var level: Int

    fn __init__(out self, name: String, level: Int = 1):
        """Create a new Logger.

        Args:
            name: Logger name (appears in "logger" field).
            level: Minimum log level (0=DEBUG, 1=INFO, 2=WARNING, 3=ERROR).
        """
        self.name = name
        self.level = level

    fn debug(self, msg: String, extra: String = ""):
        """Log at DEBUG level (0)."""
        self.log(LOG_DEBUG, msg, extra)

    fn info(self, msg: String, extra: String = ""):
        """Log at INFO level (1)."""
        self.log(LOG_INFO, msg, extra)

    fn warning(self, msg: String, extra: String = ""):
        """Log at WARNING level (2)."""
        self.log(LOG_WARNING, msg, extra)

    fn error(self, msg: String, extra: String = ""):
        """Log at ERROR level (3)."""
        self.log(LOG_ERROR, msg, extra)

    fn log(self, level: Int, msg: String, extra: String = ""):
        """Emit a structured JSON log line if level >= self.level.

        Output format:
            {"level":"info","logger":"name","msg":"message","extra":"data"}

        If extra is empty, the "extra" field is omitted.
        """
        if level < self.level:
            return

        # Build JSON line manually (avoid circular import with json.writer)
        var line = String('{"level":"')
        line += json_escape_string(_level_name(level))
        line += '","logger":"'
        line += json_escape_string(self.name)
        line += '","msg":"'
        line += json_escape_string(msg)
        line += '"'

        if len(extra) > 0:
            line += ',"extra":"'
            line += json_escape_string(extra)
            line += '"'

        line += "}"

        print(line)


# ── Factory function ─────────────────────────────────────────────────────────


fn get_logger(name: String) -> Logger:
    """Create a Logger with INFO level.

    Args:
        name: Logger name.

    Returns:
        A Logger instance at INFO level.
    """
    return Logger(name, LOG_INFO)
