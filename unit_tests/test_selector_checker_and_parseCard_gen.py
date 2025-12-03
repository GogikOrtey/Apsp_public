import sys
import os
import unittest

# Добавляем путь к корню проекта (чтобы найти MainFuncAgent)
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from MainFuncAgent import selector_checker_and_parseCard_gen

class TestSelectorCheckerAndParseCardGen(unittest.TestCase):
    def setUp(self):
        # Пример данных, которые будут использоваться во многих тестах
        self.data_input_table = {
            "host": "",
            "links": {
                "simple": [
                    {"InStock_trigger": "есть на складе"},
                    {"InStock_trigger": "есть на складе"},
                ]
            },
            "search_requests": []
        }

    def test_no_stock_triggers(self):
        """Проверяет случай, когда нет триггеров наличия"""
        result_selectors = {"name": "h1", "price": ".p"}
        result = selector_checker_and_parseCard_gen(result_selectors, self.data_input_table)
        self.assertIn('const stock = "InStock"', result)

    def test_only_instock_trigger(self):
        """Проверяет, если есть только InStock_trigger"""
        result_selectors = {
            "name": "h1",
            "price": ".p",
            "InStock_trigger": ".instock"
        }
        result = selector_checker_and_parseCard_gen(result_selectors, self.data_input_table)
        # Должен использовать константу const stock = ...
        self.assertIn('const stock', result)
        self.assertIn('InStock', result)

    def test_only_outofstock_trigger(self):
        """Проверяет, если есть только OutOfStock_trigger"""
        result_selectors = {
            "name": "h1",
            "price": ".p",
            "OutOfStock_trigger": ".outstock"
        }
        result = selector_checker_and_parseCard_gen(result_selectors, self.data_input_table)
        self.assertIn('OutOfStock', result)
        self.assertIn('const stock', result)

    def test_both_triggers_equal(self):
        """Если оба триггера одинаковы, используется InStock"""
        result_selectors = {
            "name": "h1",
            "price": ".p",
            "InStock_trigger": ".same",
            "OutOfStock_trigger": ".same"
        }
        result = selector_checker_and_parseCard_gen(result_selectors, self.data_input_table)
        self.assertIn('.same', result)
        self.assertIn('const stock', result)

    def test_multiple_instock_texts(self):
        """Если несколько разных InStock_trigger'ов в data_input_table"""
        data_input_table = {
            "links": {
                "simple": [
                    {"InStock_trigger": "есть на складе"},
                    {"InStock_trigger": "в наличии"},
                ]
            },
            "search_requests": []
        }
        result_selectors = {
            "name": "h1",
            "price": ".p",
            "InStock_trigger": ".nal"
        }
        result = selector_checker_and_parseCard_gen(result_selectors, data_input_table)
        # Должен использовать массив строк с some()
        self.assertIn('.some(', result)
        self.assertIn('"есть на складе"', result)
        self.assertIn('"в наличии"', result)

    def test_return_contains_cheerio_load(self):
        """Проверяет, что шаблон содержит cheerio.load(data)"""
        result_selectors = {"name": "h1", "price": ".p"}
        result = selector_checker_and_parseCard_gen(result_selectors, self.data_input_table)
        self.assertIn("cheerio.load(data)", result)

if __name__ == '__main__':
    unittest.main()
