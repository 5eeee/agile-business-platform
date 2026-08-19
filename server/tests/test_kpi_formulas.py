import os
import unittest
from datetime import datetime
from decimal import Decimal

os.environ.setdefault("DEBUG", "true")

from app.services.kpi_calculator import (
    calculate_working_days,
    calculate_working_hours,
    punctuality_score,
)
from app.services.s3 import _decrypt, _encrypt
from app.api.kpi_workflows import _validate_report


class KPIPureFormulaTests(unittest.TestCase):
    def test_kpi2_progressive_scale(self):
        expected = {
            Decimal("0"): Decimal("100"),
            Decimal("1"): Decimal("95"),
            Decimal("2"): Decimal("90"),
            Decimal("3"): Decimal("85"),
            Decimal("4"): Decimal("75"),
            Decimal("5"): Decimal("70"),
            Decimal("6"): Decimal("60"),
            Decimal("12"): Decimal("60"),
        }
        for points, score in expected.items():
            with self.subTest(points=points):
                self.assertEqual(punctuality_score(points), score)

    def test_five_consecutive_lates_add_thirty_point_penalty(self):
        self.assertEqual(punctuality_score(Decimal("5"), 5), Decimal("40"))

    def test_workday_excludes_lunch(self):
        start = datetime(2026, 8, 17, 9, 0)  # Monday
        end = datetime(2026, 8, 17, 18, 0)
        self.assertEqual(calculate_working_hours(start, end), Decimal("8.00"))
        self.assertEqual(calculate_working_days(start, end), Decimal("1.0"))

    def test_weekend_is_paused(self):
        start = datetime(2026, 8, 21, 17, 0)  # Friday
        end = datetime(2026, 8, 24, 10, 0)  # Monday
        self.assertEqual(calculate_working_hours(start, end), Decimal("2.00"))

    def test_private_file_payload_is_encrypted_and_authenticated(self):
        source = b"private task document"
        key = "tasks/00000000-0000-0000-0000-000000000001/file.pdf"
        encrypted = _encrypt(source, key)
        self.assertNotIn(source, encrypted)
        self.assertEqual(_decrypt(encrypted, key), source)
        with self.assertRaises(Exception):
            _decrypt(encrypted[:-1] + bytes([encrypted[-1] ^ 1]), key)

    def test_weekly_report_requires_five_detailed_criteria_and_three_plans(self):
        invalid = {"criteria": {"1": "коротко", "2": "", "3": "нет", "4": "один пункт", "5": "нет"}}
        self.assertGreaterEqual(len(_validate_report(invalid)), 5)

        valid = {
            "criteria": {
                "1": "Выполнены все задачи недельного плана",
                "2": "В работе остаётся итоговая аналитика",
                "3": "Просроченных задач за неделю нет",
                "4": "Проверить API\nПровести тестирование\nПодготовить отчёт",
                "5": "Критических проблем и рисков сейчас нет",
                "6": "Улучшить автоматический контроль отчётов",
            },
            "initiative_sphere": "process",
        }
        self.assertEqual(_validate_report(valid), [])


if __name__ == "__main__":
    unittest.main()
