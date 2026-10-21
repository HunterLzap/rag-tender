import pytest
from sqlalchemy import select

from app.domain.document_ir import ParsedBlock, ParsedDocument, ParsedPage
from app.models import AnalysisRun, Document, Project, Requirement, SourceSpan
from app.services import extraction, model_gateway
from app.services.ir_persistence import persist_parsed_document


async def test_only_truncation_splits_batches(monkeypatch):
    class Block:
        def __init__(self, block_id):
            self.id = block_id

    blocks = [Block(str(index)) for index in range(4)]
    calls = []

    async def fake_extract(_session, *, blocks, **_kwargs):
        calls.append(len(blocks))
        if len(blocks) > 2:
            raise model_gateway.ModelOutputTruncated("output length")
        return extraction.ExtractedRequirements()

    monkeypatch.setattr(extraction, "_extract_batch", fake_extract)
    await extraction._extract_bounded_batch(None, blocks=blocks)
    assert calls == [4, 2, 2]

    async def network_error(_session, *, blocks, **_kwargs):
        calls.append(len(blocks))
        raise model_gateway.ModelGatewayError("network error")

    calls.clear()
    monkeypatch.setattr(extraction, "_extract_batch", network_error)
    with pytest.raises(model_gateway.ModelGatewayError, match="network error"):
        await extraction._extract_bounded_batch(None, blocks=blocks)
    assert calls == [4]


async def test_structured_output_does_not_repeat_truncated_requests(monkeypatch):
    calls = []

    async def truncated(*_args, **_kwargs):
        calls.append(1)
        raise model_gateway.ModelOutputTruncated("output length")

    monkeypatch.setattr(model_gateway, "complete_text", truncated)
    with pytest.raises(model_gateway.ModelOutputTruncated):
        await model_gateway.structured_text(
            None,
            system="",
            user="",
            output_model=extraction.ExtractedRequirements,
            purpose="test",
        )
    assert len(calls) == 1


async def test_validated_page_survives_later_page_failure(session, monkeypatch):
    project = Project(name="partial extraction")
    session.add(project)
    await session.flush()
    document = Document(
        project_id=project.id,
        role="tender",
        filename="partial.pdf",
        storage_path="unused",
        sha256="c" * 64,
        file_size=0,
    )
    session.add(document)
    await session.flush()
    parsed = ParsedDocument(
        pages=tuple(
            ParsedPage(
                page_index=index,
                width=600,
                height=800,
                text="须提交 营业执照。",
                blocks=(ParsedBlock("line", "须提交 营业执照。", (50, 50, 200, 70), 0),),
            )
            for index in range(2)
        )
    )
    await persist_parsed_document(session, document, parsed)
    run = AnalysisRun(project_id=project.id)
    session.add(run)
    await session.commit()
    run_id = run.id

    async def fake_extract(_session, *, page, blocks, **_kwargs):
        if page.page_index == 1:
            raise model_gateway.ModelGatewayError("second page failed")
        return extraction.ExtractedRequirements(
            requirements=[
                extraction.ExtractedRequirement(
                    title="营业执照",
                    statement="须提交营业执照",
                    block_id=blocks[0].id,
                    quote="须提交营业执照",
                )
            ]
        )

    monkeypatch.setattr(extraction, "_extract_batch", fake_extract)
    with pytest.raises(model_gateway.ModelGatewayError, match="second page failed"):
        await extraction.extract_requirements_for_run(session, run)
    await session.rollback()
    requirement = (
        await session.execute(select(Requirement).where(Requirement.run_id == run_id))
    ).scalar_one()
    span = await session.get(SourceSpan, requirement.source_span_id)
    assert span.quote == "须提交 营业执照"
    assert span.char_start == 0
    assert span.char_end == len(span.quote)
