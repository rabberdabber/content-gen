"""
This file defines the schemas for the post content for ai content generation using openai structured outputs.
"""
from typing import Literal

from pydantic import BaseModel


# Content node models
class TextNode(BaseModel):
    type: Literal["text"]
    text: str

class ImageNode(BaseModel):
    type: Literal["imageBlock"]
    src: str
    alt: str

class CodeBlockAttributes(BaseModel):
    language: Literal["python", "javascript", "typescript", "tsx", "jsx", "python", "java", "c", "cpp", "ruby", "go", "rust", "html", "css", "sql", "shell", "markdown", "json", "yaml", "xml"]

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

class TableCellAttributes(BaseModel):
    colspan: int
    rowspan: int

class TableCellNode(BaseModel):
    type: Literal["tableCell"]
    attrs: TableCellAttributes
    content: list[ParagraphNode]

class TableRowNode(BaseModel):
    type: Literal["tableRow"]
    content: list[TableCellNode]

class TableCellNode(BaseModel):
    type: Literal["tableCell"]
    content: list[TextNode]

class TableNode(BaseModel):
    type: Literal["table"]
    content: list[TableRowNode]


class PostContent(BaseModel):
    type: Literal["doc"]
    content: list[HeadingNode | ParagraphNode | CodeBlockNode | BulletListNode | OrderedListNode | TableNode]


class DraftContentRequest(BaseModel):
    prompt: str