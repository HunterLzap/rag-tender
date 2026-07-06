"""规则库路由。"""

import logging

from fastapi import APIRouter
from pydantic import BaseModel

from app.services import rule_library_service
from app.utils.api_response import ErrorCode, error_response, success_response

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/rules", tags=["规则库"])


class RuleEnabledUpdate(BaseModel):
    enabled: bool
    reason: str | None = None


class RuleSuggestionReviewUpdate(BaseModel):
    review_status: str
    review_reason: str | None = None


class RuleDraftReviewUpdate(BaseModel):
    draft_status: str
    review_reason: str | None = None
    similar_rule_ids: list[str] | None = None
    difference_reason: str | None = None


class RuleDraftUpdate(BaseModel):
    name: str
    rule_type: str
    draft_content: str
    edit_reason: str | None = None


class RuleDraftReuseUpdate(BaseModel):
    target_rule_id: str
    reason: str | None = None


class RuleTemplateDraftCreate(BaseModel):
    reason: str | None = None


class RuleMergeUpdate(BaseModel):
    target_rule_id: str
    reason: str | None = None


class CustomRuleUpdate(BaseModel):
    name: str
    rule_type: str
    description: str
    edit_reason: str | None = None


class RuleRollbackUpdate(BaseModel):
    version_no: int
    reason: str | None = None


@router.get("", summary="获取规则库目录")
async def get_rule_catalog() -> dict:
    """返回当前系统内置规则目录。"""
    try:
        return success_response(data=await rule_library_service.list_rule_catalog_with_overrides())
    except Exception as e:
        logger.error("获取规则库失败: %s", str(e))
        return error_response(ErrorCode.INTERNAL_SERVER_ERROR, f"获取规则库失败: {str(e)}")


@router.get("/templates", summary="获取规则参考模板")
async def get_rule_templates() -> dict:
    """返回成熟标书分析场景中的参考模板，不直接作为生效规则。"""
    try:
        return success_response(data=rule_library_service.list_rule_templates())
    except Exception as e:
        logger.error("获取规则参考模板失败: %s", str(e))
        return error_response(ErrorCode.INTERNAL_SERVER_ERROR, f"获取规则参考模板失败: {str(e)}")


@router.post("/templates/{template_id}/draft", summary="从规则模板生成草案")
async def create_rule_draft_from_template(template_id: str, req: RuleTemplateDraftCreate) -> dict:
    """从参考模板生成待审核规则草案，不直接发布为生效规则。"""
    try:
        result = await rule_library_service.create_rule_draft_from_template(
            template_id,
            req.reason,
        )
        if result is None:
            return error_response(ErrorCode.PARAM_VALIDATION_FAILED, "模板不存在或使用原因缺失")
        return success_response(data=result, message="规则模板已生成待审核草案")
    except Exception as e:
        logger.error("从规则模板生成草案失败: template_id=%s, error=%s", template_id, str(e))
        return error_response(ErrorCode.INTERNAL_SERVER_ERROR, f"从规则模板生成草案失败: {str(e)}")


@router.get("/{rule_id}/relations", summary="获取规则关系")
async def get_rule_relations(rule_id: str) -> dict:
    """返回某条规则的复用、相似等追溯关系。"""
    try:
        return success_response(data=await rule_library_service.list_rule_relations(rule_id))
    except Exception as e:
        logger.error("获取规则关系失败: rule_id=%s, error=%s", rule_id, str(e))
        return error_response(ErrorCode.INTERNAL_SERVER_ERROR, f"获取规则关系失败: {str(e)}")


@router.get("/{rule_id}/versions", summary="获取规则版本历史")
async def get_rule_versions(rule_id: str) -> dict:
    """返回自定义规则的历史版本。"""
    try:
        return success_response(data=await rule_library_service.list_rule_versions(rule_id))
    except Exception as e:
        logger.error("获取规则版本历史失败: rule_id=%s, error=%s", rule_id, str(e))
        return error_response(ErrorCode.INTERNAL_SERVER_ERROR, f"获取规则版本历史失败: {str(e)}")


@router.put("/{rule_id}/merge", summary="归并自定义规则")
async def merge_custom_rule(rule_id: str, req: RuleMergeUpdate) -> dict:
    """将一条重复自定义规则归并到另一条已存在规则，并停用源规则。"""
    try:
        result = await rule_library_service.merge_custom_rule(
            rule_id,
            req.target_rule_id,
            req.reason,
        )
        if result is None:
            return error_response(ErrorCode.PARAM_VALIDATION_FAILED, "源规则或目标规则不存在，或源规则不可归并")
        return success_response(data=result, message="规则已归并")
    except Exception as e:
        logger.error("归并规则失败: rule_id=%s, error=%s", rule_id, str(e))
        return error_response(ErrorCode.INTERNAL_SERVER_ERROR, f"归并规则失败: {str(e)}")


@router.put("/{rule_id}/rollback", summary="回滚自定义规则")
async def rollback_custom_rule(rule_id: str, req: RuleRollbackUpdate) -> dict:
    """将自定义规则恢复到某个历史版本，并保存回滚前内容。"""
    try:
        result = await rule_library_service.rollback_custom_rule(
            rule_id,
            req.version_no,
            req.reason,
        )
        if result is None:
            return error_response(ErrorCode.PARAM_VALIDATION_FAILED, "规则不存在、版本不存在或回滚原因缺失")
        return success_response(data=result, message="规则已回滚")
    except Exception as e:
        logger.error("回滚自定义规则失败: rule_id=%s, error=%s", rule_id, str(e))
        return error_response(ErrorCode.INTERNAL_SERVER_ERROR, f"回滚自定义规则失败: {str(e)}")


@router.put("/{rule_id}", summary="编辑自定义规则")
async def update_custom_rule(rule_id: str, req: CustomRuleUpdate) -> dict:
    """编辑已发布自定义规则，并保存修改前版本。"""
    try:
        result = await rule_library_service.update_custom_rule(
            rule_id,
            req.name,
            req.rule_type,
            req.description,
            req.edit_reason,
        )
        if result is None:
            return error_response(ErrorCode.PARAM_VALIDATION_FAILED, "规则不存在、不是自定义规则或修改原因缺失")
        return success_response(data=result, message="规则已更新")
    except Exception as e:
        logger.error("编辑自定义规则失败: rule_id=%s, error=%s", rule_id, str(e))
        return error_response(ErrorCode.INTERNAL_SERVER_ERROR, f"编辑自定义规则失败: {str(e)}")


@router.put("/{rule_id}/enabled", summary="更新规则启停状态")
async def update_rule_enabled(rule_id: str, req: RuleEnabledUpdate) -> dict:
    """更新单条内置规则启停状态。"""
    try:
        result = await rule_library_service.update_rule_enabled(
            rule_id,
            req.enabled,
            req.reason,
        )
        if result is None:
            return error_response(ErrorCode.PARAM_VALIDATION_FAILED, "规则不存在")
        return success_response(data=result, message="规则状态已更新")
    except Exception as e:
        logger.error("更新规则启停失败: rule_id=%s, error=%s", rule_id, str(e))
        return error_response(ErrorCode.INTERNAL_SERVER_ERROR, f"更新规则失败: {str(e)}")


@router.get("/changes", summary="获取规则变更记录")
async def get_rule_change_logs(limit: int = 100) -> dict:
    """返回规则启停变更记录。"""
    try:
        return success_response(data=await rule_library_service.list_rule_change_logs(limit))
    except Exception as e:
        logger.error("获取规则变更记录失败: %s", str(e))
        return error_response(ErrorCode.INTERNAL_SERVER_ERROR, f"获取规则变更记录失败: {str(e)}")


@router.get("/suggestions", summary="获取规则候选建议")
async def get_rule_suggestions(limit: int = 100) -> dict:
    """从人工错例中生成规则候选建议。"""
    try:
        return success_response(data=await rule_library_service.list_rule_suggestions(limit))
    except Exception as e:
        logger.error("获取规则候选建议失败: %s", str(e))
        return error_response(ErrorCode.INTERNAL_SERVER_ERROR, f"获取规则候选建议失败: {str(e)}")


@router.put("/suggestions/{suggestion_id}/review", summary="处理规则候选建议")
async def review_rule_suggestion(
    suggestion_id: str,
    req: RuleSuggestionReviewUpdate,
) -> dict:
    """记录规则建议的采纳/忽略状态。"""
    try:
        result = await rule_library_service.review_rule_suggestion(
            suggestion_id,
            req.review_status,
            req.review_reason,
        )
        if result is None:
            return error_response(ErrorCode.PARAM_VALIDATION_FAILED, "建议处理状态无效")
        return success_response(data=result, message="规则建议处理状态已更新")
    except Exception as e:
        logger.error("处理规则候选建议失败: suggestion_id=%s, error=%s", suggestion_id, str(e))
        return error_response(ErrorCode.INTERNAL_SERVER_ERROR, f"处理规则建议失败: {str(e)}")


@router.get("/drafts", summary="获取规则草案")
async def get_rule_drafts(limit: int = 100) -> dict:
    """返回由已采纳建议生成的规则草案。"""
    try:
        return success_response(data=await rule_library_service.list_rule_drafts(limit))
    except Exception as e:
        logger.error("获取规则草案失败: %s", str(e))
        return error_response(ErrorCode.INTERNAL_SERVER_ERROR, f"获取规则草案失败: {str(e)}")


@router.put("/drafts/{draft_id}", summary="编辑规则草案")
async def update_rule_draft(draft_id: int, req: RuleDraftUpdate) -> dict:
    """编辑待审核规则草案，已发布/已驳回草案不可直接修改。"""
    try:
        result = await rule_library_service.update_rule_draft(
            draft_id,
            req.name,
            req.rule_type,
            req.draft_content,
            req.edit_reason,
        )
        if result is None:
            return error_response(ErrorCode.PARAM_VALIDATION_FAILED, "规则草案不存在、已发布或内容无效")
        return success_response(data=result, message="规则草案已更新")
    except Exception as e:
        logger.error("编辑规则草案失败: draft_id=%s, error=%s", draft_id, str(e))
        return error_response(ErrorCode.INTERNAL_SERVER_ERROR, f"编辑规则草案失败: {str(e)}")


@router.get("/drafts/{draft_id}/similar", summary="检测规则草案相似规则")
async def get_similar_rules_for_draft(draft_id: int, limit: int = 10) -> dict:
    """发布草案前检测相似内置规则、自定义规则和其他草案。"""
    try:
        result = await rule_library_service.list_similar_rules_for_draft(draft_id, limit)
        if result is None:
            return error_response(ErrorCode.PARAM_VALIDATION_FAILED, "规则草案不存在")
        return success_response(data=result)
    except Exception as e:
        logger.error("检测相似规则失败: draft_id=%s, error=%s", draft_id, str(e))
        return error_response(ErrorCode.INTERNAL_SERVER_ERROR, f"检测相似规则失败: {str(e)}")


@router.put("/drafts/{draft_id}/reuse", summary="复用已有规则")
async def reuse_existing_rule_for_draft(draft_id: int, req: RuleDraftReuseUpdate) -> dict:
    """将待审核草案关联到已有规则，避免重复发布。"""
    try:
        result = await rule_library_service.reuse_existing_rule_for_draft(
            draft_id,
            req.target_rule_id,
            req.reason,
        )
        if result is None:
            return error_response(ErrorCode.PARAM_VALIDATION_FAILED, "规则草案或目标规则不存在，或草案状态不可复用")
        return success_response(data=result, message="已复用已有规则")
    except Exception as e:
        logger.error("复用已有规则失败: draft_id=%s, error=%s", draft_id, str(e))
        return error_response(ErrorCode.INTERNAL_SERVER_ERROR, f"复用已有规则失败: {str(e)}")


@router.put("/drafts/{draft_id}/review", summary="审核规则草案")
async def review_rule_draft(draft_id: int, req: RuleDraftReviewUpdate) -> dict:
    """发布或驳回规则草案。"""
    try:
        result = await rule_library_service.review_rule_draft(
            draft_id,
            req.draft_status,
            req.review_reason,
            req.similar_rule_ids,
            req.difference_reason,
        )
        if result is None:
            return error_response(ErrorCode.PARAM_VALIDATION_FAILED, "规则草案不存在或状态无效")
        return success_response(data=result, message="规则草案审核状态已更新")
    except Exception as e:
        logger.error("审核规则草案失败: draft_id=%s, error=%s", draft_id, str(e))
        return error_response(ErrorCode.INTERNAL_SERVER_ERROR, f"审核规则草案失败: {str(e)}")
