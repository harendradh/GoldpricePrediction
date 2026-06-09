"""Skills · the reusable building blocks every agent calls.

All skills self-register on import. Skills are stateless · each `run()`
takes a SkillContext and returns a SkillResult.
"""
from skills.base import Skill, get_skill_registry, register_skill
# Each skill module self-registers on import
from skills import (
    code_quality,                # noqa: F401
    security_scan,               # noqa: F401
    performance_analysis,        # noqa: F401
    architecture_validation,     # noqa: F401
    test_coverage_analysis,      # noqa: F401
    dependency_audit,            # noqa: F401
    configuration_validation,    # noqa: F401
    database_migration,          # noqa: F401
    api_contract_validation,     # noqa: F401
    error_handling_review,       # noqa: F401
    concurrency_analysis,        # noqa: F401
    resource_management,         # noqa: F401
    documentation_quality,       # noqa: F401
    cab_section_generation,      # noqa: F401
    scorecard_narration,         # noqa: F401
    risk_assessment,             # noqa: F401
    governance_compliance,       # noqa: F401
)

__all__ = ["Skill", "get_skill_registry", "register_skill"]
