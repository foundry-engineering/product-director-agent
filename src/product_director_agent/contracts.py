from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


NonEmpty = Annotated[str, Field(min_length=1, max_length=4000)]
Identifier = Annotated[str, Field(pattern=r"^[a-z0-9][a-z0-9._-]{2,127}$")]


class DeliverableKind(StrEnum):
    MARKET_RESEARCH = "market-research"
    BUSINESS_STRATEGY = "business-strategy"
    BRAND_SYSTEM = "brand-system"
    PRODUCT_SPEC = "product-spec"
    WEBSITE = "website"
    WEB_APP = "web-app"
    MOBILE_APP = "mobile-app"
    PITCH_DECK = "pitch-deck"
    FINANCIAL_MODEL = "financial-model"
    BUSINESS_DOCUMENTATION = "business-documentation"
    TECHNICAL_DOCUMENTATION = "technical-documentation"
    OPERATING_PROCEDURES = "operating-procedures"
    ACCOUNTING_AUTOMATION = "accounting-automation"
    TAX_PREPARATION = "tax-preparation"
    COMPLIANCE_REVIEW = "compliance-review"
    LAUNCH_OPERATIONS = "launch-operations"


class EvidenceRequirement(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    requirement_id: Identifier
    description: NonEmpty
    required: bool = True
    source_types: tuple[str, ...] = ()

    @field_validator("source_types")
    @classmethod
    def _unique_sources(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        normalized = tuple(sorted({item.strip() for item in value if item.strip()}))
        return normalized


class ProductBrief(BaseModel):
    """Customer-authoritative input. Missing facts stay missing; they are never inferred as truth."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    brief_id: Identifier
    company_name: str | None = Field(default=None, max_length=300)
    idea: NonEmpty
    target_users: tuple[NonEmpty, ...]
    business_goals: tuple[NonEmpty, ...]
    requested_deliverables: tuple[DeliverableKind, ...]
    jurisdictions: tuple[str, ...] = ()
    constraints: tuple[NonEmpty, ...] = ()
    known_facts: tuple[NonEmpty, ...] = ()
    evidence_refs: tuple[str, ...] = ()

    @field_validator("target_users", "business_goals", "requested_deliverables")
    @classmethod
    def _non_empty_tuple(cls, value: tuple[object, ...]) -> tuple[object, ...]:
        if not value:
            raise ValueError("field must contain at least one item")
        return value

    @field_validator("requested_deliverables")
    @classmethod
    def _unique_deliverables(
        cls, value: tuple[DeliverableKind, ...]
    ) -> tuple[DeliverableKind, ...]:
        if len(set(value)) != len(value):
            raise ValueError("requested_deliverables must be unique")
        return value

    @field_validator("jurisdictions")
    @classmethod
    def _jurisdictions(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        normalized = tuple(sorted({item.strip() for item in value if item.strip()}))
        return normalized


class AcceptanceCriterion(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    criterion_id: Identifier
    description: NonEmpty
    evidence_required: bool = True


class WorkPackage(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    package_id: Identifier
    deliverable: DeliverableKind
    owner_capability: Identifier
    depends_on: tuple[Identifier, ...] = ()
    inputs: tuple[NonEmpty, ...]
    outputs: tuple[NonEmpty, ...]
    acceptance_criteria: tuple[AcceptanceCriterion, ...]
    evidence_requirements: tuple[EvidenceRequirement, ...] = ()
    professional_review: Literal["not-required", "required-before-use"] = "not-required"

    @model_validator(mode="after")
    def _validate_self_dependency(self) -> "WorkPackage":
        if self.package_id in self.depends_on:
            raise ValueError("work package cannot depend on itself")
        if not self.inputs or not self.outputs or not self.acceptance_criteria:
            raise ValueError("work package must define inputs, outputs and acceptance criteria")
        return self


class DeliveryPlan(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["foundry.delivery-plan.v1"] = "foundry.delivery-plan.v1"
    plan_id: Identifier
    brief_id: Identifier
    packages: tuple[WorkPackage, ...]
    open_questions: tuple[NonEmpty, ...]
    assumptions: tuple[NonEmpty, ...] = ()
    blocked_reasons: tuple[NonEmpty, ...] = ()

    @model_validator(mode="after")
    def _validate_graph(self) -> "DeliveryPlan":
        ids = [package.package_id for package in self.packages]
        if len(ids) != len(set(ids)):
            raise ValueError("package ids must be unique")
        known = set(ids)
        for package in self.packages:
            unknown = set(package.depends_on) - known
            if unknown:
                raise ValueError(f"unknown work-package dependency: {sorted(unknown)}")
        visiting: set[str] = set()
        visited: set[str] = set()
        graph = {package.package_id: package.depends_on for package in self.packages}

        def visit(node: str) -> None:
            if node in visiting:
                raise ValueError("work-package dependency cycle detected")
            if node in visited:
                return
            visiting.add(node)
            for dependency in graph[node]:
                visit(dependency)
            visiting.remove(node)
            visited.add(node)

        for node in graph:
            visit(node)
        return self
