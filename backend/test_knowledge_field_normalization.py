"""知识库资质字段归一化测试。"""

import os
import sys
import asyncio

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.services.knowledge_service import (
    _build_extract_qualification_prompt,
    _extract_qualification_from_text_locally,
    _extract_personnel_qualification_from_text,
    _extract_pdf_text_with_ocr_fallback,
    build_placeholder_qualification,
    has_meaningful_qualification_data,
    normalize_qualification_field,
)


def test_normalize_qualification_field_keeps_plain_values() -> None:
    assert normalize_qualification_field("高新技术企业证书") == "高新技术企业证书"
    assert normalize_qualification_field(12345) == "12345"
    assert normalize_qualification_field(None) is None


def test_normalize_qualification_field_joins_list_values() -> None:
    assert normalize_qualification_field(["江苏省科学技术厅", "江苏省财政厅"]) == (
        "江苏省科学技术厅、江苏省财政厅"
    )


def test_normalize_qualification_field_serializes_dict_values() -> None:
    assert normalize_qualification_field({"机关": "江苏省科学技术厅", "级别": "省级"}) == (
        '{"机关": "江苏省科学技术厅", "级别": "省级"}'
    )


def test_all_empty_qualification_data_is_not_meaningful() -> None:
    assert not has_meaningful_qualification_data(
        {
            "name": None,
            "number": None,
            "issue_date": None,
            "expiry_date": None,
            "issuing_authority": None,
            "scope": None,
            "level": None,
            "holder": None,
        }
    )


def test_filename_placeholder_qualification_marks_manual_completion_needed() -> None:
    placeholder = build_placeholder_qualification(
        filename="项目经理身份证.pdf",
        reason="PDF 未提取到可解析文本",
        category="personnel",
    )

    assert placeholder["name"] == "身份证明"
    assert placeholder["scope"] == "待人工补全：PDF 未提取到可解析文本"
    assert placeholder["holder"] is None
    assert placeholder["number"] is None


def test_personnel_placeholder_infers_social_security_material_type() -> None:
    placeholder = build_placeholder_qualification(
        filename="刘伟养老保险.docx",
        reason="Office 转 PDF 后未提取到可解析文本",
        category="personnel",
    )

    assert placeholder["name"] == "社保证明"
    assert placeholder["holder"] == "刘伟"
    assert placeholder["scope"] == "待人工补全：Office 转 PDF 后未提取到可解析文本"


def test_personnel_placeholder_does_not_treat_region_and_numbers_as_holder() -> None:
    placeholder = build_placeholder_qualification(
        filename="上海市社会保险个人社保参保证明20260408131206.pdf",
        reason="历史解析返回全空字段",
        category="personnel",
    )

    assert placeholder["name"] == "社保证明"
    assert placeholder["holder"] is None


def test_personnel_extract_prompt_mentions_social_security_materials() -> None:
    prompt = _build_extract_qualification_prompt(
        "上海市社会保险个人社保参保证明\n姓名：刘伟\n缴费年月：2026-04",
        category="personnel",
        filename="上海市社会保险个人社保参保证明20260408131206.pdf",
    )

    assert "人员资质/人员证明材料" in prompt
    assert "社保证明" in prompt
    assert "身份证明" in prompt
    assert "职称/资格证明" in prompt


def test_pdf_text_with_ocr_fallback_uses_vision_pages_when_text_layer_empty() -> None:
    async def run_case() -> None:
        import app.services.knowledge_service as service

        original_extract_pdf_text = service.extract_pdf_text
        original_extract_pdf_with_pages = service.extract_pdf_with_pages
        original_ocr_vision_pages = service.ocr_vision_pages
        try:
            async def fake_extract_pdf_text(pdf_path: str) -> str:
                return ""

            async def fake_extract_pdf_with_pages(pdf_path: str) -> list[dict]:
                return [
                    {"page": 1, "content": None, "char_count": 0, "parse_mode": "vision"},
                    {"page": 2, "content": "已有文字", "char_count": 4, "parse_mode": "text"},
                ]

            async def fake_ocr_vision_pages(pdf_path: str, pages: list[int]) -> dict[int, str]:
                assert pages == [1]
                return {1: "姓名：刘伟\n公民身份号码：310000000000000000"}

            service.extract_pdf_text = fake_extract_pdf_text
            service.extract_pdf_with_pages = fake_extract_pdf_with_pages
            service.ocr_vision_pages = fake_ocr_vision_pages

            text = await _extract_pdf_text_with_ocr_fallback("scan.pdf")
        finally:
            service.extract_pdf_text = original_extract_pdf_text
            service.extract_pdf_with_pages = original_extract_pdf_with_pages
            service.ocr_vision_pages = original_ocr_vision_pages

        assert "[第1页]" in text
        assert "姓名：刘伟" in text
        assert "[第2页]" in text
        assert "已有文字" in text

    asyncio.run(run_case())


def test_extract_personnel_identity_card_from_ocr_text_without_llm() -> None:
    result = _extract_personnel_qualification_from_text(
        """
        姓名 宋建
        性别 男 民族 汉
        出生 1984年2月3日
        住址 江苏省泰兴市广陵镇兴宁村二十一组10号
        公民身份号码 321283198402031031
        中华人民共和国 居民身份证
        签发机关 泰兴市公安局
        有效期 2018.10.16-2038.10.16
        """,
        filename="项目经理身份证.pdf",
    )

    assert result is not None
    assert result["name"] == "身份证明"
    assert result["holder"] == "宋建"
    assert result["number"] == "321283198402031031"
    assert result["issue_date"] == "2018-10-16"
    assert result["expiry_date"] == "2038-10-16"
    assert result["issuing_authority"] == "泰兴市公安局"


def test_extract_personnel_social_security_from_text_without_llm() -> None:
    result = _extract_personnel_qualification_from_text(
        """
        上海市社会保险个人社保参保证明
        姓名：刘伟
        证件号码：310101198001010011
        参保单位：上海某某有限公司
        缴费年月：2024年01月至2026年04月
        出具日期：2026年04月08日
        """,
        filename="上海市社会保险个人社保参保证明20260408131206.pdf",
    )

    assert result is not None
    assert result["name"] == "社保证明"
    assert result["holder"] == "刘伟"
    assert result["number"] == "310101198001010011"
    assert result["issue_date"] == "2026-04-08"
    assert "上海某某有限公司" in result["scope"]


def test_extract_personnel_identity_card_name_without_space() -> None:
    result = _extract_personnel_qualification_from_text(
        "姓名宋建性别男民族汉公民身份号码321283198402031031签发机关泰兴市公安局有效期2018.10.16-2038.10.16",
        filename="项目经理身份证.pdf",
    )

    assert result is not None
    assert result["holder"] == "宋建"


def test_extract_personnel_identity_card_name_with_inner_space() -> None:
    result = _extract_personnel_qualification_from_text(
        "姓名 宋 建 性别 男 民族 汉 公民身份号码321283198402031031签发机关泰兴市公安局有效期2018.10.16-2038.10.16",
        filename="项目经理身份证.pdf",
    )

    assert result is not None
    assert result["holder"] == "宋建"


def test_extract_special_operation_certificate_from_ocr_text_without_llm() -> None:
    result = _extract_personnel_qualification_from_text(
        """
        A31000032323073858
        T320682199203125632
        刘伟 电工作业
        男 低压电工作业
        2023-04-14 2023-04-14至2029-04-13
        2026-04-13前 上海市应急管理局
        备注：本证书应于2026-04-13前进行复审
        """,
        filename="低压电工作业证.pdf",
    )

    assert result is not None
    assert result["name"] == "特种作业操作证（低压电工作业）"
    assert result["number"] == "A31000032323073858"
    assert result["holder"] == "刘伟"
    assert result["issue_date"] == "2023-04-14"
    assert result["expiry_date"] == "2029-04-13"
    assert result["issuing_authority"] == "上海市应急管理局"
    assert result["scope"] == "低压电工作业"


def test_extract_personnel_title_certificate_from_ocr_text_without_llm() -> None:
    result = _extract_personnel_qualification_from_text(
        """
        Full Name: 宋建
        Professional Field 电气工程
        Qualification Title 助理工程师
        ID No. 321283198402031031
        Certificate No. AZC2024005
        Issuing Authority 上海市安装行业协会
        Issue Date 2024年12月25日
        """,
        filename="职称证明.docx",
    )

    assert result is not None
    assert result["name"] == "助理工程师"
    assert result["number"] == "AZC2024005"
    assert result["holder"] == "宋建"
    assert result["issue_date"] == "2024-12-25"
    assert result["issuing_authority"] == "上海市安装行业协会"
    assert result["scope"] == "电气工程"


def test_extract_personnel_diploma_from_ocr_text_without_llm() -> None:
    result = _extract_personnel_qualification_from_text(
        """
        毕业证书
        学生 宋建 系 江苏省泰兴市人，性别 男，于一九九八年九月至二00一年七月在本校建筑工程技术专业学习。
        编号 2001 字642828号
        毕业学校：苏州市轻工业学校
        二00一年七月一日
        """,
        filename="华业证书.pdf",
    )

    assert result is not None
    assert result["name"] == "毕业证书"
    assert result["number"] == "2001字642828号"
    assert result["holder"] == "宋建"
    assert result["issuing_authority"] == "苏州市轻工业学校"
    assert result["scope"] == "建筑工程技术专业"


def test_extract_enterprise_iso_certificate_from_text_without_llm() -> None:
    result = _extract_qualification_from_text_locally(
        """
        质量管理体系认证证书
        证书编号：331240449
        兹证明 上海某某科技有限公司 质量管理体系符合 GB/T19001-2016/ISO9001:2015 标准
        认证范围：配电柜、控制柜的生产和销售
        发证日期：2024年05月20日
        有效期至：2027年05月19日
        发证机构：中国质量认证中心
        """,
        category="enterprise",
        filename="ISO9001质量管理体系认证_331240449.pdf",
    )

    assert result is not None
    assert result["name"] == "质量管理体系认证证书"
    assert result["number"] == "331240449"
    assert result["holder"] == "上海某某科技有限公司"
    assert result["issue_date"] == "2024-05-20"
    assert result["expiry_date"] == "2027-05-19"
    assert result["issuing_authority"] == "中国质量认证中心"
    assert result["scope"] == "配电柜、控制柜的生产和销售"


def test_extract_enterprise_high_tech_certificate_from_text_without_llm() -> None:
    result = _extract_qualification_from_text_locally(
        """
        高新技术企业证书
        企业名称：上海某某科技有限公司
        证书编号：GR202231005683
        发证时间：2022年11月15日
        有效期：三年
        批准机关：上海市科学技术委员会 上海市财政局 国家税务总局上海市税务局
        """,
        category="enterprise",
        filename="高新技术企业证书_GR202231005683.png",
    )

    assert result is not None
    assert result["name"] == "高新技术企业证书"
    assert result["number"] == "GR202231005683"
    assert result["holder"] == "上海某某科技有限公司"
    assert result["issue_date"] == "2022-11-15"
    assert result["issuing_authority"] == "上海市科学技术委员会上海市财政局国家税务总局上海市税务局"


def test_extract_financial_audit_report_from_text_without_llm() -> None:
    result = _extract_qualification_from_text_locally(
        """
        审计报告
        被审计单位：上海某某科技有限公司
        报告编号：XYZH/2024/审字第001号
        审计年度：2023年度
        出具日期：2024年04月20日
        会计师事务所：上海某某会计师事务所
        营业收入 1234.56万元
        资产总额 5000万元
        """,
        category="financial",
        filename="2023年度审计报告.pdf",
    )

    assert result is not None
    assert result["name"] == "审计报告"
    assert result["number"] == "XYZH/2024/审字第001号"
    assert result["holder"] == "上海某某科技有限公司"
    assert result["issue_date"] == "2024-04-20"
    assert result["issuing_authority"] == "上海某某会计师事务所"
    assert "2023年度" in result["scope"]
    assert "营业收入1234.56万元" in result["scope"]


def test_extract_financial_statement_from_text_without_llm() -> None:
    result = _extract_qualification_from_text_locally(
        """
        资产负债表 会小企01表
        税款所属期起止:2025-10-01 至 2025-12-31
        纳税人识别号:91310114769674792P 报送日期:2026-01-18
        纳税人名称:上海苏靖机电工程有限公司 单位：元
        资产总计 30 15,247,974.77
        利润表 会小企02表
        一、营业收入 1 12,982,335.15
        """,
        category="financial",
        filename="202512小企业会计准则财务会计报告报送（季报）112252.pdf",
    )

    assert result is not None
    assert result["name"] == "财务会计报告（季报）"
    assert result["number"] == "2025-10-01至2025-12-31"
    assert result["issue_date"] == "2026-01-18"
    assert result["holder"] == "上海苏靖机电工程有限公司"
    assert "资产总计15247974.77元" in result["scope"]
    assert "营业收入12982335.15元" in result["scope"]


def test_extract_tax_authority_when_label_value_is_wrapped() -> None:
    result = _extract_qualification_from_text_locally(
        """
        中 华 人 民 共 和 国
        税 收 完 税 证 明
        填发日期： 2026 年 4 月 3 日 税务机关：
        纳税人识别号 91310114769674792P 纳税人名称 上海苏靖机电工程有限公司
        原凭证号 税种 品目名称 税款所属时期 入(退)库日期 实缴(退)金额
        No.431015251200054444
        国家税务总局上海市嘉定区税务局
        431016251200086192 企业职工基本养老保险费 2025-11-01至2025-11-30
        税务机关
        （盖章）
        """,
        category="financial",
        filename="完税证明f91a7f89f4f34d53a18d187630962c99.pdf",
    )

    assert result is not None
    assert result["name"] == "纳税证明"
    assert result["issuing_authority"] == "国家税务总局上海市嘉定区税务局"
    assert result["holder"] == "上海苏靖机电工程有限公司"


def test_extract_enterprise_software_copyright_from_text_without_llm() -> None:
    result = _extract_qualification_from_text_locally(
        """
        计算机软件著作权登记证书
        软件名称：光伏电能制氢柜应用控制软件V1.0
        著作权人：上海某某科技有限公司
        登记号：2024SR0541480
        证书号：软著登字第12945353号
        发证日期：2024年04月22日
        发证机关：中华人民共和国国家版权局
        权利取得方式：原始取得
        权利范围：全部权利
        """,
        category="enterprise",
        filename="软著_光伏电能制氢柜应用控制软件V1.0_2024SR0541480.png",
    )

    assert result is not None
    assert result["name"] == "计算机软件著作权登记证书"
    assert result["number"] == "2024SR0541480"
    assert result["holder"] == "上海某某科技有限公司"
    assert result["issue_date"] == "2024-04-22"
    assert "光伏电能制氢柜应用控制软件V1.0" in result["scope"]


def test_extract_enterprise_test_report_from_text_without_llm() -> None:
    result = _extract_qualification_from_text_locally(
        """
        检测报告
        报告编号：WTCT251810
        样品名称：配电控制柜
        检测项目：外壳防护等级 IP65
        签发日期：2025年09月29日
        检测机构：安徽中质电科检测有限公司
        """,
        category="enterprise",
        filename="IP65等级检测报告.pdf",
    )

    assert result is not None
    assert result["name"] == "检测报告"
    assert result["number"] == "WTCT251810"
    assert result["issue_date"] == "2025-09-29"
    assert result["issuing_authority"] == "安徽中质电科检测有限公司"
    assert result["level"] == "IP65"


def test_extract_enterprise_bank_account_license_from_text_without_llm() -> None:
    result = _extract_qualification_from_text_locally(
        """
        开户许可证
        存款人名称：上海某某科技有限公司
        核准号：J290002140648
        开户银行：中国工商银行股份有限公司上海市罗店支行
        发证日期：2013年09月05日
        账户性质：基本存款账户
        """,
        category="enterprise",
        filename="开户许可证_工商银行罗店支行.png",
    )

    assert result is not None
    assert result["name"] == "开户许可证"
    assert result["number"] == "J290002140648"
    assert result["holder"] == "上海某某科技有限公司"
    assert result["issuing_authority"] == "中国工商银行股份有限公司上海市罗店支行"


if __name__ == "__main__":
    test_normalize_qualification_field_keeps_plain_values()
    test_normalize_qualification_field_joins_list_values()
    test_normalize_qualification_field_serializes_dict_values()
    test_all_empty_qualification_data_is_not_meaningful()
    test_filename_placeholder_qualification_marks_manual_completion_needed()
    test_personnel_placeholder_infers_social_security_material_type()
    test_personnel_placeholder_does_not_treat_region_and_numbers_as_holder()
    test_personnel_extract_prompt_mentions_social_security_materials()
    test_pdf_text_with_ocr_fallback_uses_vision_pages_when_text_layer_empty()
    test_extract_personnel_identity_card_from_ocr_text_without_llm()
    test_extract_personnel_social_security_from_text_without_llm()
    test_extract_personnel_identity_card_name_without_space()
    test_extract_personnel_identity_card_name_with_inner_space()
    test_extract_special_operation_certificate_from_ocr_text_without_llm()
    test_extract_personnel_title_certificate_from_ocr_text_without_llm()
    test_extract_personnel_diploma_from_ocr_text_without_llm()
    test_extract_enterprise_iso_certificate_from_text_without_llm()
    test_extract_enterprise_high_tech_certificate_from_text_without_llm()
    test_extract_financial_audit_report_from_text_without_llm()
    test_extract_financial_statement_from_text_without_llm()
    test_extract_enterprise_software_copyright_from_text_without_llm()
    test_extract_enterprise_test_report_from_text_without_llm()
    test_extract_enterprise_bank_account_license_from_text_without_llm()
    print("knowledge field normalization tests passed")
