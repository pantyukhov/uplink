# Third party imports
import pytest

# Local imports
from uplink import builder, converters, hooks, exceptions, utils


@pytest.fixture
def fake_service_cls(request_definition_builder, request_definition):
    class Service(object):
        builder = request_definition_builder
    request_definition_builder.build.return_value = request_definition
    return Service


@pytest.fixture
def uplink_builder(http_client_mock):
    b = builder.Builder()
    b.client = http_client_mock
    return b


class TestRequestHandler(object):

    def test_fulfill(self, mocker, request_mock):
        hook = mocker.Mock(spec=hooks.BaseTransactionHook)
        request_mock.send.return_value = 1

        request_handler = builder.RequestHandler(hook, 1, 2, 3)
        value = request_handler.fulfill(request_mock)

        hook.audit_request(1, 2, 3)
        request_mock.add_callback.assert_called_with(hook.handle_response)
        assert value == 1


class TestRequestPreparer(object):

    def test_prepare_request(
            self,
            request_definition,
            uplink_builder,
            transaction_hook_mock
    ):
        request = utils.Request("METHOD", "/example/path", {}, None)
        uplink_builder.hook = transaction_hook_mock
        uplink_builder.base_url = "https://example.com"
        request_preparer = builder.RequestPreparer(
            uplink_builder, request_definition
        )
        request_preparer.prepare_request(request)
        transaction_hook_mock.audit_request.assert_called_with(
            "METHOD",
            "https://example.com/example/path",
            {}
        )


class TestCallFactory(object):
    def test_call(self, mocker, request_definition, request_builder):
        args = ()
        kwargs = {}
        request_preparer = mocker.Mock(spec=builder.RequestPreparer)
        request_preparer.create_request_builder.return_value = request_builder
        factory = builder.CallFactory(
            request_preparer,
            request_definition)
        assert factory(*args, **kwargs) is request_preparer.prepare_request.return_value
        request_definition.define_request.assert_called_with(
            request_builder, args, kwargs
        )
        assert request_builder.build.called


class TestBuilder(object):
    def test_init_adds_standard_converter_factory(self, uplink_builder):
        assert isinstance(
            uplink_builder._converters[0],
            converters.StandardConverter
        )

    def test_client_getter(self, uplink_builder, http_client_mock):
        uplink_builder.client = http_client_mock
        assert uplink_builder.client is http_client_mock

    def test_client_setter(self, uplink_builder, http_client_mock):
        uplink_builder.client = http_client_mock
        assert uplink_builder._client is http_client_mock

    def test_base_url(self, uplink_builder):
        uplink_builder.base_url = "example"
        assert uplink_builder._base_url == "example"

    def test_add_converter_factory(self,
                                   uplink_builder,
                                   converter_factory_mock):
        uplink_builder.add_converter(converter_factory_mock)
        factory = list(uplink_builder.converters)[0]
        assert factory == converter_factory_mock


def test_build_failure(fake_service_cls):
    exception = exceptions.InvalidRequestDefinition()
    fake_service_cls.builder.build.side_effect = exception
    fake_service_cls.builder.__name__ = "builder"
    with pytest.raises(exceptions.UplinkBuilderError):
        builder.build(fake_service_cls, base_url="example.com")


def test_build(
        mocker,
        http_client_mock,
        converter_factory_mock,
        fake_service_cls
):
    # Monkey-patch the Builder class.
    builder_cls_mock = mocker.Mock()
    builder_mock = builder.Builder()
    builder_cls_mock.return_value = builder_mock
    mocker.patch.object(builder, "Builder", builder_cls_mock)

    builder.build(
        fake_service_cls,
        base_url="example.com",
        client=http_client_mock,
        converter=converter_factory_mock
    )
    assert builder_mock.base_url == "example.com"
    assert builder_mock.client is http_client_mock
    assert list(builder_mock.converters)[0] is converter_factory_mock
