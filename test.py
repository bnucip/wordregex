# Create your tests here.
from compile import (
    find_word_string,
    find_all_word_string,
    find_word_string_r,
    compile_regex,
)

word_lst1 = [{"shape": "发展", "semantic": "dev"}, {"shape": "建设", "semantic": "dev"}]
word_lst2 = [
    {"shape": "１９９７年", "pos": "t"},
    {"shape": "，", "pos": "w"},
    {"shape": "是", "pos": "v"},
    {"shape": "中国", "pos": "n"},
    {"shape": "发展", "pos": "v"},
    {"shape": "历史", "pos": "n"},
    {"shape": "上", "pos": "f"},
    {"shape": "非常", "pos": "d"},
    {"shape": "重要", "pos": "a"},
    {"shape": "的", "pos": "u"},
    {"shape": "很", "pos": "d"},
    {"shape": "不", "pos": "d"},
    {"shape": "平凡", "pos": "a"},
    {"shape": "的", "pos": "u"},
    {"shape": "一", "pos": "m"},
    {"shape": "年", "pos": "q"},
    {"shape": "。", "pos": "w"},
]
res, ok = find_all_word_string("<dev>+", word_lst1)
if ok:
    print("test1: ", res)

res, ok = find_all_word_string("(?<haha>v)n", word_lst2)
if ok:
    print("test2: ", res)

res, ok = find_word_string(" pred n", word_lst2, options_regex={"pred": "[va]"})
if ok:
    print("test3: ", res)

runner, ok = compile_regex("(?<pred>v)(n)")
res, ok = find_word_string_r(runner, word_lst2)
if ok:
    print("test4: ", res)
