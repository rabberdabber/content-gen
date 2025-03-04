"""
This file defines the schemas for the post content for AI content generation 
using OpenAI structured outputs (Tiptap style).
"""
from typing import Literal

from pydantic import BaseModel

# =====================
# MARKS
# =====================

class BoldMark(BaseModel):
    type: Literal["bold"]

class ItalicMark(BaseModel):
    type: Literal["italic"]

class UnderlineMark(BaseModel):
    type: Literal["underline"]

class StrikeMark(BaseModel):
    type: Literal["strike"]

class SubscriptMark(BaseModel):
    type: Literal["subscript"]

class HighlightMarkAttrs(BaseModel):
    color: str | None = None

class HighlightMark(BaseModel):
    type: Literal["highlight"]
    attrs: HighlightMarkAttrs

class LinkMarkAttrs(BaseModel):
    href: str
    target: str | None = None

class LinkMark(BaseModel):
    type: Literal["link"]
    attrs: LinkMarkAttrs

# Union of all possible marks
AllMarks = (
    BoldMark |
    ItalicMark |
    UnderlineMark |
    StrikeMark |
    SubscriptMark |
    HighlightMark |
    LinkMark
)

# =====================
# CONTENT NODES
# =====================

class TextNode(BaseModel):
    type: Literal["text"]
    text: str
    # Add the marks field:
    marks: list[AllMarks]

class ImageNode(BaseModel):
    type: Literal["imageBlock"]
    src: str
    alt: str

class CodeBlockAttributes(BaseModel):
    language: Literal[
        "python",
        "javascript",
        "typescript",
        "java",
        "c",
        "cpp",
        "ruby",
        "go",
        "rust",
        "html",
        "css",
        "sql",
        "shell",
        "markdown",
        "json",
        "yaml",
        "xml"
    ]

class CodeBlockNode(BaseModel):
    type: Literal["codeBlock"]
    attrs: CodeBlockAttributes
    content: list[TextNode]

class HeadingAttributes(BaseModel):
    textAlign: Literal["left"]
    level: Literal[1, 2, 3, 4, 5, 6]

class ParagraphAttributes(BaseModel):
    textAlign: Literal["left"]

class ParagraphNode(BaseModel):
    type: Literal["paragraph"]
    attrs: ParagraphAttributes
    content: list[TextNode]

class HeadingNode(BaseModel):
    type: Literal["heading"]
    attrs: HeadingAttributes
    content: list[TextNode]

class ListItemNode(BaseModel):
    type: Literal["listItem"]
    content: list[ParagraphNode]

class OrderedListNode(BaseModel):
    type: Literal["orderedList"]
    content: list[ListItemNode]

class BulletListNode(BaseModel):
    type: Literal["bulletList"]
    content: list[ListItemNode]

class TableRowNode(BaseModel):
    type: Literal["tableRow"]
    content: list["TableCellNode"]  # forward reference if needed

class TableCellNode(BaseModel):
    type: Literal["tableCell"]
    # If you want to allow paragraph or text content, adapt accordingly
    content: list[ParagraphNode]

class TableNode(BaseModel):
    type: Literal["table"]
    content: list[TableRowNode]

class PostContent(BaseModel):
    type: Literal["doc"]
    content: list[
        HeadingNode | ParagraphNode | CodeBlockNode | BulletListNode | OrderedListNode | TableNode
    ]

class DraftContentRequest(BaseModel):
    prompt: str

# If you're using forward references, you might need:
# PostContent.update_forward_refs()
# TableRowNode.update_forward_refs()
