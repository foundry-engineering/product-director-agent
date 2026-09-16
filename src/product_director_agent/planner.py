from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable

from .contracts import (
    AcceptanceCriterion,
    DeliverableKind,
    DeliveryPlan,
    EvidenceRequirement,
    ProductBrief,
    WorkPackage,
)


_REGULATED = {
    DeliverableKind.ACCOUNTING_AUTOMATION,
    DeliverableKind.TAX_PREPARATION,
    DeliverableKind.COMPLIANCE_REVIEW,
}

_OWNER = {
    DeliverableKind.MARKET_RESEARCH: "research-compliance",
    DeliverableKind.BUSINESS_STRATEGY: "product-strategy",
    DeliverableKind.BRAND_SYSTEM: "creative-brand",
    DeliverableKind.PRODUCT_SPEC: "product-strategy",
    DeliverableKind.WEBSITE: "web-delivery",
    DeliverableKind.WEB_APP: "software-delivery",
    DeliverableKind.MOBILE_APP: "mobile-delivery",
    DeliverableKind.PITCH_DECK: "presentation-delivery",
    DeliverableKind.FINANCIAL_MODEL: "finance-modeling",
    DeliverableKind.BUSINESS_DOCUMENTATION: "documentation",
    DeliverableKind.TECHNICAL_DOCUMENTATION: "documentation",
    DeliverableKind.OPERATING_PROCEDURES: "operations-design",
    DeliverableKind.ACCOUNTING_AUTOMATION: "finance-operations",
    DeliverableKind.TAX_PREPARATION: "finance-operations",
    DeliverableKind.COMPLIANCE_REVIEW: "research-compliance",
    DeliverableKind.LAUNCH_OPERATIONS: "launch-operations",
}

_DEPENDENCIES: dict[DeliverableKind, tuple[DeliverableKind, ...]] = {
    DeliverableKind.BUSINESS_STRATEGY: (DeliverableKind.MARKET_RESEARCH,),
    DeliverableKind.BRAND_SYSTEM: (DeliverableKind.BUSINESS_STRATEGY,),
    DeliverableKind.PRODUCT_SPEC: (DeliverableKind.BUSINESS_STRATEGY,),
    DeliverableKind.WEBSITE: (DeliverableKind.BRAND_SYSTEM, DeliverableKind.PRODUCT_SPEC),
    DeliverableKind.WEB_APP: (DeliverableKind.PRODUCT_SPEC,),
    DeliverableKind.MOBILE_APP: (DeliverableKind.PRODUCT_SPEC,),
    DeliverableKind.PITCH_DECK: (
        DeliverableKind.MARKET_RESEARCH,
        DeliverableKind.BUSINESS_STRATEGY,
        DeliverableKind.BRAND_SYSTEM,
        DeliverableKind.FINANCIAL_MODEL,
    ),
    DeliverableKind.FINANCIAL_MODEL: (DeliverableKind.BUSINESS_STRATEGY,),
    DeliverableKind.BUSINESS_DOCUMENTATION: (DeliverableKind.BUSINESS_STRATEGY,),
    DeliverableKind.TECHNICAL_DOCUMENTATION: (DeliverableKind.PRODUCT_SPEC,),
    DeliverableKind.OPERATING_PROCEDURES: (
        DeliverableKind.BUSINESS_STRATEGY,
        DeliverableKind.PRODUCT_SPEC,
    ),
    DeliverableKind.ACCOUNTING_AUTOMATION: (
        DeliverableKind.OPERATING_PROCEDURES,
        DeliverableKind.COMPLIANCE_REVIEW,
    ),
    DeliverableKind.TAX_PREPARATION: (
        DeliverableKind.FINANCIAL_MODEL,
        DeliverableKind.COMPLIANCE_REVIEW,
    ),
    DeliverableKind.LAUNCH_OPERATIONS: (
        DeliverableKind.WEBSITE,
        DeliverableKind.BUSINESS_DOCUMENTATION,
        DeliverableKind.OPERATING_PROCEDURES,
    ),
}

_STANDARD_EVIDENCE: dict[DeliverableKind, tuple[EvidenceRequirement, ...]] = {
    DeliverableKind.MARKET_RESEARCH: (
        EvidenceRequirement(
            requirement_id="ev-market-sources",
            description="Material market claims must be traceable to dated external sources.",
            source_types=("primary-source", "official-statistics", "reputable-secondary-source"),
        ),
    ),
    DeliverableKind.PITCH_DECK: (
        EvidenceRequirement(
            requirement_id="ev-deck-claims",
            description="Investor-facing factual and financial claims must resolve to source or model evidence.",
            source_types=("research-dossier", "financial-model", "company-authoritative-input"),
        ),
    ),
    DeliverableKind.FINANCIAL_MODEL: (
        EvidenceRequirement(
            requirement_id="ev-finance-assumptions",
            description="Every material model assumption must be explicitly identified and sourced or marked as an assumption.",
            source_types=("company-authoritative-input", "market-evidence", "explicit-assumption"),
        ),
    ),
    DeliverableKind.COMPLIANCE_REVIEW: (
        EvidenceRequirement(
            requirement_id="ev-compliance-authority",
            description="Regulatory conclusions must cite the applicable jurisdiction and authoritative source.",
            source_types=("law", "regulator", "official-guidance"),
        ),
    ),
    DeliverableKind.TAX_PREPARATION: (
        EvidenceRequirement(
            requirement_id="ev-tax-inputs",
            description="Tax-preparation output must be based on customer-authoritative accounting data and jurisdiction-specific evidence.",
            source_types=("ledger", "invoice", "bank-evidence", "tax-authority-guidance"),
        ),
    ),
}


def _canonical_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _package_id(kind: DeliverableKind) -> str:
    return f"pkg-{kind.value}"


def _closure(requested: Iterable[DeliverableKind]) -> tuple[DeliverableKind, ...]:
    required: set[DeliverableKind] = set()

    def add(kind: DeliverableKind) -> None:
        if kind in required:
            return
        for dependency in _DEPENDENCIES.get(kind, ()):
            add(dependency)
        required.add(kind)

    for kind in requested:
        add(kind)
    return tuple(sorted(required, key=lambda item: item.value))


def _acceptance(kind: DeliverableKind) -> tuple[AcceptanceCriterion, ...]:
    base = [
        AcceptanceCriterion(
            criterion_id=f"ac-{kind.value}-complete",
            description="All declared outputs are present and machine-addressable.",
        ),
        AcceptanceCriterion(
            criterion_id=f"ac-{kind.value}-evidence",
            description="All factual assertions and quality claims required by the package resolve to evidence.",
        ),
    ]
    if kind in {DeliverableKind.WEBSITE, DeliverableKind.WEB_APP, DeliverableKind.MOBILE_APP}:
        base.extend(
            [
                AcceptanceCriterion(
                    criterion_id=f"ac-{kind.value}-qa",
                    description="Required functional, accessibility, security and regression quality gates have passed.",
                ),
                AcceptanceCriterion(
                    criterion_id=f"ac-{kind.value}-deployable",
                    description="Delivery includes a reproducible build and deployment handoff without hidden local state.",
                ),
            ]
        )
    if kind is DeliverableKind.PITCH_DECK:
        base.append(
            AcceptanceCriterion(
                criterion_id="ac-pitch-deck-consistency",
                description="Narrative, market claims and financial numbers are internally consistent across all slides.",
            )
        )
    return tuple(base)


def _outputs(kind: DeliverableKind) -> tuple[str, ...]:
    mapping: dict[DeliverableKind, tuple[str, ...]] = {
        DeliverableKind.MARKET_RESEARCH: ("evidence-backed market dossier", "competitor landscape", "market risks"),
        DeliverableKind.BUSINESS_STRATEGY: ("business model", "positioning", "pricing strategy", "go-to-market strategy"),
        DeliverableKind.BRAND_SYSTEM: ("brand strategy", "visual direction", "brand rules", "brand asset manifest"),
        DeliverableKind.PRODUCT_SPEC: ("product requirements", "user journeys", "release scope", "acceptance criteria"),
        DeliverableKind.WEBSITE: ("production website", "content manifest", "deployment package"),
        DeliverableKind.WEB_APP: ("production web application", "admin/operations surface where required", "deployment package"),
        DeliverableKind.MOBILE_APP: ("production mobile application", "store/deployment handoff", "release evidence"),
        DeliverableKind.PITCH_DECK: ("editable investor presentation", "claim/evidence register", "presentation source assets"),
        DeliverableKind.FINANCIAL_MODEL: ("financial model", "assumption register", "scenario analysis"),
        DeliverableKind.BUSINESS_DOCUMENTATION: ("business documentation set", "document index", "version manifest"),
        DeliverableKind.TECHNICAL_DOCUMENTATION: ("architecture documentation", "runbook", "integration documentation"),
        DeliverableKind.OPERATING_PROCEDURES: ("operating procedures", "control matrix", "responsibility map"),
        DeliverableKind.ACCOUNTING_AUTOMATION: ("accounting workflow specification", "integration mappings", "exception-handling rules"),
        DeliverableKind.TAX_PREPARATION: ("tax-preparation workpaper package", "source-data reconciliation", "professional-review handoff"),
        DeliverableKind.COMPLIANCE_REVIEW: ("jurisdiction-scoped compliance dossier", "obligation register", "professional-review items"),
        DeliverableKind.LAUNCH_OPERATIONS: ("launch checklist", "production-readiness evidence", "operating handoff"),
    }
    return mapping[kind]


def _inputs(kind: DeliverableKind, brief: ProductBrief) -> tuple[str, ...]:
    inputs = ["customer-authoritative product brief"]
    for dependency in _DEPENDENCIES.get(kind, ()):
        inputs.append(f"accepted output from {_package_id(dependency)}")
    if brief.evidence_refs:
        inputs.append("customer-provided evidence references")
    return tuple(inputs)


def _questions(brief: ProductBrief, expanded: tuple[DeliverableKind, ...]) -> tuple[str, ...]:
    questions: list[str] = []
    if brief.company_name is None:
        questions.append("What company or working project name should be used in customer-facing assets?")
    if not brief.jurisdictions and any(kind in _REGULATED for kind in expanded):
        questions.append("Which jurisdictions apply to regulated finance, tax or compliance work?")
    if DeliverableKind.FINANCIAL_MODEL in expanded and not brief.known_facts:
        questions.append("Which customer-authoritative commercial assumptions are available for the financial model?")
    if any(kind in expanded for kind in (DeliverableKind.WEBSITE, DeliverableKind.WEB_APP, DeliverableKind.MOBILE_APP)):
        questions.append("Which production domains, identity providers, payment providers and deployment environments are approved?")
    return tuple(questions)


def build_delivery_plan(brief: ProductBrief) -> DeliveryPlan:
    expanded = _closure(brief.requested_deliverables)
    packages: list[WorkPackage] = []
    for kind in expanded:
        dependencies = tuple(_package_id(dep) for dep in _DEPENDENCIES.get(kind, ()) if dep in expanded)
        packages.append(
            WorkPackage(
                package_id=_package_id(kind),
                deliverable=kind,
                owner_capability=_OWNER[kind],
                depends_on=dependencies,
                inputs=_inputs(kind, brief),
                outputs=_outputs(kind),
                acceptance_criteria=_acceptance(kind),
                evidence_requirements=_STANDARD_EVIDENCE.get(kind, ()),
                professional_review=(
                    "required-before-use" if kind in _REGULATED else "not-required"
                ),
            )
        )

    questions = _questions(brief, expanded)
    blocked: list[str] = []
    if any(kind in _REGULATED for kind in expanded) and not brief.jurisdictions:
        blocked.append("Regulated deliverables cannot be finalized until applicable jurisdictions are supplied.")

    material = {
        "schema_version": "foundry.delivery-plan.v1",
        "brief_id": brief.brief_id,
        "packages": [package.model_dump(mode="json") for package in packages],
        "open_questions": questions,
        "assumptions": [],
        "blocked_reasons": blocked,
    }
    plan_id = "plan-" + hashlib.sha256(_canonical_json(material).encode("utf-8")).hexdigest()[:32]
    return DeliveryPlan(plan_id=plan_id, **material)
