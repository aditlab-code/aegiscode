#!/usr/bin/env python
"""Django management utility untuk Aegis Gateway (#50).

Gateway HTTP tipis menuju Aegis. Django HANYA bertugas sebagai HTTP layer:
    HTTP request -> API validation -> Aegis service/facade -> response

Tidak ada logic Agent/Runtime/Planning/Tool di sini.
"""

import os
import sys


def main() -> None:
    """Jalankan administrative tasks."""
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:  # pragma: no cover
        raise ImportError(
            "Tidak dapat mengimpor Django. Pastikan Django terpasang "
            "(pip install Django)."
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
