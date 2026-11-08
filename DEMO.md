```bash
python -m pytest -q tests/test_call_evaluation.py -k test_cancelled_appointment_full_flow -s
```

Анализаторът отчита анулирания час и как judge проверява дали цитатът подкрепя крайния статус.

```bash
python -m pytest -q tests/test_call_evaluation.py -k test_judge_rejects_irrelevant_evidence -s
```

Judge отхвърля цитат, който описва повредата и не подкрепя статуса.

```bash
python -m json.tool data/judge_validation.json | grep -F -A 13 '"id": "cancelled_visit_confirmation_evidence"'
```

Фиксирания регресионен случай за анулирания час и очакваните оценки.

```bash
python -m pytest -q
```

Обобщението на тестовете и регресионните случаи.

**Следваща стъпка.** Да се добави случай с анулиране и потвърден нов час, за да проверим дали judge отхвърля цитата за старото анулиране като доказателство за новата резервация.
