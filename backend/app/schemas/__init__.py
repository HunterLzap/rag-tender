"""Schema 包，导出所有 Pydantic 请求/响应 schema。"""

from app.schemas.common import ApiResponse
from app.schemas.config_schema import (
    ApiConfigCreate,
    ApiConfigResponse,
    ProviderPresetResponse,
    TestConnectionRequest,
    TestConnectionResponse,
)
from app.schemas.knowledge import (
    KnowledgeFileResponse,
    QualificationCreate,
    QualificationResponse,
    QualificationUpdate,
)
from app.schemas.match import (
    MatchConfirmRequest,
    MatchResultResponse,
)
from app.schemas.tender import (
    TenderDetail,
    TenderRequirementUpdate,
    TenderUploadResponse,
)

__all__ = [
    # common
    "ApiResponse",
    # config
    "ApiConfigCreate",
    "ApiConfigResponse",
    "ProviderPresetResponse",
    "TestConnectionRequest",
    "TestConnectionResponse",
    # tender
    "TenderUploadResponse",
    "TenderDetail",
    "TenderRequirementUpdate",
    # knowledge
    "KnowledgeFileResponse",
    "QualificationCreate",
    "QualificationResponse",
    "QualificationUpdate",
    # match
    "MatchResultResponse",
    "MatchConfirmRequest",
]
