import inspect
import re
from typing import Callable, Dict, Any

class Tool:
    registry = {}  # 所有注册的工具函数

    def __init__(self, name: str, description: str, args_schema: Dict[str, Any]):
        self.name = name
        self.description = description
        self.args_schema = args_schema
        Tool.registry[self.name] = self  # 注册工具

    def __call__(self, *args, **kwargs):
        return self.forward(self, *args, **kwargs)

    def forward(self, *args, **kwargs):
        raise NotImplementedError("Tool must implement forward().")

def tool(tool_function: Callable) -> Tool:
    tool_json_schema = convert_to_json(tool_function)
    # print(tool_json_schema)
    parameters = tool_json_schema["function"]["parameters"]

    wrapped_tool = Tool(
        name=tool_json_schema["function"]["name"],
        description=tool_json_schema["function"]["description"],
        args_schema=parameters["properties"]
    )

    def wrapped_forward(self, *args, **kwargs):
        return tool_function(*args, **kwargs)

    wrapped_tool.forward = wrapped_forward
    wrapped_tool.func = tool_function
    wrapped_tool.tool_json_schema = tool_json_schema
    return wrapped_tool

def parse_docstring(function: Callable) -> Dict[str, Any]:
    docstring = inspect.getdoc(function)
    if not docstring:
        raise ValueError(f"函数 {function.__name__} 没有 docstring，无法解析。")

    func_name = function.__name__
    description_match = re.split(r"\n\s*(Args|Returns):", docstring, maxsplit=1)
    description = description_match[0].strip() if description_match else ""

    args_match = re.search(r"Args:\s*(.*?)\n\s*(Returns|$)", docstring, re.DOTALL)
    args = args_match.group(1).strip() if args_match else ""

    returns_match = re.search(r"Returns:\s*(.*?)$", docstring, re.DOTALL)
    returns = returns_match.group(1).strip() if returns_match else ""

    if not description or not args or not returns:
        raise ValueError(f"函数 {function.__name__} 的 docstring 不完整，缺少 'description', 'args' 或 'returns'。")

    return {"description": description, "args": args, "returns": returns, "func_name": func_name}

def convert_to_json(function: Callable) -> Dict[str, Any]:
    parsed_doc = parse_docstring(function)
    parameters = {
        "type": "object",
        "properties": {},
        "required": [],
        "additionalProperties": False,
    }

    args_lines = parsed_doc["args"].strip().split("\n") if parsed_doc["args"] else []
    for line in args_lines:
        line = line.strip()
        if not line:
            continue

        match = re.match(r"(\w+)\s*\((\w+)\):\s*(.*)", line)
        if match:
            param_name, param_type, param_desc = match.groups()
            type_mapping = {
                "int": "integer",
                "str": "string",
                "float": "number",
                "bool": "boolean",
                "dict": "object",
                "list": "array",
            }
            json_type = type_mapping.get(param_type.lower(), "string")

            parameters["properties"][param_name] = {
                "type": json_type,
                "description": param_desc,
            }
            parameters["required"].append(param_name)

    return {
        "type": "function",
        "function": {
            "name": parsed_doc["func_name"],
            "description": parsed_doc["description"],
            "parameters": parameters,
            "strict": True,
        },
    }