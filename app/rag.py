import re
from typing import List, Dict
from pathlib import Path

from app.config import settings



RULE_HEADER_PATTERN = re.compile(r"^###\s+(R-[A-Z]+-\d+)\s+(.+?)\s*$")



class RuleChunk:
    # 表示一个规则块

    def __init__(
            self,
            rule_id: str,
            title: str,
            content: str,
    ):
        self.rule_id = rule_id
        self.title = title
        self.content = content

    def to_dict(self) -> Dict:
        return {
            "rule_id": self.rule_id,
            "title": self.title,
            "content": self.content
        }



class MarkdownRuleRag:
    # mvp关键词版本rag
    # 功能：
    # 1. 读取markdown文件
    # 2. 切分规则块
    # 3. 建立简单文本索引
    # 4. 关键词检索


    def __init__(self, markdown_path: str):
        self.markdown_path = Path(markdown_path)

        self.rule_chunks: List[RuleChunk] = []

        self._load_rules()


    def _load_rules(self) -> None:
        # 加载并且切分Markdown规则文件
        if not self.markdown_path.exists():
            raise FileNotFoundError(f"Markdown file not found: {self.markdown_path}")

        markdown_text = self.markdown_path.read_text(
            encoding="utf-8"
            )

        lines = markdown_text.splitlines()

        current_rule_id = None
        current_title = None
        current_content_lines = []

        for line in lines:
            header_match = RULE_HEADER_PATTERN.match(line)

            if header_match:
                if current_rule_id is not None and current_title is not None:
                    self._append_rule_chunk(
                        current_rule_id,
                        current_title,
                        current_content_lines
                    )

                current_rule_id = header_match.group(1).strip()
                current_title = (
                    f"{current_rule_id} {header_match.group(2).strip()}"
                )
                current_content_lines = []
            elif current_title is not None:
                if line.startswith("### ") or line.startswith("## ") or line.strip() == "---":
                    self._append_rule_chunk(
                        current_rule_id,
                        current_title,
                        current_content_lines
                    )
                    current_rule_id = None
                    current_title = None
                    current_content_lines = []
                else:
                    current_content_lines.append(line)

        if current_rule_id is not None and current_title is not None:
            self._append_rule_chunk(
                current_rule_id,
                current_title,
                current_content_lines
            )


    def _append_rule_chunk(
            self,
            rule_id: str,
            title: str,
            content_lines: List[str]
    ) -> None:
        # 创建RuleChunk并添加到列表中

        content = "\n".join(content_lines).strip()

        chunk = RuleChunk(
            rule_id=rule_id,
            title=title,
            content=content
        )

        self.rule_chunks.append(chunk)

    def search(
            self,
            query: str,
            top_k: int = 5
    ) -> List[Dict]:
        # 基于关键词的简单规则检索
        # 当前策略：
        # 1. query分词
        # 2. 在title + content中统计关键词出现次数
        # 3. 根据出现次数排序返回top_k条规则

        keywords = [
            keyword.strip().lower()
            for keyword in query.split()
            if keyword.strip()
        ]

        results = []

        for chunk in self.rule_chunks:
            searchable_text = (
                f"{chunk.title}\n{chunk.content}"
            ).lower()
            score = 0

            for keyword in keywords:
                score += searchable_text.count(keyword)

            if score > 0:
                results.append(
                    {
                        "score": score,
                        "rule": chunk.to_dict()
                    }
                )

        results.sort(
            key=lambda item: item["score"],
            reverse=True
        )

        return results[:top_k]


rule_rag = MarkdownRuleRag(
    markdown_path=settings.rules_markdown_path
)
