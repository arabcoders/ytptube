import pytest
from aiohttp import web

from app.library.router import ROUTES, Route, RouteType, add_route, get_route, get_routes, make_route_name, route
from app.tests.helpers import url_for


@pytest.fixture(autouse=True)
def reset_routes():
    snapshot = {route_type: routes.copy() for route_type, routes in ROUTES.items()}
    ROUTES.clear()
    yield
    ROUTES.clear()
    ROUTES.update(snapshot)


class TestMakeRouteName:
    def test_trailing_slash_and_root(self) -> None:
        # Current behavior converts empty part to 'part'
        assert make_route_name("post", "/") == "post:part"
        assert make_route_name("post", "") == "post:part"

    def test_invalid_chars_and_numbers(self) -> None:
        # invalid chars become underscores, leading digits prefixed with p_
        assert make_route_name("GET", "/a-b/c@d/123/0x-ff") == "get:a_b.c_d.p_123.p_0x_ff"


class TestRouteDecorator:
    @pytest.mark.asyncio
    async def test_registers_http_alias(self) -> None:
        # Define an async handler and decorate it
        result_bucket: dict[str, int] = {"called": 0}

        @route("GET", "/api/test/")
        async def handler() -> str:
            result_bucket["called"] += 1
            return "ok"

        # Two routes should be registered: with slash and _no_slash alias
        http_routes = get_routes(RouteType.HTTP)
        assert "get:api.test" in http_routes
        assert "get:api.test_no_slash" in http_routes

        # Verify stored Route objects
        r1: Route = http_routes["get:api.test"]
        r2: Route = http_routes["get:api.test_no_slash"]
        assert r1.method == "GET"
        assert r1.path == "/api/test/"
        assert r1.public is False
        assert r2.method == "GET"
        assert r2.path == "/api/test"
        assert r2.public is False

        # The wrapper should call the original function
        res = await r1.handler()
        assert res == "ok"
        assert result_bucket["called"] == 1

        # Check that metadata is preserved by wraps
        assert r1.handler.__name__ == handler.__name__

    def test_decorator_no_slash_disabled(self) -> None:
        @route("GET", "/api/one/", no_slash=True)
        async def h1():
            return "one"

        http_routes = get_routes(RouteType.HTTP)
        assert "get:api.one" in http_routes
        assert "get:api.one_no_slash" not in http_routes

    def test_public_alias_metadata(self) -> None:
        @route("GET", "/api/public/", public=True)
        async def handler():
            return "public"

        http_routes = get_routes(RouteType.HTTP)
        assert http_routes["get:api.public"].public is True
        assert http_routes["get:api.public_no_slash"].public is True

    def test_socket_route_registration(self) -> None:
        @route(RouteType.SOCKET, "/ws/conn")
        async def ws():
            return "socket"

        socket_routes = get_routes(RouteType.SOCKET)
        assert "socket:ws.conn" in socket_routes
        # No no_slash alias for socket routes
        assert "socket:ws.conn_no_slash" not in socket_routes


class TestAddRoute:
    def test_add_http_alias(self) -> None:
        async def handler():
            return "ok"

        add_route("POST", "/api/create/", handler)

        http_routes = get_routes(RouteType.HTTP)
        assert "post:api.create" in http_routes
        assert "post:api.create_no_slash" in http_routes

        r = get_route(RouteType.HTTP, "post:api.create")
        assert isinstance(r, Route)
        assert r.method == "POST"
        assert r.path == "/api/create/"

    def test_add_socket_no_alias(self) -> None:
        async def s():
            return "s"

        add_route(RouteType.SOCKET, "/sock/path/", s)

        socket_routes = get_routes(RouteType.SOCKET)
        assert "socket:sock.path" in socket_routes
        assert "socket:sock.path_no_slash" not in socket_routes

    def test_add_route_custom_name(self) -> None:
        async def h():
            return "x"

        add_route("GET", "/v1/x", h, name="get:v1.custom")
        assert get_route(RouteType.HTTP, "get:v1.custom") is not None

    def test_public_add_alias(self) -> None:
        async def handler():
            return "public"

        add_route("GET", "/public/", handler, public=True)

        route_with_slash = get_route(RouteType.HTTP, "get:public")
        no_slash_route = get_route(RouteType.HTTP, "get:public_no_slash")
        assert isinstance(route_with_slash, Route)
        assert isinstance(no_slash_route, Route)
        assert route_with_slash.public is True
        assert no_slash_route.public is True


class TestGetters:
    def test_get_routes_copy(self) -> None:
        async def h():
            return "x"

        add_route("GET", "/x", h)
        routes = get_routes(RouteType.HTTP)
        assert isinstance(routes, dict)
        assert "get:x" in routes

    def test_get_route_not_found(self) -> None:
        assert get_route(RouteType.HTTP, "nonexistent") is None


class TestTestApp:
    @pytest.mark.asyncio
    async def test_handler_and_url(self, test_client) -> None:
        @route("GET", "api/items/{id}", "items_get")
        async def production_handler(request: web.Request) -> web.Response:
            return web.Response(text="production")

        async def test_handler(request: web.Request) -> web.Response:
            return web.Response(text=f"{request.match_info['id']}:{request.query['q']}")

        client = await test_client({"items_get": test_handler})
        response = await client.get(url_for("items_get", id="7", query={"q": "found"}))

        assert response.status == 200
        assert await response.text() == "7:found"

    @pytest.mark.asyncio
    async def test_unknown_route(self, test_client) -> None:
        await test_client()

        with pytest.raises(KeyError, match="Unknown test route"):
            url_for("missing")
