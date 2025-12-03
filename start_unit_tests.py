import unittest

# Автоматически ищет и запускает все юнит-тесты
loader = unittest.TestLoader()
suite = loader.discover("unit_tests")

runner = unittest.TextTestRunner(verbosity=2)
runner.run(suite)