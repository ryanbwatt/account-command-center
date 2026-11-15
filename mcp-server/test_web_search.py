from server import _parse_ddg

PAGE = """<div class="result__body">
<a class="result__a" href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fexample.com%2Fa&rut=x">Example A</a>
<a class="result__snippet">Snippet A</a></div>
<div class="result__body"><a class="result__a" href="https://duckduckgo.com/y.js?ad=1">Ad</a></div>
<div class="result__body"><a class="result__a" href="https://example.org/b">Example B</a></div>"""


def test_parse_ddg():
    r = _parse_ddg(PAGE, 10)
    assert r == [
        {"title": "Example A", "url": "https://example.com/a", "snippet": "Snippet A"},
        {"title": "Example B", "url": "https://example.org/b", "snippet": ""},
    ]
    assert len(_parse_ddg(PAGE, 1)) == 1


if __name__ == "__main__":
    test_parse_ddg()
    print("ok")
