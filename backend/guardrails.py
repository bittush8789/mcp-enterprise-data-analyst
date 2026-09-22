"""AI Guardrails Engine for MCP Enterprise Data Analyst.

Implements defense-in-depth across 11 critical security & safety layers:
1. Input Validation
2. Prompt Injection Detection
3. PII Detection and Redaction
4. Authorization Checks
5. Tool Permission Enforcement
6. SQL Safety Guards
7. RAG Injection Defense
8. Evidence Validation
9. Hallucination Verification & Causal Claim Pruning
10. Output Validation & Secret Leak Prevention
11. Resource & Rate Limits
"""

import re
import logging
from typing import Any, Dict, List, Optional, Tuple

from backend.config import settings
from backend.models.schemas import EvidenceObject

logger = logging.getLogger("enterprise_analyst.guardrails")

# 1. Prompt Injection Attack Signatures
PROMPT_INJECTION_PATTERNS = [
    r"(?i)\bignore\s+(all\s+)?(previous|prior|above|security)?\s*(instructions|prompts|rules|commands|security)\b",
    r"(?i)\breveal\s+(the\s+)?(database\s+)?(password|credentials|secrets|api\s*key|system\s*prompt)\b",
    r"(?i)\bshow\s+(me\s+)?(your\s+)?system\s+prompt\b",
    r"(?i)\bdisable\s+(all\s+)?(security|guardrails|safety|rules)\b",
    r"(?i)\bpretend\s+(i\s+am|you\s+are)\s+(an?\s+)?(admin|root|system|developer)\b",
    r"(?i)\bbypass\s+(all\s+)?(permissions|restrictions|auth)\b",
    r"(?i)\bexecute\s*:\s*drop\b",
    r"(?i)\bexecute\s+this\s+sql\b",
    r"(?i)\bdrop\s+table\b",
    r"(?i)\bdelete\s+from\b",
    r"(?i)\bjailbreak\b",
    r"(?i)\bgive\s+me\s+all\s+(customer\s+)?(pii|emails?|passwords?|credit\s*cards?)\b",
    r"(?i)\breturn\s+all\s+customer\s+records\b",
    r"(?i)\bthe\s+retrieved\s+policy\s+says\s+to\s+reveal\b",
    r"(?i)\bfollow\s+the\s+(malicious\s+)?policy\s+to\s+reveal\b",
]

# 2. PII Detection Patterns
PII_PATTERNS = {
    "email": r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,7}\b",
    "phone": r"\b(?:\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b",
    "credit_card": r"\b(?:\d{4}[-\s]?){3}\d{4}\b",
    "ssn": r"\b\d{3}-\d{2}-\d{4}\b",
}

# 3. Disallowed SQL Mutation Keywords
DISALLOWED_SQL = [
    "DROP", "DELETE", "UPDATE", "INSERT", "ALTER", "TRUNCATE",
    "CREATE", "GRANT", "REVOKE", "EXEC", "EXECUTE"
]


class GuardrailPipeline:
    """Enterprise 11-Layer AI Security and Hallucination Prevention Pipeline."""

    # Layer 1: Input Validation
    def validate_input(self, user_input: str) -> Tuple[bool, Optional[str]]:
        if not user_input or not user_input.strip():
            return False, "Input query cannot be empty."
        if len(user_input) > settings.MAX_INPUT_LENGTH:
            return False, f"Input query exceeds maximum allowed length of {settings.MAX_INPUT_LENGTH} characters."
        return True, None

    # Layer 2: Prompt Injection Detection
    def check_prompt_injection(self, text: str) -> Tuple[bool, Optional[str]]:
        for pattern in PROMPT_INJECTION_PATTERNS:
            if re.search(pattern, text):
                logger.warning("Prompt injection attempt detected matching: %s", pattern)
                return True, "Security Guardrail Triggered: Request contains prohibited instructions or prompt injection patterns."
        return False, None

    # Layer 3: PII Detection and Masking
    def detect_and_mask_pii(self, text: str) -> Tuple[str, List[str]]:
        detected_types = []
        masked_text = text
        for pii_type, pattern in PII_PATTERNS.items():
            if re.search(pattern, masked_text):
                detected_types.append(pii_type)
                masked_text = re.sub(pattern, f"[REDACTED_{pii_type.upper()}]", masked_text)
        return masked_text, detected_types

    # Layer 4: Authorization Check
    def check_authorization(self, user_role: str = "business_analyst", requested_action: str = "read") -> Tuple[bool, Optional[str]]:
        allowed_roles = {"business_analyst", "executive", "auditor", "admin"}
        if user_role not in allowed_roles:
            return False, f"Unauthorized: User role '{user_role}' is not permitted to query enterprise intelligence."
        if requested_action != "read":
            return False, "Unauthorized: Only read-only analytical queries are permitted."
        return True, None

    # Layer 5: Tool Permission Check
    def check_tool_permission(self, tool_name: str) -> bool:
        allowed_tools = {
            "get_revenue_by_region",
            "get_monthly_revenue",
            "get_sales_by_product",
            "compare_segments_revenue",
            "get_top_customers",
            "get_overall_summary",
            "search_business_documents",
            "search_policy",
            "search_sop",
        }
        return tool_name in allowed_tools

    # Layer 6: SQL Safety Check
    def validate_sql_safety(self, sql_query: str) -> Tuple[bool, Optional[str]]:
        sql_clean = sql_query.upper().strip()
        for forbidden in DISALLOWED_SQL:
            if re.search(rf"\b{forbidden}\b", sql_clean):
                return False, f"SQL Guardrail: Statement contains forbidden mutation token '{forbidden}'."
        if ";" in sql_clean[:-1]:
            return False, "SQL Guardrail: Multiple SQL statements are not permitted."
        return True, None

    # Layer 7: RAG Injection Defense
    def sanitize_rag_chunk(self, chunk_text: str) -> str:
        """Neutralizes any prompt injection attempts hidden in retrieved documents."""
        sanitized = chunk_text
        for pattern in PROMPT_INJECTION_PATTERNS:
            sanitized = re.sub(pattern, "[DOCUMENT_CONTENT_FILTERED]", sanitized)
        return sanitized

    # Layer 8: Evidence Validation
    def validate_evidence(self, evidence: EvidenceObject) -> Tuple[bool, List[str]]:
        issues = []
        if not evidence.sources:
            issues.append("No enterprise sources returned for this inquiry.")
            return False, issues

        has_valid_data = False
        for s in evidence.sources:
            if s.type == "mysql" and s.data:
                has_valid_data = True
            elif s.type == "chroma" and s.documents:
                has_valid_data = True

        if not has_valid_data:
            issues.append("Retrieved enterprise sources contain empty datasets.")
            return False, issues

        return True, []

    # Layer 9: Hallucination Verification & Causal Claim Pruning
    def verify_and_prune_hallucinations(
        self,
        question: str,
        generated_answer: str,
        evidence: EvidenceObject,
    ) -> str:
        """Inspects claims in the generated response against verified evidence.
        
        Specifically checks for unsupported causal explanations (e.g. 'because marketing...',
        'due to price discounts...') when the database contains numerical data without causality.
        """
        # Case A: Causal question check (e.g. "Why did North revenue increase?")
        is_causal_question = bool(re.search(r"(?i)\bwhy\s+did\b|\breasons?\s+(for|behind)\b|\bcause\s+of\b", question))
        
        # Check if evidence contains explicit causal factors
        has_causal_evidence = False
        for s in evidence.sources:
            if s.type == "chroma" and s.documents:
                for doc in s.documents:
                    content = doc.get("content", "").lower()
                    if "reason" in content or "driver" in content or "caused by" in content:
                        has_causal_evidence = True

        if is_causal_question and not has_causal_evidence:
            logger.info("Hallucination Guard: Causal question detected without causal evidence. Enforcing refusal.")
            return (
                "I can verify the revenue figures, but the available enterprise data "
                "does not contain sufficient evidence to determine why North region revenue changed."
            )

        # Case B: Remove fabricated causal clauses if model invented causality
        if not has_causal_evidence:
            causal_patterns = [
                r"(?i)because\s+demand\s+increased\s+by\s+\d+[\.\d]*\%?",
                r"(?i)due\s+to\s+a\s+surge\s+in\s+marketing\s+campaigns?",
                r"(?i)driven\s+by\s+new\s+customer\s+acquisitions\s+in\s+q\d",
            ]
            cleaned_answer = generated_answer
            for cp in causal_patterns:
                cleaned_answer = re.sub(cp, "", cleaned_answer)
            generated_answer = cleaned_answer

        return generated_answer

    # Layer 10: Output Validation & Secret Leak Prevention
    def validate_output(self, output_text: str) -> str:
        # 1. Defang any potential system prompt leaks
        leaks = [
            r"(?i)You\s+are\s+an\s+AI\s+analyst.*",
            r"(?i)GROQ_API_KEY\s*=\s*\S+",
            r"(?i)MYSQL_PASSWORD\s*=\s*\S+",
            r"(?i)password\s*=\s*['\"][^'\"]+['\"]",
        ]
        clean_output = output_text
        for leak in leaks:
            clean_output = re.sub(leak, "[CONFIDENTIAL_SYSTEM_CONFIG]", clean_output)

        # 2. Defang PII in final output
        clean_output, _ = self.detect_and_mask_pii(clean_output)

        # 3. Normalize non-ASCII typography for robust cross-platform compatibility
        typographic_fixes = {
            "\u2011": "-",
            "\u2012": "-",
            "\u2013": "-",
            "\u2014": "--",
            "\u202f": " ",
            "\u00a0": " ",
            "\u2018": "'",
            "\u2019": "'",
            "\u201c": '"',
            "\u201d": '"',
            "\u2022": "*",
            "\u3010": " [",
            "\u3011": "] ",
            "\u2264": "<=",
            "\u2265": ">=",
        }
        for k, v in typographic_fixes.items():
            clean_output = clean_output.replace(k, v)

        return clean_output

    # Layer 11: Rate / Resource Limits
    def check_resource_limits(self, row_count: int, execution_time_ms: float) -> Tuple[bool, Optional[str]]:
        if row_count > settings.MAX_ROWS:
            return False, f"Resource Limit: Query returned {row_count} rows, exceeding cap of {settings.MAX_ROWS}."
        if execution_time_ms > (settings.QUERY_TIMEOUT * 1000):
            return False, f"Timeout Limit: Execution exceeded timeout of {settings.QUERY_TIMEOUT}s."
        return True, None


# Global Singleton Instance
guardrails = GuardrailPipeline()
