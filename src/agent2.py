import json
import logging
from jinja2 import Template
import yaml
from typing import Callable, List, Dict, Any, Optional

from .executor import Executor
from .reasoner2 import Reasoner
from .memory2 import AgentMemory, ActionStep, FinalStep, Message, MessageRole, ModelOutputMessage, StartStep, TaskStep
from .tool import Tool
import re
import os
from .dbinspector import extract_table_metadata


class PromptTemplate:
    def __init__(self, template_str: str):
        self.template_str = template_str

    def format(self, **kwargs):
        return Template(self.template_str).render(**kwargs)

    @classmethod
    def from_template(cls, template_str: str) -> "PromptTemplate":
        return cls(template_str)


class AgentBase:
    def __init__(
        self,
        tools: List[Tool],
        model: Callable[[List[Dict[str, str]]], Any],
        max_steps: int = 11,
        prompt_config_path: str = "prompt/sql_agent_prompts.yaml",
    ):
        self.model = model
        self.step_number = 1
        self.max_steps = max_steps
        self.memory = AgentMemory()
        self.verbose = True
        if not os.path.exists(prompt_config_path):
            raise FileNotFoundError(
                f"Prompt config file not found: {prompt_config_path}")
        with open(prompt_config_path, "r", encoding="utf-8") as f:
            self.prompt_config = yaml.safe_load(f)

        self.system_prompt = self.prompt_config.get("system_prompt", "")
        self.memory.steps.append(StartStep(self.system_prompt))
        self.logger = logging.getLogger(__name__)

    def run(
        self,
        task: str,
        user_extra_info: str = "",
        additional_args: Optional[Dict] = None,
        max_steps: Optional[int] = None,
    ):
        max_steps = max_steps or self.max_steps
        self.task = task
        self.memory.steps.append(TaskStep(task))
        self.user_extra_info = user_extra_info
        db_path = additional_args.get(
            "db_path") if additional_args else "example.db"
        self.db_path = db_path
        self.reasoner = Reasoner(
            model=self.model,
            memory=self.memory,
            question=task,
            db_path=db_path,
            prompt_config=self.prompt_config,
            user_extra_info=self.user_extra_info,
        )
        self.executor = Executor(db_path=db_path)
        for step_id in range(0, max_steps):
            self.step_number = step_id
            print(f"\n🔁 Step {step_id}")

            step_result = self.step(self.step_number, db_path)

            if not step_result:
                print("⚠️ 当前 step 未返回有效结果，终止执行。")
                return None

            if "final_answer" in step_result:
                print("final_answer", step_result)
                self.memory.export_json("trace_record.json")
                self.memory.save_trace_to_markdown("trace_output.md")
                return step_result

            if "next_action" in step_result and "step_text" in step_result:
                action = step_result["next_action"]
                step_text = step_result["step_text"]

                if action == "sql":
                    execution_result = self.reasoner.run_sql_step(step_text)
                elif action == "tool":
                    execution_result = self.reasoner.run_tool_step(step_text)
                else:
                    return {"final_answer": f"Unknown execution type: {action}"}

                if execution_result and "final_answer" in execution_result:
                    return execution_result
            else:
                continue

        print("\n⚠️ Agent reached max steps without finding a final answer.")
        return None

    def initial_plan(self, db_path: str) -> dict:
        """生成 planner 初始分析内容，提取 initial_sql 并执行测试，返回其他结构信息"""
        init_plan_template_str = self.prompt_config["planning"]["init_plan_EN"]
        template = Template(init_plan_template_str)
        rendered_prompt = template.render(
            task=self.task,
            extra=self.user_extra_info,
            table_data=extract_table_metadata(db_path)
        )
        messages = [{"role": "user", "content": rendered_prompt}]
        output = self.model(messages=messages)
        content = output["message"].content.strip()
        print("\n🧠 初始规划输出：\n", content)

        try:
            json_match = re.search(r"```json\n(.*?)```", content, re.DOTALL)
            # initial_step = ActionStep(
            #     step_number=0,
            #     model_input_messages=[{"role": "user", "content": rendered_prompt}],
            #     model_output_message=ModelOutputMessage(
            #         content=content,
            #         raw=output
            #     ),
            #     model_output=content,
            #     observations=self.initial_sql.get("sql_answer", "")
            # )
            # self.memory.steps.append(initial_step)

            if json_match:
                json_str = json_match.group(1)
                parsed = json.loads(json_str)

                # 提取 initial_sql 并执行
                self.initial_sql = parsed.get("initial_sql", {})  # ✅ 单独存储
                sql = self.initial_sql.get("sql", None)

                if sql:
                    result = self.executor.execute_sql(sql)
                    if result["status"] == "error":
                        self.initial_sql["sql_answer"] = f"Error: {result['error']['message']}"
                    else:
                        self.initial_sql["sql_answer"] = f"Result: {result['result']}"
                else:
                    self.initial_sql["sql_answer"] = "No SQL found."

                # 删除原始 JSON 中的 initial_sql，避免重复
                parsed.pop("initial_sql", None)
                return parsed

        except Exception as e:
            self.initial_sql = {
                "sql": "",
                "comments": [],
                "sql_answer": f"❌ SQL 执行异常: {str(e)}"
            }
            return {
                "task_understanding": "",
                "extra_understanding": "",
                "table_analysis": {},
                "relevant_tables": {"tables": [], "reasons": {}}
            }

    # def step(self, step_number: int, db_path: str) -> Optional[dict]:
    #     try:
    #         # 第一步单独用 initial_plan
    #         if step_number == 0:
    #             initial_thought = self.initial_plan(db_path)
    #             print("initial_thought:", initial_thought)
    #             self.initial_plan_data = initial_thought
    #             return initial_thought

    #         # 非第一步由 reasoner 决策
    #         plan_output = self.think(step_number)

    #         if isinstance(plan_output, dict) and "final_answer" in plan_output:
    #             return plan_output
    #         step_description = plan_output.get("step_text") if isinstance(
    #             plan_output, dict) else plan_output
    #         if re.search(r"<final_answer>.*?<\final_answer>", step_description, re.DOTALL):
    #             return {"final_answer": "No reasoning step."}

    #         if re.search(r"<tool_executor>.*?</tool_executor>", step_description, re.DOTALL):
    #             return {"next_action": "tool", "step_text": step_description}

    #         return {"next_action": "sql", "step_text": step_description}

    #     except Exception as e:
    #         return {"final_answer": f"Exception occurred: {e}"}
    #     # 不要直接final

    def step(self, step_number: int, db_path: str) -> Optional[dict]:
        try:
            # 第一步单独用 initial_plan
            if step_number == 0:
                initial_thought = self.initial_plan(db_path)
                print("initial_thought:", initial_thought)
                self.initial_plan_data = initial_thought
                return initial_thought

            # 非第一步由 reasoner 决策
            plan_output = self.think(step_number)

            # 判断是否为 final_answer 类型结构（包含 final_sql 字段）
            if isinstance(plan_output, dict) and "final_sql" in plan_output:
                return {
                    "final_answer": {
                        "final_sql": plan_output.get("final_sql", ""),
                        "final_result": plan_output.get("final_result", ""),
                        "explanation": plan_output.get("explanation", ""),
                        "full_text": plan_output.get("full_text", "")
                    }
                }

            # 提取思考内容 step_text
            if isinstance(plan_output, dict):
                step_description = plan_output.get("step_text", "")
            else:
                step_description = str(plan_output)

            # 判断是否包含 <final_answer> 标签
            if re.search(r"<final_answer>.*?<\final_answer>", step_description, re.DOTALL):
                return {"final_answer": "No reasoning step."}

            # 判断是否为工具调用
            if re.search(r"<tool_executor>.*?</tool_executor>", step_description, re.DOTALL):
                return {"next_action": "tool", "step_text": step_description}

            # 默认是 SQL 类型操作
            return {"next_action": "sql", "step_text": step_description}

        except Exception as e:
            return {"final_answer": f"Exception occurred: {e}"}

    def think(self, step_number) -> Optional[dict]:
        prompt = PromptTemplate.from_template(
            self.prompt_config["planning"]["unified_plan"]
        ).format(
            task=self.task,
            observation_history=self.memory.get_observation_history(),
            user_extra=self.user_extra_info,
            step=str(step_number),
            all_table_data=extract_table_metadata(self.db_path),
        )
        print("memory-----")
        print(self.memory.get_observation_history())
        print("memory-----")
        messages = [
            {"role": MessageRole.USER.value, "content": prompt.strip()},
        ]
        if step_number == 1:
            print(messages)
        output = self.model(messages=messages)
        message = output["message"]
        if not message:
            raise ValueError("Model did not return a valid message")
        step_text = message.content.strip()
        if self.verbose:
            print("\n🧠 Step description:\n", step_text)

        if "<final_answer>" in step_text.lower():
            # ✅ 提取内容，忽略大小写 + 跨行匹配
            raw_sql = ""
            raw_result = ""
            explanation = ""

            # 提取 Sql 块
            match_sql = re.search(r"Sql:\s*(.+?)\nResult:",
                                  step_text, re.IGNORECASE | re.DOTALL)
            if match_sql:
                raw_sql = match_sql.group(1).strip()

            # 提取 Result 块
            match_result = re.search(
                r"Result:\s*(.+?)\nAnswer:", step_text, re.IGNORECASE | re.DOTALL)
            if match_result:
                raw_result = match_result.group(1).strip()

            # 提取 Answer 块
            match_expl = re.search(
                r"Answer:\s*(.+?)</final_answer>", step_text, re.IGNORECASE | re.DOTALL)
            if match_expl:
                explanation = match_expl.group(1).strip()
            
            print("final::",raw_sql,raw_result,explanation)
            self.memory.steps.append(FinalStep(
                step_number=self.step_number,
                sql=raw_sql,
                result=raw_result,
                explanation=explanation,
                full_text=step_text
            ))

            return {
                "final_sql": raw_sql,
                "final_result": raw_result,
                "explanation": explanation,
                "full_text": step_text,
            }
        return {"step_text": step_text}
