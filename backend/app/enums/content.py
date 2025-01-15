from enum import Enum


class NodeTypeEnum(str, Enum):
    doc = "doc"
    paragraph = "paragraph"
    heading = "heading"
    text = "text"
    imageBlock = "imageBlock"
    codeBlock = "codeBlock"
    orderedList = "orderedList"
    listItem = "listItem"
    video = "video"
