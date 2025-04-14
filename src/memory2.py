from dataclasses import asdict, dataclass
from enum import Enum
from typing import Any, Dict, List, Optional, TypedDict, Union
import json
import copy

class MessageRole(str, Enum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"

    @classmethod
    def roles(cls):
        return [r.value for r in cls]


class Message(TypedDict):
    role: MessageRole
    content: str


@dataclass
class ModelOutputMessage:
    content: str
    role: str = "assistant"
    raw: Optional[dict] = None


@dataclass
class MemoryStep:
    def dict(self):
        return asdict(self)

    def to_messages(self, **kwargs) -> List[Message]:
        return []


@dataclass
class StartStep(MemoryStep):
    system_prompt: str

    def to_messages(self, **kwargs) -> List[Message]:
        return [Message(role=MessageRole.SYSTEM.value, content=self.system_prompt)]


@dataclass
class TaskStep(MemoryStep):
    task: str

    def to_messages(self, **kwargs) -> List[Message]:
        content = f"New task:\n{self.task}"
        return [Message(role=MessageRole.USER.value, content=content)]


@dataclass
class ActionStep(MemoryStep):
    step_number: int
    model_input_messages: Optional[List[Message]] = None
    model_output_message: Optional[ModelOutputMessage] = None
    model_output: Optional[str] = None
    observations: Optional[str] = None
    error: Optional[str] = None

    def to_messages(self, summary_mode: bool = False, show_model_input_messages: bool = False) -> List[Message]:
        messages = []

        if show_model_input_messages and self.model_input_messages:
            messages.extend(self.model_input_messages)

        if self.model_output:
            messages.append(
                Message(role=MessageRole.ASSISTANT.value,
                        content=self.model_output.strip())
            )

        if self.observations:
            messages.append(
                Message(role=MessageRole.USER.value,
                        content=f"Observation:\n{self.observations.strip()}")
            )

        if self.error:
            messages.append(
                Message(role=MessageRole.USER.value,
                        content=f"Error: {self.error.strip()}")
            )

        return messages

    def pretty_print(self):
        print("\n🧠 Action Step")
        print("=" * 30)
        print(f"🔢 Step Number: {self.step_number}")

        if self.model_output:
            print("\n🤖 Model Output:")
            print(self.model_output.strip())

        if self.observations:
            print("\n🔍 Observation:")
            print(self.observations.strip())

        if self.error:
            print("\n❌ Error:")
            print(self.error.strip())

        if self.model_input_messages:
            print("\n📥 Model Input Messages:")
            for msg in self.model_input_messages:
                print(f"[{msg['role']}] {msg['content']}")
        print("ActionStep打印结束______")
@dataclass
class ToolCallStep(MemoryStep):
    step_number: int
    tool_name: str
    tool_args: Dict[str, Any]
    tool_result: Any
    model_input_messages: str
    model_output_message: Optional[ModelOutputMessage] = None

    def to_messages(self, **kwargs) -> List[Message]:
        messages = []
        if self.model_input_messages:
            messages.extend(self.model_input_messages)

        tool_content = f"[Tool Call] {self.tool_name}({self.tool_args})\n[Tool Result] {self.tool_result}"
        messages.append(Message(role=MessageRole.ASSISTANT.value, content=tool_content))
        return messages
    
    def pretty_print(self):
        print("\n🔧 Tool Call Step")
        print("=" * 30)
        print(f"🔢 Step Number: {self.step_number}")
        print(f"🔧 Tool: {self.tool_name}({self.tool_args})")
        print(f"📥 Tool Result: {self.tool_result}")
@dataclass
class SqlStep(MemoryStep):
    step_number: int
    sql: str
    sql_result: Any
    model_input_messages: str
    model_output_message: Optional[ModelOutputMessage] = None

    def to_messages(self, **kwargs) -> List[Message]:
        messages = []
        if self.model_input_messages:
            messages.extend(self.model_input_messages)

        messages.append(Message(
            role=MessageRole.ASSISTANT.value,
            content=f"[SQL Executed]\n{self.sql}\n[Result]\n{self.sql_result}"
        ))

        return messages

    def pretty_print(self):
        print("\n🟡 SQL Execution Step")
        print("=" * 30)
        print(f"🔢 Step Number: {self.step_number}")
        print(f"📝 SQL:\n{self.sql}")
        print(f"📥 Result:\n{self.sql_result}")
@dataclass
class FinalStep(MemoryStep):
    step_number: int
    sql: str
    result: str
    explanation: str
    full_text: str

    def to_messages(self, **kwargs) -> List[Message]:
        return [
            Message(role=MessageRole.ASSISTANT.value, content=f"<final_answer>\nSql: {self.sql}\nResult: {self.result}\nAnswer: {self.explanation}\n</final_answer>")
        ]

    def pretty_print(self):
        print("\n✅ Final Answer Step")
        print("=" * 30)
        print(f"🔢 Step Number: {self.step_number}")
        print(f"🧾 SQL:\n{self.sql}")
        print(f"📊 Result:\n{self.result}")
        print(f"🧠 Explanation:\n{self.explanation}")

class AgentMemory:
    def __init__(self):
        self.system_prompt = None
        self.steps: List[MemoryStep] = []

    def reset(self):
        self.steps = []

    def get_succinct_steps(self) -> List[dict]:
        return [step.dict() for step in self.steps if isinstance(step, ActionStep)]

    def get_full_steps(self) -> List[dict]:
        return [step.dict() for step in self.steps]

    def to_messages(self) -> List[Message]:
        messages = []
        for step in self.steps:
            messages.extend(step.to_messages())
        return messages

    def get_observation_history(self) -> str:
        # print("🧠 [Memory] 正在提取观察历史...")
        history = []
        for step in self.steps:
            # 重复输出
            if isinstance(step, TaskStep):
                history.append(f"Task: {step.task}")
            elif isinstance(step, ActionStep):
                action = step.model_output or "<no action>"
                obs = step.observations or step.error or "<no observation>"
                history.append(
                    f"Step {step.step_number}:\nAction: {action.strip()}\nObservation: {obs.strip()}"
                )
            elif isinstance(step, ToolCallStep):
                history.append(
                    f"Step {step.step_number}:\nTool: {step.tool_name}({step.tool_args})\nObservation: {step.tool_result}"
                )
            elif isinstance(step, SqlStep):
                history.append(
                    f"Step {step.step_number}:\nSQL: {step.sql}\nResult: {step.sql_result}"
                )
        full_history = "\n\n".join(history)
        return full_history

    def pretty_print(self):
        print("\n🧠 Agent Memory Summary")
        print("=" * 40)
        for i, step in enumerate(self.steps):
            print(f"\nStep {i + 1}: {type(step).__name__}")
            print("-" * 30)
            if hasattr(step, "task"):
                print(f"📌 Task: {step.task}")
            if hasattr(step, "model_output"):
                print("🤖 Model Output:")
                print(step.model_output.strip())
            if isinstance(step, ToolCallStep):
                step.pretty_print()
            if hasattr(step, "observations") and step.observations:
                print("🔍 Observation:")
                print(step.observations.strip())
            if hasattr(step, "error") and step.error:
                print("❌ Error:")
                print(step.error.strip())

    def export_trace(self) -> str:
        """将推理过程以 Markdown 字符串形式导出，仅保留必要信息"""
        lines = []

        # 任务头
        task_step = next((s for s in self.steps if isinstance(s, TaskStep)), None)
        if task_step:
            lines.append(f"# 📝 Task:\n{task_step.task}\n")

        # 步骤
        for i, step in enumerate(self.steps):
            step_num = getattr(step, "step_number", i)
            lines.append(f"\n## Step {step_num}")

            if isinstance(step, ToolCallStep):
                lines.append("### 🤖 Tool Prompt")
                lines.append(step.model_input_messages.strip())
                lines.append("### 🛠️ Tool Execution")
                lines.append(f"Tool: {step.tool_name}({step.tool_args})")
                lines.append(f"Result: {step.tool_result}")

            elif isinstance(step, SqlStep):
                lines.append("### 🤖 SQL Prompt")
                lines.append(step.model_input_messages.strip())
                lines.append("### 📝 SQL Execution")
                lines.append(f"SQL: {step.sql}")
                lines.append(f"Result: {step.sql_result}")

            elif isinstance(step, ActionStep):
                lines.append("### 🧠 Model Reasoning")
                lines.append(step.model_output.strip())

        return "\n".join(lines)


    def save_trace_to_markdown(self, filepath: str = "trace_output.md"):
        """保存 Markdown 文件"""
        trace_md = self.export_trace()
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(trace_md)


    def export_json(self, filepath: str = "trace_output.json"):
        """导出为 JSON，仅保留必要字段，全部字符串可序列化"""
        import json
        print("export_json")
        print(self.steps)
        steps_data = []
        for i, step in enumerate(self.steps):
            step_data = {
                "step_number": getattr(step, "step_number", i),
                "type": type(step).__name__,
            }

            if isinstance(step, StartStep):
                step_data["system_prompt"] = step.system_prompt

            elif isinstance(step, TaskStep):
                step_data["task"] = step.task

            elif isinstance(step, ToolCallStep):
                step_data["model_input"] = step.model_input_messages
                step_data["tool_name"] = step.tool_name
                step_data["tool_args"] = str(step.tool_args)
                step_data["tool_result"] = str(step.tool_result)

            elif isinstance(step, SqlStep):
                step_data["model_input"] = step.model_input_messages
                step_data["sql"] = step.sql
                step_data["sql_result"] = str(step.sql_result)

            elif isinstance(step, ActionStep):
                step_data["model_output"] = step.model_output

            steps_data.append(step_data)

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump({"steps": steps_data}, f, indent=2, ensure_ascii=False)