from app.services.retrieval import lexical_score, normalize_cn


def test_chinese_normalization_and_bigram_score():
    assert normalize_cn("ＩＳＯ ９００１（质量）") == "ｉｓｏ９００１(质量)"
    assert lexical_score("ISO9001质量管理体系", "质量管理体系认证 ISO9001") > 0.3
    assert lexical_score("营业执照", "人员社保") < 0.1
