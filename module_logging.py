"""
Legacy logging module.

Раньше этот файл глобально подменял sys.stdout и писал всё в output.log в корне проекта.
Для параллельных UID-задач это опасно (логи смешиваются), поэтому теперь:
- глобальные файлы логов не создаём
- per-task вывод делается через task_runtime.print_router (регистрация файла на thread задачи)
"""

from task_runtime.print_router import install_print_router

# Важно: безопасно вызывать много раз
install_print_router()