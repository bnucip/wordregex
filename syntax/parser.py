from dataclasses import dataclass
from typing import List, Text, Optional, Tuple, Dict, Any
import sys
from .tree import (
    Node,
    ConcatenateNode,
    AlternateNode,
    CaptureNode,
    FakeCaptureNode,
    RepeatNode,
    ConditionNode,
    AnyNode,
    PositionNode,
    RefNode,
    EmptyNode,
    WordNode,
    WordSetNode,
    DynamicWordNode,
    DynamicWordSetNode,
    SthNode,
    NodeType,
    PositionNodeType,
)
from .tree import simplify_node, reverse_subnode


def is_special(ch):
    if ch == "^" or ch == "$":  # 位置限定
        return True
    elif ch == "?" or ch == "+" or ch == "*" or ch == "{":  # 数量限定
        return True
    elif ch == "(" or ch == ")" or ch == "|":  # 分组
        return True
    elif ch == "\\":  # 反向引用
        return True
    elif ch == "\/":  # 逆序匹配反向引用
        return True
    elif ch == "." or ch == "[":  # 字符集
        return True
    return False


def is_chinese(ch: Text):
    return True if "\u4e00" <= ch <= "\u9fff" else False


# 分析模式串中单个词对象表示
# 输入：模式串
# 输出：DynamicWordNode, 消耗的字符个数
# 示例
# 输入：a⑦⑦xxxx (自定义语法)
# 输出：DynamicWordNode(属性，生成规则), 3
class WordParser:
    # 词形
    @staticmethod
    def scanWordNode(input_text):
        if len(input_text) == 0 or not is_chinese(input_text[0]):
            return None, False
        match_l = 0
        for i in range(len(input_text)):
            if is_chinese(input_text[i]):
                match_l += 1
            else:
                break
        return WordNode(shape=input_text[:match_l]), match_l

    # 单个词对象表示形式
    @staticmethod
    def scanDynamicWordNode(input_text):
        if len(input_text) == 0 or not input_text[0].isalpha():
            return None, 0
        pos_ = input_text[0]
        input_text_ = input_text[1:]
        match_l = 1
        if len(input_text_) == 0:
            return DynamicWordNode(pos=pos_), match_l
        if ord("0") <= ord(input_text_[0]) <= ord("9"):
            match_l += 1
            return (
                DynamicWordNode(pos=pos_, length=ord(input_text_[0]) - ord("0")),
                match_l,
            )
        elif input_text_[0] in "①②③④⑤⑥⑦⑧⑨⑩":
            match_l += 1
            pos2_ = input_text_[0]
            input_text_ = input_text_[1:]
            if len(input_text_) > 0 and ord("0") <= ord(input_text_[0]) <= ord("9"):
                match_l += 1
                return (
                    DynamicWordNode(
                        pos=pos_, pos2=pos2_, length=ord(input_text_[0]) - ord("0")
                    ),
                    match_l,
                )
            else:
                return DynamicWordNode(pos=pos_, pos2=pos2_), match_l
        else:
            return DynamicWordNode(pos=pos_), match_l

    # 词汇集合
    @staticmethod
    def scanSet(input_text):
        if len(input_text) == 0 or input_text[0] != "[":
            return None, False
        # 左括号匹配
        match_l = 1
        input_text_ = input_text[1:]
        has_right = False
        if len(input_text_) == 0:
            return None, 0
        if (
            input_text_[0] == "#"
        ):  # 长度大于2的词形集合    [#自己|之一|本身|这样|那样|这般|那般]
            match_l += 1
            input_text_ = input_text_[1:]
            word_lst = []
            while len(input_text_) > 0:
                wn, wn_l = WordParser.scanWordNode(input_text_)
                if wn_l == 0:
                    return None, 0
                match_l += wn_l
                word_lst.append(wn)
                input_text_ = input_text_[wn_l:]
                if len(input_text_) == 0:
                    return None, 0
                if input_text_[0] == "|":
                    match_l += 1
                    input_text_ = input_text_[1:]
                elif input_text_[0] == "]":
                    has_right = True
                    match_l += 1
                    break
                else:
                    return None, 0
            if not has_right:
                return None, 0
            return WordSetNode(word_list=word_lst), match_l
        elif is_chinese(input_text_[0]):  # 词长为1的词形    [了着过]
            word_lst = []
            for i in range(len(input_text_)):
                if is_chinese(input_text_[i]):
                    word_lst.append(WordNode(shape=input_text_[i]))
                    match_l += 1
                elif input_text_[i] == "]":
                    match_l += 1
                    break
                else:
                    return None, 0
            return WordSetNode(word_list=word_lst), match_l
        elif input_text_[0].isalpha():  # 词汇集合扩展 [amv]
            word_lst = []
            while len(input_text_) > 0:
                dwn, dwn_l = WordParser.scanDynamicWordNode(input_text_)
                if dwn_l == 0:
                    break
                word_lst.append(dwn)
                match_l += dwn_l
                input_text_ = input_text_[dwn_l:]
            if len(input_text_) > 0 and input_text_[0] == "]":
                match_l += 1
                return DynamicWordSetNode(word_list=word_lst), match_l
            else:
                return None, 0
        else:
            return None, 0

    # 构词模式 或 语义类
    @staticmethod
    def scanStruct(input_text):  # 语义类 或 构词模式
        if len(input_text) == 0 or input_text[0] != "<":
            return None, False
        match_l = 1
        input_text_ = input_text[1:]
        if len(input_text_) == 0:
            return None, 0
        is_semantic = True
        if input_text_[0] == "#":  # 构词模式 <#
            match_l += 1
            input_text_ = input_text_[1:]
            is_semantic = False
        tag = ""
        has_right = False
        for i in range(len(input_text_)):
            if input_text_[i] == "<":
                return None, 0
            elif input_text_[i] == ">":
                match_l += 1
                has_right = True
                break
            else:
                match_l += 1
                tag += input_text_[i]
        if not has_right:
            return None, 0
        if is_semantic:  # 语义类
            return DynamicWordNode(semantic_tag=tag), match_l
        else:  # 构词模式
            return DynamicWordNode(word_struct=tag), match_l

    # 主函数
    @staticmethod
    def ParseWordNode(input_text):
        if len(input_text) == 0:
            return None, 0
        ch = input_text[0]
        if is_chinese(ch):
            return WordParser.scanWordNode(input_text)
        elif ch.isalpha():  # 词性
            return WordParser.scanDynamicWordNode(input_text)
        elif ch == "[":
            return WordParser.scanSet(input_text)
        elif ch == "<":
            return WordParser.scanStruct(input_text)

        else:
            return None, 0


@dataclass
class RegexParser:
    nodestack: List["Node"] = None
    regex_raw: Text = ""
    regex_length: int = 0
    textpos: int = 0
    autocap: int = 0
    capturename_lst: List[Text] = None
    captureinfo_dict: Dict[Text, int] = None  # name=>cap_id

    def init_state(self):
        self.nodestack = []
        self.textpos = 0
        self.regex_length = len(self.regex_raw)
        self.capturename_lst = []
        self.captureinfo_dict = {}

    def moveRight(self, i):
        self.textpos += i

    def getChar(self):
        return self.regex_raw[self.textpos]

    def getRestStr(self):
        return self.regex_raw[self.textpos :]

    # 分析数字,成功则把标识符消耗
    def scanNumber(self):
        ch = self.getChar()
        if not ch.isdigit():
            return None, False
        if ch == "0":
            self.moveRight(1)
            if self.getChar().isdigit():
                return None, False
            self.moveRight(-1)

        num = 0
        while self.textpos < self.regex_length:
            ch = self.getChar()
            if ch.isdigit():
                num += num * 10 + int(ch)
            else:
                break
            self.moveRight(1)
        return num, True

    # 分析标识符,成功则把标识符消耗
    def scanName(self):
        ch = self.getChar()
        self.moveRight(1)
        # ch为字母,数字或下划线,且不为数字开头
        if not ch.isidentifier():
            return None, False
        while self.textpos < self.regex_length:
            c = self.getChar()
            if c.isalnum() or c == "_":
                ch += c
                self.moveRight(1)
            else:
                break
        return ch, True

    # 分析(...结构,生成伪节点
    def scanGroupOpen(self):
        if self.textpos >= self.regex_length:  # 不能以(结尾
            return None, False
        ch = self.getChar()
        self.moveRight(1)
        if ch != "?":  # 非命名捕获分组
            self.textpos -= 1
            self.autocap += 1
            return (
                FakeCaptureNode(
                    t=NodeType.LeftParent, tt=NodeType.Capture, index=self.autocap
                ),
                True,
            )
        if self.textpos == self.regex_length:  # 不允许(?结尾
            return None, False
        ch = self.getChar()
        self.moveRight(1)
        if self.textpos == self.regex_length:  # 不能以(?x
            return None, False
        if ch == ":":  # (?:,非捕获，只规定优先级
            return (
                FakeCaptureNode(t=NodeType.LeftParent, tt=NodeType.Capture, index=-1),
                True,
            )
        elif ch == "=":  # (?=
            return (
                FakeCaptureNode(
                    t=NodeType.LeftParent, tt=NodeType.Condition, is_positive=True
                ),
                True,
            )
        elif ch == "!":  # (?!
            return (
                FakeCaptureNode(
                    t=NodeType.LeftParent, tt=NodeType.Condition, is_positive=False
                ),
                True,
            )
        elif ch == "<":  # (?<
            ch = self.getChar()
            self.moveRight(1)
            if ch == "=":  # (?<=
                return (
                    FakeCaptureNode(
                        t=NodeType.LeftParent,
                        tt=NodeType.Condition,
                        is_positive=True,
                        RightToLeft=True,
                    ),
                    True,
                )
            elif ch == "!":  # (?<!
                return (
                    FakeCaptureNode(
                        t=NodeType.LeftParent,
                        tt=NodeType.Condition,
                        is_positive=False,
                        RightToLeft=True,
                    ),
                    True,
                )
            elif ch.isidentifier():  # (?<name>
                self.textpos -= 1
                name, ok = self.scanName()
                if not ok:
                    return None, False
                ch = self.getChar()
                if ch != ">":  # 必须以>结尾，
                    return None, False
                self.moveRight(1)
                self.autocap += 1
                return (
                    FakeCaptureNode(
                        t=NodeType.LeftParent,
                        tt=NodeType.Capture,
                        index=self.autocap,
                        name=name,
                    ),
                    True,
                )
            else:
                return None, False
        else:
            return None, False

    def scanWordNode(self):
        if self.textpos >= self.regex_length:
            return None, False
        word_node, word_l = WordParser.ParseWordNode(self.getRestStr())
        if word_node is None:
            return None, False
        self.moveRight(word_l)
        return word_node, True

    def __collapse(self, subs: List["Node"], _t: NodeType):

        if len(subs) == 0:
            return EmptyNode()
        if len(subs) == 1:
            return subs[0]
        res = []
        for sub in subs:
            if sub.t == _t and hasattr(sub, "subs"):
                res += sub.subs
            else:
                res.append(sub)

        if _t == NodeType.Concatenate:
            fnode = ConcatenateNode(subs=res)
        elif _t == NodeType.Alternate:
            fnode = AlternateNode(subs=res)
        else:
            return None
        for node in res:
            node.fa = fnode
        return fnode

    def collapse(self, _t: NodeType):  # concat规约
        i = len(self.nodestack)
        while i > 0 and self.nodestack[i - 1].t < NodeType.LeftParent:
            i -= 1
        subs = self.nodestack[i:]
        self.nodestack = self.nodestack[:i]
        node = self.__collapse(subs, _t)
        if node is None:
            return False
        self.nodestack.append(node)
        return True

    def collect_group_info(self, node) -> bool:
        if not isinstance(node, CaptureNode):
            return False

        if node.name != "" and node.name not in self.capturename_lst:
            self.captureinfo_dict[node.name] = node.index
            self.capturename_lst.append(node.name)

        if 0 < node.index <= self.autocap:
            return True
        else:
            return False

    def scan_regex(self) -> Tuple[Optional["Node"], bool]:
        self.init_state()
        # 一次循环分析一个元字符
        POSITION_CHARS = "^$"
        QUANTIFIER_CHAR = "?+*{"
        while self.textpos < self.regex_length:
            ch = self.getChar()
            self.moveRight(1)

            # 位置限定
            if POSITION_CHARS.find(ch) >= 0:
                if ch == "^":
                    self.nodestack.append(PositionNode(tt=PositionNodeType.BeginLine))
                elif ch == "$":
                    self.nodestack.append(PositionNode(tt=PositionNodeType.EndLine))
            # 数量限定
            elif QUANTIFIER_CHAR.find(ch) >= 0:
                if len(self.nodestack) < 1:  # 表达元字符必须要转义
                    return None, False
                m = -1  # 次数最小值
                n = -1  # 次数最大值
                is_nongreedy = False
                INT_MAX = sys.maxsize
                if ch == "?":
                    m = 0
                    n = 1
                elif ch == "+":
                    m = 1
                    n = INT_MAX
                elif ch == "*":
                    m = 0
                    n = INT_MAX
                elif ch == "{":
                    if self.textpos + 2 > self.regex_length:
                        return None, False
                    m, ok = self.scanNumber()
                    if not ok:
                        return None, False
                    ch = self.getChar()
                    if ch != "," and ch != "}":
                        return None, False
                    if ch == "}":
                        n = m
                    else:  # ch == ',':
                        self.moveRight(1)  # 跳过,
                        ch = self.getChar()
                        if ch == "}":  # {m,}
                            n = INT_MAX
                        else:  # {m,n}
                            n, ok = self.scanNumber()
                            if not ok:
                                return None, False
                            ch = self.getChar()
                            if ch != "}":
                                return None, False

                    self.moveRight(1)  # 跳过}

                if m > n:
                    return None, False
                if self.textpos < self.regex_length:
                    nxt_ch = self.getChar()
                    if nxt_ch == "?":  # 是否为非贪婪
                        is_nongreedy = True
                        self.moveRight(1)
                # 前面已分析完量词语法，开始构建树节点
                tail_node = self.nodestack[-1]
                self.nodestack = self.nodestack[:-1]
                node = RepeatNode(
                    _min=m, _max=n, is_nongreedy=is_nongreedy, sub=tail_node
                )
                tail_node.fa = node
                self.nodestack.append(node)

            elif ch == "(":  # 分组或零宽断言，生成左括号伪节点
                node, ok = self.scanGroupOpen()
                if not ok:
                    return None, False
                self.nodestack.append(node)

            elif ch == "|":  # 生成竖线伪节点
                ok = self.collapse(NodeType.Concatenate)
                if not ok:
                    return None, False
                if (
                    len(self.nodestack) >= 2
                    and self.nodestack[-2].t == NodeType.VerticalBar
                ):
                    # 交换竖线伪节点到
                    t = self.nodestack[-1]
                    self.nodestack[-1] = self.nodestack[-2]
                    self.nodestack[-2] = t
                else:
                    self.nodestack.append(FakeCaptureNode(t=NodeType.VerticalBar))

            elif ch == ")":
                ok = self.collapse(NodeType.Concatenate)
                if not ok:
                    return None, False
                if (
                    len(self.nodestack) > 1
                    and self.nodestack[-2].t == NodeType.VerticalBar
                ):  # 清除VerticalBar
                    self.nodestack[-2] = self.nodestack[-1]
                    self.nodestack.pop()
                ok = self.collapse(NodeType.Alternate)
                if not ok:
                    return None, False
                sub = self.nodestack.pop()
                fake_node = self.nodestack.pop()
                if not isinstance(fake_node, FakeCaptureNode):
                    return None, False
                # 根据FakeCapture节点生成对应节点
                if fake_node.tt == NodeType.Capture:
                    if fake_node.index == -1:  # 非捕获?:
                        self.nodestack.append(sub)
                    else:
                        cap = CaptureNode(
                            name=fake_node.name, index=fake_node.index, sub=sub
                        )
                        sub.fa = cap
                        ok = self.collect_group_info(cap)
                        if not ok:
                            return None, False
                        self.nodestack.append(cap)

                elif fake_node.tt == NodeType.Condition:
                    fnode = ConditionNode(
                        is_positive=fake_node.is_positive,
                        sub=sub,
                        RightToLeft=fake_node.RightToLeft,
                    )

                    if fnode.RightToLeft:
                        reverse_subnode(fnode)
                    sub.fa = fnode
                    self.nodestack.append(fnode)

                else:
                    return None, False

            elif (
                ch == "\\" or ch == r"/"
            ):  # TODO:反向引用 或 转义元字符，元字符在扩展正则中表示不能直接表示，需要创建新语法
                if self.textpos >= self.regex_length:
                    return None, False
                if ch == "\\":
                    isReversed = False
                else:
                    isReversed = True
                ch = self.getChar()
                if ch.isdigit():  # \number
                    n, ok = self.scanNumber()
                    if not ok:
                        return None, False
                    if 0 < n <= self.autocap:
                        self.nodestack.append(RefNode(index=n, isReversed=isReversed))
                    else:
                        return None, False
                elif ch == "p":  # \p<name>
                    self.moveRight(1)
                    ch = self.getChar()
                    if ch != "<":
                        return None, False
                    self.moveRight(1)
                    name, ok = self.scanName()
                    if not self.captureinfo_dict.get(name):
                        return None, False
                    if self.textpos == self.regex_length:
                        return None, False
                    ch = self.getChar()
                    if ch != ">":
                        return None, False
                    self.moveRight(1)
                    self.nodestack.append(
                        RefNode(
                            index=self.captureinfo_dict.get(name), isReversed=isReversed
                        )
                    )

            elif ch == ".":  # TODO:字符集
                self.nodestack.append(AnyNode())

            elif ch == " ":
                if self.textpos >= self.regex_length:
                    return None, False
                sth_name, ok = self.scanName()
                if not ok or self.textpos >= self.regex_length:
                    return None, False
                ch = self.getChar()
                if ch != " ":
                    print("sth_name is not closed with one white space")
                    return None, False
                self.moveRight(1)
                self.nodestack.append(SthNode(name=sth_name))

            else:  # 其它首字符
                self.moveRight(-1)
                node, ok = self.scanWordNode()
                if not ok:
                    return None, False
                self.nodestack.append(node)

        self.collapse(NodeType.Concatenate)
        if (
            len(self.nodestack) > 1 and self.nodestack[-2].t == NodeType.VerticalBar
        ):  # 清除VerticalBar
            self.nodestack[-2] = self.nodestack[-1]
            self.nodestack.pop()
        self.collapse(NodeType.Alternate)
        if len(self.nodestack) > 1:
            return None, False
        return self.nodestack[0], True

    def groups_info(self):
        return self.capturename_lst, self.captureinfo_dict


def _expand_node(node, option_nodes, expandedNode):
    if type(node) == SthNode:
        name = node.name
        if expandedNode.get(name) is not None:
            return expandedNode[name], True
        else:
            if option_nodes.get(name) is None:
                return None, False
            node, ok = _expand_node(option_nodes[name], option_nodes, expandedNode)
            if not ok:
                return None, False
            expandedNode[name] = node
    if hasattr(node, "sub"):
        node.sub, ok = _expand_node(node.sub, option_nodes, expandedNode)
        node.sub.fa = node
        if not ok:
            return None, False
    if hasattr(node, "subs"):
        for ind, sub in enumerate(node.subs):
            sub, ok = _expand_node(sub, option_nodes, expandedNode)
            if not ok:
                return None, False
            sub.fa = node
            node.subs[ind] = sub
    return node, True


def expand_node(node, option_nodes):
    expandedNode = {}
    node, ok = _expand_node(node, option_nodes, expandedNode)
    if not ok:
        return None, False
    return node, True


def regex_to_tree(regex_raw, regex_others: Optional[Dict[Text, Any]] = None):
    if regex_others is None:
        regex_others = {}
    p = RegexParser(regex_raw=regex_raw)
    tree, ok = p.scan_regex()
    if not ok:
        return None, False
    for item in regex_others.items():
        reg_p = RegexParser(regex_raw=item[1])
        t, ok = reg_p.scan_regex()
        if not ok:
            print(f"regex<{item[0]}>  regex_to_tree error")
            return None, False
        regex_others[item[0]] = t
    tree, ok = expand_node(tree, regex_others)
    if not ok:
        print("expand regex error")
        return None, False

    tree = simplify_node(tree)
    new_tree = CaptureNode(index=0, name="<global>", sub=tree)
    tree.fa = new_tree
    return new_tree, ok
