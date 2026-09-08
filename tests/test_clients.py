import json

from cinema import Cinema


class Response:
    def __init__(self, status=200, payload=None, text=None):
        self.status_code = status
        self.ok = 200 <= status < 400
        self._payload = payload
        self.text = text if text is not None else json.dumps(payload)
        self.content = b"" if status == 204 else self.text.encode()

    def json(self):
        return self._payload

    def raise_for_status(self):
        if not self.ok:
            raise RuntimeError(self.status_code)


class Session:
    def __init__(self, responses):
        self.responses, self.calls, self.headers = iter(responses), [], {}

    def get(self, url, **kw):
        self.calls.append(("GET", url, kw))
        return next(self.responses)

    def post(self, url, **kw):
        self.calls.append(("POST", url, kw))
        return next(self.responses)

    def request(self, method, url, **kw):
        self.calls.append((method, url, kw))
        return next(self.responses)

    def close(self):
        pass


def test_namespace():
    assert Cinema.Odeon.__name__ == "OdeonClient"
    assert Cinema.Vue.__name__ == "VueClient"


def test_odeon_cancel_is_delete_and_accepts_204():
    session = Session([Response(204)])
    client = Cinema.Odeon(session=session, auto_connect=False)
    client.api_root = "https://example.test/ocapi/v1"
    client.cancel_order("abc")
    assert session.calls[0][0:2] == (
        "DELETE",
        "https://example.test/ocapi/v1/orders/abc",
    )


def test_vue_cancel_is_delete_and_accepts_204():
    session = Session([Response(204)])
    client = Cinema.Vue(session=session, auto_connect=False)
    client.cancel_order("abc")
    assert session.calls[0][0] == "DELETE"
    assert session.calls[0][1].endswith("/booking/order/abc")


def test_vue_order_shape():
    body = Cinema.Vue.make_order(
        "c",
        "s",
        "e@example.com",
        {"areaCategoryCode": "a", "code": "t", "priceInCents": 10},
        [{"areaNumber": 1, "rowIndex": 2, "columnIndex": 3}],
    )
    assert body["tickets"][0]["seats"][0]["rowIndex"] == 2
