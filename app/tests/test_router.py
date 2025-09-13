import pytest

from app.library.router import ROUTES, Route, RouteType, add_route, get_route, get_routes, make_route_name, route


@pytest.fixture(autouse=True)
def reset_routes():
    # Ensure ROUTES is clean before each test
    ROUTES.clear()
    yield
    ROUTES.clear()


class TestRouteType:
    def test_all_returns_values(self) -> None:
        assert set(RouteType.all()) == {"http", "socket"}


class TestMakeRouteName:
    def test_basic_http_path(self) -> None:
        assert make_route_name("GET", "/api/test") == "get:api.test"

    def test_trailing_slash_and_root(self) -> None:
        # Current behavior converts empty part to 'part'
        assert make_route_name("post", "/") == "post:part"
        assert make_route_name("post", "") == "post:part"

    def test_invalid_chars_and_numbers(self) -> None:
        # invalid chars become underscores, leading digits prefixed with p_
        assert make_route_name("GET", "/a-b/c@d/123/0x-ff") == "get:a_b.c_d.p_123.p_0x_ff"


class TestRouteDecorator:
    @pytest.mark.asyncio
    async def test_registers_http_and_no_slash_alias(self) -> None:
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
        assert r2.method == "GET"
        assert r2.path == "/api/test"

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

    def test_socket_route_registration(self) -> None:
        @route(RouteType.SOCKET, "/ws/conn")
        async def ws():
            return "socket"

        socket_routes = get_routes(RouteType.SOCKET)
        assert "socket:ws.conn" in socket_routes
        # No no_slash alias for socket routes
        assert "socket:ws.conn_no_slash" not in socket_routes


class TestAddRoute:
    def test_add_route_http_with_alias(self) -> None:
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

    def test_add_route_socket_without_alias(self) -> None:
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


class TestGetters:
    def test_get_routes_returns_copy_like_mapping(self) -> None:
        async def h():
            return "x"

        add_route("GET", "/x", h)
        routes = get_routes(RouteType.HTTP)
        assert isinstance(routes, dict)
        assert "get:x" in routes

    def test_get_route_not_found(self) -> None:
        assert get_route(RouteType.HTTP, "nonexistent") is None
