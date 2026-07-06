"""业绩项目本地解析测试。"""

from app.services.performance_project_service import parse_performance_projects_from_text


def test_parse_annual_performance_table_from_ocr_text() -> None:
    projects = parse_performance_projects_from_text(
        """
        [第1页]
        业 绩 表
        序号 发包方 工程名称 工程内容 工程地点 合同价
        1 上海晶成建筑安装工程有限公司 嘉定赛车场 配电箱 上海 14.05W
        2 上海自立塑料科技有限公司 自立工厂 打包带控制柜 上海 5.68W
        3 诚荣和电气科技（上海）有限公司 中石油 动力柜 南通 7.3W
        4 镇江鸿鑫智能制造装备有限公司 阿里数据中心 变频动力柜 河北 49W
        """,
        filename="业绩表2026年.pdf",
        file_id=189,
    )

    assert len(projects) == 4
    assert projects[0]["client_name"] == "上海晶成建筑安装工程有限公司"
    assert projects[0]["project_name"] == "嘉定赛车场"
    assert projects[0]["project_scope"] == "配电箱；地点：上海"
    assert projects[0]["contract_amount"] == "14.05万"
    assert projects[0]["year"] == "2026"
    assert projects[0]["file_ids"] == [189]

    assert projects[3]["client_name"] == "镇江鸿鑫智能制造装备有限公司"
    assert projects[3]["project_name"] == "阿里数据中心"
    assert projects[3]["project_scope"] == "变频动力柜；地点：河北"
    assert projects[3]["contract_amount"] == "49万"


def test_parse_wrapped_project_name_line() -> None:
    projects = parse_performance_projects_from_text(
        """
        序号 发包方 工程名称 工程内容 工程地点 合同价
        8 上海林伟建筑工程有限公司 生物医药科研仪器研
        发制造基地项目
        配电动力柜 上海 34W
        """,
        filename="业绩表2026年.pdf",
        file_id=189,
    )

    assert len(projects) == 1
    assert projects[0]["project_name"] == "生物医药科研仪器研发制造基地项目"
    assert projects[0]["project_scope"] == "配电动力柜；地点：上海"
    assert projects[0]["contract_amount"] == "34万"


if __name__ == "__main__":
    test_parse_annual_performance_table_from_ocr_text()
    test_parse_wrapped_project_name_line()
    print("performance project parsing tests passed")
