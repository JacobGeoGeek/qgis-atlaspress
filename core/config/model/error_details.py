from dataclasses import dataclass


@dataclass
class ErrorDetails:
    path: str
    message: str
