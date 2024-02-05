from dataclasses import dataclass, fields
from typing import List, Text, Optional, Union
from enum import IntEnum


class NodeType(IntEnum):
    Concatenate = 1
    Alternate = 2
    # And = 3
    Capture = 4
    Repeat = 5
    Condition = 6
    # leaf node

    Empty = 6
    Any = 7
    Position = 8
    Ref = 9

    Word = 10
    WordSet = 11
    DynamicWord = 12
    DynamicWordSet = 13
    SthWord = 14

    LeftParent = 100
    VerticalBar = 101


class PositionNodeType(IntEnum):
    BeginLine = 1
    EndLine = 2


def dump_node(node, depth, DUMP_INDENT_WIDTH=2):
    SPACE_UNIT = " " * DUMP_INDENT_WIDTH
    # 5种非叶节点
    if isinstance(node, ConcatenateNode):
        res_str = f"Concatenate"
        if node.RightToLeft:
            res_str += " -L "
        res_str += "(\n"
        for sub in node.subs:
            res_str += SPACE_UNIT * (depth + 1) + dump_node(sub, depth + 1)
        return res_str + SPACE_UNIT * depth + ")\n"

    elif isinstance(node, AlternateNode):
        res_str = f"Alternate"
        if node.RightToLeft:
            res_str += " -L "
        res_str += "(\n"
        for sub in node.subs:
            res_str += SPACE_UNIT * (depth + 1) + dump_node(sub, depth + 1)
        return res_str + SPACE_UNIT * depth + ")\n"

    elif isinstance(node, CaptureNode):
        res_str = f"Capture"
        if node.RightToLeft:
            res_str += " -L "
        res_str += "(name={node.name},index={node.index}\n"
        res_str += SPACE_UNIT * (depth + 1) + dump_node(node.sub, depth + 1)
        return res_str + SPACE_UNIT * depth + ")\n"

    elif isinstance(node, ConditionNode):
        if node.is_positive:
            res_str = f"Require"
        else:
            res_str = f"Prevent"
        if node.RightToLeft:
            res_str += " -L "
        res_str += "(\n"
        res_str += SPACE_UNIT * (depth + 1) + dump_node(node.sub, depth + 1)
        return res_str + SPACE_UNIT * depth + ")\n"

    elif isinstance(node, RepeatNode):
        res_str = f"Repeat"
        if node.RightToLeft:
            res_str += " -L "
        res_str += "(min={node._min},max={node._max},is_nongreedy={node.is_nongreedy}\n"
        res_str += SPACE_UNIT * (depth + 1) + dump_node(node.sub, depth + 1)
        return res_str + SPACE_UNIT * depth + ")\n"
    # 9种叶节点
    elif isinstance(node, AnyNode):
        return f"{str(node)}\n"
    elif isinstance(node, PositionNode):
        if node.tt == PositionNodeType.BeginLine:
            return "LINE_BEGIN\n"
        elif node.tt == PositionNodeType.EndLine:
            return "LINE_END\n"
    elif isinstance(node, RefNode):
        return f"{str(node)}\n"
    elif isinstance(node, EmptyNode):
        return f"Empty\n"
    elif isinstance(node, WordNode):
        return f"{str(node)}\n"
    elif isinstance(node, WordSetNode):
        return f"{str(node)}\n"
    elif isinstance(node, DynamicWordNode):
        return f"{str(node)}\n"
    elif isinstance(node, DynamicWordSetNode):
        return f"{str(node)}\n"
    elif isinstance(node, SthNode):
        return f"{str(node)}\n"
    else:
        raise Exception("invalid node type")


# 抽象类，有公共属性和方法
@dataclass
class Node:
    t: int = -1
    fa: "Node" = None
    RightToLeft: bool = False

    def to_string(self):
        return dump_node(self, 0)


@dataclass
class ConcatenateNode(Node):
    t: int = NodeType.Concatenate
    subs: List[Node] = None


@dataclass
class AlternateNode(Node):
    t: int = NodeType.Alternate
    subs: List[Node] = None


@dataclass
class CaptureNode(Node):
    t: int = NodeType.Capture
    name: Text = ""
    index: int = -1  # -1表示非捕获
    sub: Node = None


@dataclass
class FakeCaptureNode(Node):  # 用于记录捕获节点信息
    t: int = NodeType.LeftParent
    tt: int = NodeType.Capture | NodeType.Condition | -1
    # capture node
    name: Text = ""
    index: int = -1
    sub: Node = None
    # 零宽断言
    subs: List[Node] = None
    is_positive: bool = True
    forward: bool = True


@dataclass
class RepeatNode(Node):  # 数量限定符
    t: int = NodeType.Repeat
    sub: Node = None
    _min: int = -1
    _max: int = -1
    is_nongreedy: bool = False

    @property
    def min(self):
        return self._min

    @property
    def max(self):
        return self._max


@dataclass
class ConditionNode(Node):  # 零宽断言
    t: int = NodeType.Condition
    sub: Node = None
    is_positive: bool = True


# 叶节点
def common_fields_expr(node):
    fields_filters = ["fa", "t", "RightToLeft"]
    fields_expr = [
        f"{f.name}={getattr(node, f.name)}"
        for f in fields(node)
        if f.name not in fields_filters
    ]
    fields_expr = "(" + ",".join(fields_expr) + ")"
    if node.RightToLeft:
        fields_expr = " -L " + fields_expr
    return fields_expr


# 匹配词形
@dataclass(repr=False)
class WordNode(Node):  # 匹配单元为词
    t: int = NodeType.Word
    # 词形
    shape: Text = ""

    def __repr__(self):
        return f"Word({self.shape})"


# 匹配词形集合
@dataclass(repr=False)
class WordSetNode(Node):
    t: int = NodeType.Word
    word_list: List[WordNode] = None

    def __repr__(self):
        return f"WordSet[{','.join([str(w) for w in self.word_list])}]"


@dataclass(repr=False)
class SthNode(Node):
    t: int = NodeType.SthWord
    name: Text = ""

    def __repr__(self):
        return f"Sth{common_fields_expr(self)}"


# 语法：
# 1.词性
# 2.词性+词性子类
# 3.词性+词长
# 4.词形
# 5.[#词形|词形]
@dataclass(repr=False)
class DynamicWordNode(Node):
    t: int = NodeType.DynamicWord
    # 词性
    pos: Text = ""
    # 词性子类
    pos2: Text = ""  # ①②③④⑤⑥⑦⑧⑨⑩
    # 词长
    length: int = -1
    # 构词模式
    word_struct: Text = ""
    # 语义类
    semantic_tag: Text = ""

    def __repr__(self):
        return f"DynamicWord({self.pos}{self.pos2}{self.length if self.length != -1 else ''}{self.word_struct}{self.semantic_tag})"


@dataclass(repr=False)
class DynamicWordSetNode(Node):
    t: int = NodeType.DynamicWordSet
    word_list: List[Union[DynamicWordNode, SthNode]] = None

    def __repr__(self):
        return f"DynamicWordSet{common_fields_expr(self)}"


# 语法：空格+名称+空格


@dataclass
class AnyNode(Node):
    t: int = NodeType.Any

    def __repr__(self):
        return f"Any{common_fields_expr(self)}"


@dataclass
class PositionNode(Node):  # 位置限定符：句首，句尾
    t: int = NodeType.Position
    tt: int = -1

    def __repr__(self):
        return f"Position{common_fields_expr(self)}"


@dataclass
class RefNode(Node):  # 反向引用
    t: int = NodeType.Ref
    index: int = -1
    isReversed: bool = False

    def __repr__(self):
        return f"Ref{common_fields_expr(self)}"


@dataclass
class EmptyNode(Node):
    t: int = NodeType.Empty

    def __repr__(self):
        return f"Empty{common_fields_expr(self)}"


def simplify_node(node):
    if hasattr(node, "subs"):  # ALt,Concat
        for ind, sub in enumerate(node.subs):
            sub = simplify_node(sub)
            node.subs[ind] = sub
        if len(node.subs) > 1:
            subs = []
            # Empty节点只保留一个
            possibleEmptyNode = None
            for sub in node.subs:
                if type(sub) == EmptyNode:
                    possibleEmptyNode = sub
                    continue
                if type(sub) == WordSetNode or type(sub) == DynamicWordSetNode:
                    if len(sub.word_list) == 0:
                        continue
                subs.append(sub)
            if possibleEmptyNode is not None:
                subs.append(possibleEmptyNode)
            node.subs = subs
            sub_len = len(node.subs)
            if sub_len == 0:
                return
            # 合并相邻Word节点
            l = 0
            while True:
                while l < sub_len and type(node.subs[l]) != WordNode:
                    l += 1

                if l >= sub_len:
                    break

                r = l
                while r < sub_len and type(node.subs[r]) == WordNode:
                    r += 1

                if l < r:
                    fa = node.subs[l].fa
                    RightToLeft = node.subs[l].RightToLeft
                    s = ""
                    for i in range(l, r):
                        s += node.subs[i].shape
                    fore_sub = node.subs[:l]
                    tail_sub = node.subs[r:]
                    node.subs = (
                        fore_sub
                        + [WordNode(shape=s, fa=fa, RightToLeft=RightToLeft)]
                        + tail_sub
                    )
                    sub_len = len(node.subs)
                l += 1
            pass
        # 对于Alternate或Concat节点，尽量消除其嵌套关系
        if len(node.subs) == 1:
            node.subs[0].fa = node.fa
            node = node.subs[0]
        return node
    elif hasattr(node, "sub"):
        node.sub = simplify_node(node.sub)
        return node
    else:
        return node


def reverse_subnode(node: Node):
    if hasattr(node, "subs"):
        node.subs.reverse()
        for sub in node.subs:
            if type(sub) != ConditionNode:
                sub.RightToLeft = node.RightToLeft
                reverse_subnode(sub)
    if hasattr(node, "sub"):
        if type(node.sub) != ConditionNode:
            node.sub.RightToLeft = node.RightToLeft
            reverse_subnode(node.sub)
