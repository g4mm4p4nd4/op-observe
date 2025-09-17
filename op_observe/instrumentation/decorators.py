"""Instrumentation decorators that mimic OpenLLMetry/OpenInference."""

from __future__ import annotations

import functools
import inspect
from typing import Any, Callable, Dict, Optional

from ..telemetry import StatusCode, get_tracer

# Attribute keys following the OpenLLMetry/OpenInference conventions.
OPENINFERENCE_FRAMEWORK_ATTR = "openinference.framework"
OPENINFERENCE_SPAN_KIND_ATTR = "openinference.span.kind"
OPENINFERENCE_TOOL_NAME_ATTR = "openinference.tool.name"
OPENINFERENCE_NODE_NAME_ATTR = "openinference.graph.node.name"
OPENINFERENCE_NODE_TYPE_ATTR = "openinference.graph.node.type"
OPENINFERENCE_INPUTS_ATTR = "openinference.inputs"
OPENINFERENCE_OUTPUTS_ATTR = "openinference.outputs"
OPENLLMETRY_FRAMEWORK_ATTR = "openllmetry.framework"
OPENLLMETRY_ENTITY_ATTR = "openllmetry.entity.type"
OPENLLMETRY_MODEL_ATTR = "openllmetry.llm.model"
OPENLLMETRY_OPERATION_ATTR = "openllmetry.llm.operation"
OPENLLMETRY_INSTRUMENTATION_ATTR = "openllmetry.instrumentation"
OPENLLMETRY_VERSION_ATTR = "openllmetry.instrumentation.version"
ERROR_FLAG_ATTR = "error"
ERROR_TYPE_ATTR = "error.type"
ERROR_MESSAGE_ATTR = "error.message"

DEFAULT_INSTRUMENTATION_VERSION = "0.1-test"
DEFAULT_INSTRUMENTATION_NAME = "op-observe"


CallableT = Callable[..., Any]
DecoratorT = Callable[[CallableT], CallableT]


def instrument_agent_function(
    framework: str,
    span_kind: str,
    entity_name: Optional[str] = None,
    *,
    llm_model: Optional[str] = None,
    llm_operation: str = "agent_call",
    span_name: Optional[str] = None,
    tracer_name: Optional[str] = None,
    capture_inputs: bool = True,
    capture_outputs: bool = True,
    extra_attributes: Optional[Dict[str, Any]] = None,
) -> DecoratorT:
    """Generic decorator used by the concrete LangChain/LangGraph helpers."""

    if tracer_name is None:
        tracer_name = f"{DEFAULT_INSTRUMENTATION_NAME}.{framework}"

    static_attributes = {
        OPENINFERENCE_FRAMEWORK_ATTR: framework,
        OPENINFERENCE_SPAN_KIND_ATTR: span_kind,
        OPENLLMETRY_FRAMEWORK_ATTR: framework,
        OPENLLMETRY_ENTITY_ATTR: span_kind,
        OPENLLMETRY_OPERATION_ATTR: llm_operation,
        OPENLLMETRY_INSTRUMENTATION_ATTR: DEFAULT_INSTRUMENTATION_NAME,
        OPENLLMETRY_VERSION_ATTR: DEFAULT_INSTRUMENTATION_VERSION,
    }

    if llm_model is not None:
        static_attributes[OPENLLMETRY_MODEL_ATTR] = llm_model

    if extra_attributes:
        static_attributes.update(extra_attributes)

    def decorator(func: CallableT) -> CallableT:
        nonlocal entity_name
        resolved_entity_name = entity_name or func.__name__
        span_prefix = _framework_display_name(framework)
        default_span_name = span_name or f"{span_prefix}.{resolved_entity_name}"

        attributes = dict(static_attributes)

        def update_entity_attributes(mapping: Dict[str, Any]) -> None:
            if span_kind == "tool":
                mapping[OPENINFERENCE_TOOL_NAME_ATTR] = resolved_entity_name
            else:
                mapping[OPENINFERENCE_NODE_NAME_ATTR] = resolved_entity_name

        update_entity_attributes(attributes)

        @functools.wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            tracer = get_tracer(tracer_name)
            call_attributes = _merge_dynamic_attributes(
                attributes,
                args,
                kwargs,
                capture_inputs=capture_inputs,
            )
            with tracer.start_as_current_span(default_span_name, attributes=call_attributes) as span:
                try:
                    result = await func(*args, **kwargs)
                except Exception as exc:  # pragma: no cover - handled in tests
                    _annotate_exception(span, exc)
                    raise
                else:
                    if capture_outputs:
                        span.set_attribute(OPENINFERENCE_OUTPUTS_ATTR, _safe_repr(result))
                    span.set_status(StatusCode.OK)
                    return result

        @functools.wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            tracer = get_tracer(tracer_name)
            call_attributes = _merge_dynamic_attributes(
                attributes,
                args,
                kwargs,
                capture_inputs=capture_inputs,
            )
            with tracer.start_as_current_span(default_span_name, attributes=call_attributes) as span:
                try:
                    result = func(*args, **kwargs)
                except Exception as exc:  # pragma: no cover - handled in tests
                    _annotate_exception(span, exc)
                    raise
                else:
                    if capture_outputs:
                        span.set_attribute(OPENINFERENCE_OUTPUTS_ATTR, _safe_repr(result))
                    span.set_status(StatusCode.OK)
                    return result

        return async_wrapper if inspect.iscoroutinefunction(func) else sync_wrapper  # type: ignore[return-value]

    return decorator


def instrument_langchain_tool(
    tool_name: Optional[str] = None,
    *,
    llm_model: Optional[str] = None,
    span_name: Optional[str] = None,
    tracer_name: Optional[str] = None,
    llm_operation: str = "tool_call",
    capture_inputs: bool = True,
    capture_outputs: bool = True,
    extra_attributes: Optional[Dict[str, Any]] = None,
) -> DecoratorT:
    """Instrument a LangChain tool or tool-like callable."""

    attributes = dict(extra_attributes or {})
    attributes[OPENINFERENCE_SPAN_KIND_ATTR] = "tool"

    return instrument_agent_function(
        framework="langchain",
        span_kind="tool",
        entity_name=tool_name,
        llm_model=llm_model,
        llm_operation=llm_operation,
        span_name=span_name,
        tracer_name=tracer_name,
        capture_inputs=capture_inputs,
        capture_outputs=capture_outputs,
        extra_attributes=attributes,
    )


def instrument_langgraph_node(
    node_name: Optional[str] = None,
    *,
    node_type: Optional[str] = None,
    llm_model: Optional[str] = None,
    span_name: Optional[str] = None,
    tracer_name: Optional[str] = None,
    llm_operation: str = "node_execution",
    capture_inputs: bool = True,
    capture_outputs: bool = True,
    extra_attributes: Optional[Dict[str, Any]] = None,
) -> DecoratorT:
    """Instrument a LangGraph node or callable."""

    attributes = extra_attributes.copy() if extra_attributes else {}
    if node_type is not None:
        attributes[OPENINFERENCE_NODE_TYPE_ATTR] = node_type

    return instrument_agent_function(
        framework="langgraph",
        span_kind="node",
        entity_name=node_name,
        llm_model=llm_model,
        llm_operation=llm_operation,
        span_name=span_name,
        tracer_name=tracer_name,
        capture_inputs=capture_inputs,
        capture_outputs=capture_outputs,
        extra_attributes=attributes,
    )



def _framework_display_name(framework: str) -> str:
    mapping = {
        "langchain": "LangChain",
        "langgraph": "LangGraph",
    }
    return mapping.get(framework, framework.title())



def _merge_dynamic_attributes(
    base_attributes: Dict[str, Any],
    args: Any,
    kwargs: Any,
    *,
    capture_inputs: bool,
) -> Dict[str, Any]:
    call_attributes = dict(base_attributes)
    if capture_inputs:
        call_attributes[OPENINFERENCE_INPUTS_ATTR] = {
            "args": _safe_repr(args),
            "kwargs": _safe_repr(kwargs),
        }
    return call_attributes


def _annotate_exception(span, exc: Exception) -> None:
    span.set_attribute(ERROR_FLAG_ATTR, True)
    span.set_attribute(ERROR_TYPE_ATTR, exc.__class__.__name__)
    span.set_attribute(ERROR_MESSAGE_ATTR, str(exc))


def _safe_repr(value: Any) -> str:
    try:
        return repr(value)
    except Exception:  # pragma: no cover - defensive
        return f"<unreprable {type(value).__name__}>"
