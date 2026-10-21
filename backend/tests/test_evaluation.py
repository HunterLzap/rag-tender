from app.services.evaluation import match_expected


class FakeRequirement:
    def __init__(self, statement, located=True):
        self.statement = statement
        self.source_span_id = "span" if located else None


def test_match_expected_recall_and_location():
    result = match_expected(
        [
            FakeRequirement("注册资本不少于人民币 1000 万元"),
            FakeRequirement("ISO9001 质量管理体系认证", located=False),
        ],
        [
            {"statement": "注册资本不少于人民币 1000 万元"},
            {"statement": "ISO14001 环境管理体系认证"},
        ],
    )
    assert result["matched_count"] == 1
    assert result["recall"] == 0.5
    assert result["location_rate"] == 0.5
