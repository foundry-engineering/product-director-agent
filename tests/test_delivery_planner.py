from __future__ import annotations

from product_director_agent.contracts import DeliverableKind, ProductBrief
from product_director_agent.planner import build_delivery_plan


def _brief(*deliverables: DeliverableKind, jurisdictions: tuple[str, ...] = ()) -> ProductBrief:
    return ProductBrief(
        brief_id="brief-enterprise-001",
        company_name=None,
        idea="Build a premium B2B software company with a website, product and investor materials.",
        target_users=("operations leaders",),
        business_goals=("launch a sellable company",),
        requested_deliverables=deliverables,
        jurisdictions=jurisdictions,
        constraints=("do not invent customer financial facts",),
    )


def test_full_launch_request_expands_required_dependencies() -> None:
    plan = build_delivery_plan(
        _brief(
            DeliverableKind.WEBSITE,
            DeliverableKind.WEB_APP,
            DeliverableKind.PITCH_DECK,
            DeliverableKind.BUSINESS_DOCUMENTATION,
            DeliverableKind.LAUNCH_OPERATIONS,
        )
    )
    kinds = {package.deliverable for package in plan.packages}
    assert DeliverableKind.MARKET_RESEARCH in kinds
    assert DeliverableKind.BUSINESS_STRATEGY in kinds
    assert DeliverableKind.BRAND_SYSTEM in kinds
    assert DeliverableKind.PRODUCT_SPEC in kinds
    assert DeliverableKind.FINANCIAL_MODEL in kinds
    assert DeliverableKind.WEBSITE in kinds
    assert DeliverableKind.WEB_APP in kinds
    assert DeliverableKind.PITCH_DECK in kinds


def test_plan_identity_is_deterministic() -> None:
    brief = _brief(DeliverableKind.WEBSITE, DeliverableKind.PITCH_DECK)
    first = build_delivery_plan(brief)
    second = build_delivery_plan(brief)
    assert first == second
    assert first.plan_id.startswith("plan-")


def test_regulated_work_is_blocked_without_jurisdiction_and_requires_review() -> None:
    plan = build_delivery_plan(_brief(DeliverableKind.TAX_PREPARATION))
    assert plan.blocked_reasons
    tax = next(package for package in plan.packages if package.deliverable is DeliverableKind.TAX_PREPARATION)
    compliance = next(
        package for package in plan.packages if package.deliverable is DeliverableKind.COMPLIANCE_REVIEW
    )
    assert tax.professional_review == "required-before-use"
    assert compliance.professional_review == "required-before-use"


def test_regulated_work_can_be_planned_when_jurisdiction_is_explicit() -> None:
    plan = build_delivery_plan(
        _brief(DeliverableKind.ACCOUNTING_AUTOMATION, jurisdictions=("AT",))
    )
    assert not plan.blocked_reasons
    assert any("jurisdiction" not in question.lower() for question in plan.open_questions) or not plan.open_questions


def test_pitch_deck_requires_evidence_backed_market_and_financial_inputs() -> None:
    plan = build_delivery_plan(_brief(DeliverableKind.PITCH_DECK))
    deck = next(package for package in plan.packages if package.deliverable is DeliverableKind.PITCH_DECK)
    requirement_ids = {item.requirement_id for item in deck.evidence_requirements}
    assert "ev-deck-claims" in requirement_ids
    dependencies = set(deck.depends_on)
    assert "pkg-market-research" in dependencies
    assert "pkg-financial-model" in dependencies


def test_planner_does_not_turn_missing_customer_facts_into_assumptions() -> None:
    plan = build_delivery_plan(_brief(DeliverableKind.FINANCIAL_MODEL))
    assert plan.assumptions == ()
    assert any("commercial assumptions" in question for question in plan.open_questions)
