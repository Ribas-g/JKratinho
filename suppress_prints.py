"""
Utilitário para suprimir prints durante execução
Útil para evitar erros de encoding com emojis
"""
import sys
import io
from contextlib import contextmanager

@contextmanager
def suppress_stdout():
    """Context manager para suprimir stdout temporariamente"""
    old_stdout = sys.stdout
    sys.stdout = io.StringIO()
    try:
        yield
    finally:
        sys.stdout = old_stdout

@contextmanager
def redirect_stdout_to_stderr():
    """Context manager para redirecionar stdout para stderr (menos provável de ter problema de encoding)"""
    old_stdout = sys.stdout
    sys.stdout = sys.stderr
    try:
        yield
    finally:
        sys.stdout = old_stdout


