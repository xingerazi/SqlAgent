from typing import List, Dict, Any, Optional
from dataclasses import dataclass

from .tool import Tool
from .memory2 import AgentMemory, ActionStep, Message, MessageRole, ModelOutputMessage, SqlStep, ToolCallStep
from .executor import Executor
import logging
import re
from jinja2 import Template
from .dbinspector import extract_table_metadata


class PromptTemplate:
    def __init__(self, template_str: str):
        self.template_str = template_str

    def format(self, **kwargs):
        return Template(self.template_str).render(**kwargs)

    @classmethod
    def from_template(cls, template_str: str) -> "PromptTemplate":
        return cls(template_str)


class Reasoner:
    def __init__(
        self,
        model: Any,
        memory: AgentMemory,
        question: str,
        prompt_config: Optional[Dict[str, Any]] = None,
        verbose: bool = True,
        max_rounds: int = 3,
        db_path: str = "example.db",
        user_extra_info: str = "",
        tools_list: Optional[List[str]] = None,
    ):
        self.model = model
        self.memory = memory
        self.question = question
        self.verbose = verbose
        self.step_number = 0
        self.max_rounds = max_rounds
        self.logger = logging.getLogger(__name__)
        self.executor = Executor(db_path=db_path)
        self.prompt_config = prompt_config or {}
        self.user_extra_info = user_extra_info
        self.tools_list = tools_list or []
        self.db_path = db_path
        self._init_prompt_template()

    def _init_prompt_template(self):
        list_tables_func = Tool.registry["extract_table_metadata"]
        result = list_tables_func.forward(
            list_tables_func, db_path=self.executor.db_path)

        if isinstance(result, dict) and not "error" in result:
            all_table_data = ", ".join(result.keys())
        else:
            all_table_data = "(unavailable)"

        self.list_tables = all_table_data

        raw_system_prompt = self.prompt_config.get("system_prompt", "")
        self.system_prompt = raw_system_prompt.strip()

    def run_sql_step(self, step_description: str) -> Optional[dict]:
        self.step_number += 1
        history = self.memory.get_observation_history()
        exec_template_str = self.prompt_config["execution"]["sql_code_step"]
        exec_template_str = exec_template_str.replace(
            "{{db_path}}", self.db_path)
        exec_template = PromptTemplate.from_template(exec_template_str)

        prompt = exec_template.format(
            task=self.question,
            current_step=step_description,
            observation_history=history,
            user_extra=self.user_extra_info,
            all_table_data=self.list_tables
        )

        messages = [
            {"role": MessageRole.USER.value, "content": prompt.strip()},
        ]

        attempt = 0
        model_output_text = ""
        error_msg = ""

        while attempt < self.max_rounds:
            try:
                model_output = self.model(messages=messages)
                print("🤖 model_output:", model_output)

                message = model_output["message"]  # ✅ 提取 message 对象
                model_output_text = message.content.strip()

                sql = self._extract_sql(model_output_text)
                result = self.executor.execute_sql(sql)

                if result["status"] == "error":
                    raise RuntimeError(result["error"]["message"])

                output = result["result"]

                # ✅ 保存到 memory
                sql_step = SqlStep(
                    step_number=self.step_number,
                    sql=sql,
                    sql_result=output,
                    model_input_messages=self._extract_text(step_description),
                    model_output_message=ModelOutputMessage(
                        content=model_output_text,
                        raw=model_output,
                    )
                )
                self.memory.steps.append(sql_step)

                return {
                    "observation": output,
                    "executed_sql": sql
                }

            except Exception as e:
                error_msg = str(e)
                print(
                    f"⚠️ Execution failed (attempt {attempt + 1}): {error_msg}")
                attempt += 1

        # 失败
        failed_observation = {
            "error": f"Execution failed after {self.max_rounds} attempts: {error_msg}"
        }

        err_step = SqlStep(
            step_number=self.step_number,
            sql=sql,
            sql_result=str(failed_observation),
            model_input_messages=self._extract_text(step_description),
            model_output_message=ModelOutputMessage(
                content=model_output_text,
                raw=model_output,
            )

        )
        self.memory.steps.append(err_step)

        print("🚫 Maximum retry attempts reached.")
        return {
            "observation": failed_observation,
            "executed_sql": None
        }

    def _extract_sql(self, text: str) -> str:
        match = re.search(r"```sql\n(.*?)```", text, re.DOTALL | re.IGNORECASE)
        if match:
            return match.group(1).strip()
        return text.strip()

    def _extract_text(self, text: str) -> str:
        match = re.search(r"Reasoning:\s*(.*?)\s*SQL:", text, re.DOTALL)
        return match.group(1).strip() if match else ""

    def run_tool_step(self, step_description: str) -> Optional[dict]:
        # self.step_number += 1
        # print(f"🔧 执行工具调用: step {self.step_number}")
        #         unified_plan_str = self.prompt_config["planning"]["unified_plan"]
        # unified_plan_str = unified_plan_str.replace("{{all_table_names}}", all_table_names)
        # self.plan_prompt = PromptTemplate.from_template(unified_plan_str)
        try:
            # 提取工具名和参数
            match = re.search(
                r"<tool_executor>\s*(.*?)\s*</tool_executor>", step_description, re.DOTALL)
            if not match:
                raise ValueError("未找到 tool_executor 标签")

            inner_call = match.group(1).strip()
            # print("🧩 工具调用内容:", inner_call)

            self.step_number += 1
            exec_template_str = self.prompt_config["execution"]["tool_call_step"]
            exec_template_str = exec_template_str.replace(
                "{{db_path}}", self.db_path)
            self.tool_call_prompt = PromptTemplate.from_template(
                exec_template_str)
            prompt = self.tool_call_prompt.format(
                task=self.question,
                current_step=inner_call,
                observation_history=self.memory.get_observation_history(),
                user_extra=self.user_extra_info,
                all_table_data=self.list_tables
            )
            messages = [
                # {"role": MessageRole.SYSTEM.value, "content": self.system_prompt},
                {"role": MessageRole.USER.value, "content": prompt.strip()},
            ]
            # print("🤖 model_input: run_tool_step:", messages)
            model_result = self.model(messages=messages, pass_tools=True)
            tool_results = model_result.get("tool_results", {})
            print("tool-res----:", model_result)
            message_obj = model_result["message"]
            tool_call_obj = message_obj.tool_calls[0]
            tool_name = tool_call_obj.function.name
            tool_args = tool_call_obj.function.arguments

            # ✅ 保存结果
            tool_step = ToolCallStep(
                step_number=self.step_number,
                tool_name=tool_name,
                tool_args=tool_args,
                tool_result=tool_results,
                model_input_messages=step_description,
                model_output_message=ModelOutputMessage(
                    content=inner_call,
                    raw=model_result,
                ),
            )
            self.memory.steps.append(tool_step)

            return {
                "observation": tool_results,
                "tool_invoked": inner_call
            }

        except Exception as e:
            self.step_number += 1
            error_msg = str(e)
            print(f"❌ Tool 执行出错: {error_msg}")

            failed_observation = {
                "error": f"Tool execution failed: {error_msg}"
            }

            tool_step = ToolCallStep(
                step_number=self.step_number,
                tool_name=tool_name,
                tool_args=tool_args,
                tool_result=tool_results,
                model_input_messages=step_description,
                model_output_message=ModelOutputMessage(
                    content=inner_call if 'inner_call' in locals() else "",
                    raw={"error": str(failed_observation),}
                ),
                
            )
            self.memory.steps.append(tool_step)

            return {
                "observation": failed_observation,
                "tool_invoked": None
            }
