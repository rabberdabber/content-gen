import json

from pydantic import ValidationError
from sqlmodel import Field, SQLModel

from app.enums import NodeTypeEnum


# ---------------------------------
# NodeAttrs: generic container for node attributes
# ---------------------------------
class NodeAttrs(SQLModel):
    """
    If you want strict validation for each node type
    (heading vs image vs codeBlock, etc.),
    you can split these up or make them more specific.
    """
    textAlign: str | None = None
    level: int | None = None
    src: str | None = None
    alt: str | None = None
    title: str | None = None
    width: int | str | None = None
    height: int | str | None = None
    language: str | None = None
    start: int | None = None
    color: str | None = None


# ---------------------------------
# MarkAttrs: if your marks have attributes (e.g., link, textStyle)
# ---------------------------------
class MarkAttrs(SQLModel):
    href: str | None = None
    target: str | None = None
    rel: str | None = None


# ---------------------------------
# Mark: e.g. { "type": "bold", "attrs": {...} }
# ---------------------------------
class Mark(SQLModel):
    type: str
    attrs: MarkAttrs | None = None


# ---------------------------------
# ProseMirrorNode: recursive definition
# ---------------------------------
class ProseMirrorNode(SQLModel):
    """
    Represents a generic ProseMirror/Tiptap node.
    """
    type: NodeTypeEnum
    attrs: NodeAttrs | None = None
    content: list["ProseMirrorNode"] | None = None  # recursive reference
    text: str | None = None
    marks: list[Mark] | None = None


# ---------------------------------
# TiptapDoc: top-level doc node
# ---------------------------------
class TiptapDoc(SQLModel):
    """
    Usually Tiptap outputs a top-level node like:
    {
      "type": "doc",
      "content": [...]
    }
    """
    type: NodeTypeEnum = Field(default=NodeTypeEnum.doc)
    content: list[ProseMirrorNode] = Field(default_factory=list)
    class Config:
        extra = "forbid"


# IMPORTANT: Enable forward references
ProseMirrorNode.model_rebuild()


# ---------------------------------
# EXAMPLE USAGE
# ---------------------------------
if __name__ == "__main__":
    # Sample "post" data (ProseMirror doc)
    sample_post = {
      "type": "doc",
      "content": [
        {
          "type": "heading",
          "attrs": {
            "textAlign": "left",
            "level": 1
          },
          "content": [
            {
              "type": "text",
              "text": "Hello Please Edit the blog"
            }
          ]
        },
        {
          "type": "image",
          "attrs": {
            "src": "https://example.com/sample.jpeg",
            "alt": "Generated image",
            "title": None,
            "width": 700,
            "height": 512
          }
        },
        {
          "type": "codeBlock",
          "attrs": {
            "language": "python"
          },
          "content": [
            {
              "type": "text",
              "text": "def fibonacci(n: int): return fibonacci(n-1) + fibonacci(n-2)"
            }
          ]
        },
        {
          "type": "orderedList",
          "attrs": {
            "start": 1
          },
          "content": [
            {
              "type": "listItem",
              "attrs": {
                "color": ""
              },
              "content": [
                {
                  "type": "paragraph",
                  "attrs": {
                    "textAlign": "left"
                  },
                  "content": [
                    {
                      "type": "text",
                      "text": "one"
                    }
                  ]
                }
              ]
            }
          ]
        },
        {
          "type": "video",
          "attrs": {
            "src": "http://localhost:8000/uploads/some-video.mp4"
          }
        },
        {
          "type": "paragraph",
          "attrs": {
            "textAlign": "left"
          }
        }
      ]
    }

    # Validate with Pydantic:
    try:
        doc = TiptapDoc.model_validate(sample_post)
        print("Document is valid!")
        print(doc.model_dump_json(indent=2))
    except ValidationError as e:
        print("Validation error!")
        print(json.dumps(e.errors(), indent=2))
