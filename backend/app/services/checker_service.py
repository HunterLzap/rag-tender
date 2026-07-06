"""轻量检查器接口。

先覆盖投标待办红线，后续资质核验、技术响应等模块可以按同一结果结构注册。
"""

from dataclasses import dataclass, field
from typing import Protocol

from app.services import submission_checklist_service


@dataclass
class EvidenceItem:
    """检查器输出的证据项。"""

    label: str
    status: str = "needs_review"
    detail: str | None = None
    source: str | None = None


@dataclass
class CheckContext:
    """检查器统一输入。"""

    tender_id: int


@dataclass
class CheckResult:
    """检查器统一输出。"""

    checker_id: str
    name: str
    status: str
    risk_level: str
    summary: str
    evidence: list[EvidenceItem] = field(default_factory=list)
    suggested_actions: list[str] = field(default_factory=list)


class Checker(Protocol):
    """轻量检查器协议。"""

    checker_id: str
    name: str

    async def run(self, context: CheckContext) -> CheckResult:
        """执行检查并返回统一结果。"""


class SubmissionRedFlagChecker:
    checker_id = "submission.red_flags"
    name = "投标待办红线检查"

    async def run(self, context: CheckContext) -> CheckResult:
        items = await submission_checklist_service.get_all(context.tender_id)
        red_flags = [item for item in items if "【红线】" in (item.remark or "")]
        unfinished = [item for item in red_flags if item.status != "done"]
        evidence = [
            EvidenceItem(
                label=item.item_name,
                status="pass" if item.status == "done" else "needs_review",
                detail=item.remark,
                source=f"submission_checklist:{item.id}",
            )
            for item in red_flags
        ]
        status = "pass" if not unfinished else "needs_review"
        risk_level = "high" if unfinished else "low"
        return CheckResult(
            checker_id=self.checker_id,
            name=self.name,
            status=status,
            risk_level=risk_level,
            summary=f"发现 {len(red_flags)} 条红线待办，其中 {len(unfinished)} 条未完成。",
            evidence=evidence,
            suggested_actions=["逐项确认红线待办，完成后更新状态。"] if unfinished else [],
        )


_CHECKERS: dict[str, Checker] = {
    SubmissionRedFlagChecker.checker_id: SubmissionRedFlagChecker(),
}


def list_checkers() -> list[dict[str, str]]:
    """返回已注册检查器。"""
    return [{"checker_id": checker.checker_id, "name": checker.name} for checker in _CHECKERS.values()]


async def run_checkers(
    context: CheckContext,
    checker_ids: list[str] | None = None,
) -> list[CheckResult]:
    """按 ID 执行检查器；未指定时执行全部检查器。"""
    selected_ids = checker_ids or list(_CHECKERS)
    results: list[CheckResult] = []
    for checker_id in selected_ids:
        checker = _CHECKERS.get(checker_id)
        if checker is None:
            continue
        results.append(await checker.run(context))
    return results
