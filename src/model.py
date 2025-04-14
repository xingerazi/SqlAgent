from dataclasses import asdict, dataclass
import json
import openai


from typing import Any, Dict, List, Optional
from copy import deepcopy
from .tool import Tool


def get_dict_from_nested_dataclasses(obj, ignore_key=None):
    def convert(obj):
        if hasattr(obj, "__dataclass_fields__"):
            return {k: convert(v) for k, v in asdict(obj).items() if k != ignore_key}
        return obj

    return convert(obj)

@dataclass
class ChatMessageToolCallDefinition:
    arguments: Any
    name: str
    description: Optional[str] = None

    @classmethod
    def from_hf_api(cls, tool_call_definition) -> "ChatMessageToolCallDefinition":
        return cls(
            arguments=tool_call_definition.arguments,
            name=tool_call_definition.name,
            description=tool_call_definition.description,
        )

@dataclass
class ChatMessageToolCall:
    function: ChatMessageToolCallDefinition
    id: str
    type: str

    @classmethod
    def from_hf_api(cls, tool_call) -> "ChatMessageToolCall":
        return cls(
            function=ChatMessageToolCallDefinition.from_hf_api(
                tool_call.function),
            id=tool_call.id,
            type=tool_call.type,
        )


@dataclass
class ChatMessage:
    role: str
    content: Optional[str] = None
    tool_calls: Optional[List[ChatMessageToolCall]] = None
    raw: Optional[Any] = None  # Stores the raw output from the API

    def model_dump_json(self):
        return json.dumps(get_dict_from_nested_dataclasses(self, ignore_key="raw"))

    @classmethod
    def from_hf_api(cls, message, raw) -> "ChatMessage":
        tool_calls = None
        if getattr(message, "tool_calls", None) is not None:
            tool_calls = [ChatMessageToolCall.from_hf_api(
                tool_call) for tool_call in message.tool_calls]
        return cls(role=message.role, content=message.content, tool_calls=tool_calls, raw=raw)

    @classmethod
    def from_dict(cls, data: dict) -> "ChatMessage":
        if data.get("tool_calls"):
            tool_calls = [
                ChatMessageToolCall(
                    function=ChatMessageToolCallDefinition(**tc["function"]), id=tc["id"], type=tc["type"]
                )
                for tc in data["tool_calls"]
            ]
            data["tool_calls"] = tool_calls
        return cls(**data)

    def dict(self):
        return json.dumps(get_dict_from_nested_dataclasses(self))


def get_tool_json_schema(tool: Tool) -> Dict[str, Any]:
    """
    Converts a Tool object into OpenAI's function calling JSON schema format.

    Args:
        tool (Tool): The tool object to convert.

    Returns:
        Dict[str, Any]: The OpenAI-compatible function JSON schema.
    """
    properties = deepcopy(tool.args_schema)  # 复制 schema 避免修改原数据
    required = []

    # 处理每个参数
    for key, value in properties.items():
        if value["type"] == "any":
            value["type"] = "string"  # OpenAI API 不支持 "any"，转换为 "string"
        # 如果不是 nullable，则是必填项
        if not ("nullable" in value and value["nullable"]):
            required.append(key)

    return {
        "type": "function",
        "function": {
            "name": tool.name,  # 工具名称
            "description": tool.description,  # 工具描述
            "parameters": {
                "type": "object",
                "properties": properties,
                "required": required,
            },
        },
    }


def handle_tool_calls(message) -> Dict[str, Any]:
    from .tool import Tool
    tool_calls = getattr(message, "tool_calls", None)
    results = {}

    if not tool_calls:
        return results

    for tool_call in tool_calls:
        name = tool_call.function.name
        raw_args = tool_call.function.arguments

        try:
            args = json.loads(raw_args) if isinstance(
                raw_args, str) else raw_args
        except Exception as e:
            print(f"❌ 参数解析失败: {e}")
            continue

        if name in Tool.registry:
            tool_obj = Tool.registry[name]
            try:
                result = tool_obj.forward(tool_obj, **args)
                print(f"\n🔧 Tool `{name}` executed → result:\n{result}")
                results[name] = result
            except Exception as exec_err:
                print(f"❌ 执行工具 `{name}` 出错: {exec_err}")
        else:
            print(f"⚠️ Tool `{name}` 未注册")

    return results


class OpenAIServerModel:
    """This model connects to an OpenAI-compatible API server.

    Parameters:
        model_id (`str`):
            The model identifier to use on the server (e.g. "gpt-4").
        base_url (`str`, *optional*):
            The base URL of the OpenAI-compatible API server.
        api_key (`str`, *optional*):
            The API key to use for authentication.
        project (`str`, *optional*):
            The project to use for the API request.
        stop_sequences (`List[str]`, *optional*):
            Stop sequences to indicate where generation should end.
        tools_to_call_from (`List[Tool]`, *optional*):
            A list of tools that the model can call from.
        **kwargs:
            Additional keyword arguments to pass to the OpenAI API.
    """

    def __init__(
        self,
        model_id: str,
        base_url: Optional[str],
        api_key: Optional[str],
        stop_sequences: Optional[List[str]] = None,
        tools_list: Optional[List[Tool]] = None,
        **kwargs,
    ):
        try:
            import openai
        except ModuleNotFoundError:
            raise ModuleNotFoundError(
                "Please install 'openai' to use OpenAIServerModel: `pip install openai`"
            ) from None

        self.model_id = model_id
        self.client = openai.OpenAI(
            base_url=base_url,
            api_key=api_key,
        )
        self.stop_sequences = stop_sequences
        self.tools_list = tools_list if tools_list is not None else list(Tool.registry.values())
        self.additional_kwargs = kwargs

    def __call__(
        self,
        messages: List[Dict[str, str]],
        **kwargs,
    ) -> Dict[str, Any]:
        """Generates a response using the OpenAI API."""
        pass_tools = kwargs.pop("pass_tools", False)
        completion_kwargs = {
            "messages": messages,
            "model": self.model_id,
            "stop":  self.stop_sequences,
            **self.additional_kwargs,
            **kwargs,
        }
        if pass_tools and self.tools_list:
            tools_json = [tool.tool_json_schema for tool in self.tools_list]
            completion_kwargs.update({
                "tools": tools_json,
                "tool_choice": "auto"
            })

        # print("\n🟢 [REQUEST PAYLOAD]")
        # print(json.dumps(completion_kwargs, indent=2, ensure_ascii=False))
        response = self.client.chat.completions.create(**completion_kwargs)

        message = response.choices[0].message
        # print("message",message)
        # Return parsed message

        tool_results = handle_tool_calls(message)
        # ✅ 返回原始 message 对象
        return {
            "message": message,
            "tool_results": tool_results
        }
