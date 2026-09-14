from typing import Dict, List

from app.policy import PolicyRegistry, PolicyRule, policy_registry


class RuleChunk:
    """Backward-compatible RAG projection of a structured policy rule."""

    def __init__(self, rule_id: str, title: str, content: str):
        self.rule_id = rule_id
        self.title = title
        self.content = content

    def to_dict(self) -> Dict:
        return {
            "rule_id": self.rule_id,
            "title": self.title,
            "content": self.content,
        }


class PolicyRuleRag:
    """Keyword search backed by PolicyRegistry rather than Markdown parsing."""

    def __init__(self, registry: PolicyRegistry):
        self.registry = registry
        self.rule_chunks: List[RuleChunk] = [
            self._to_rule_chunk(rule) for rule in registry.rules
        ]

    @staticmethod
    def _to_rule_chunk(rule: PolicyRule) -> RuleChunk:
        content_parts = [rule.description]
        if rule.keywords:
            content_parts.append(f"关键词：{' '.join(rule.keywords)}")

        return RuleChunk(
            rule_id=rule.rule_id,
            title=f"{rule.rule_id} {rule.title}",
            content="\n".join(content_parts),
        )

    def search(self, query: str, top_k: int = 5) -> List[Dict]:
        keywords = [
            keyword.strip().lower()
            for keyword in query.split()
            if keyword.strip()
        ]

        results = []
        for chunk in self.rule_chunks:
            searchable_text = f"{chunk.title}\n{chunk.content}".lower()
            score = sum(searchable_text.count(keyword) for keyword in keywords)
            if score > 0:
                results.append(
                    {
                        "score": score,
                        "rule": chunk.to_dict(),
                    }
                )

        results.sort(key=lambda item: item["score"], reverse=True)
        return results[:top_k]


# Keep the public singleton name used by the API, Agent, tests, and demo script.
rule_rag = PolicyRuleRag(policy_registry)
