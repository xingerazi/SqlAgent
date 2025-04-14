import streamlit as st
import os
import tempfile
from src.agent2 import AgentBase
from src.model import OpenAIServerModel
from src.dbinspector import extract_schema_from_sqlite
from src.memory2 import ActionStep, SqlStep, ToolCallStep

# ===== 读取所有数据库路径 =====
def find_all_sqlite_dbs(base_path="dataset/birdsql_dev/dev_databases"):
    preset_dbs = {}
    for folder in os.listdir(base_path):
        folder_path = os.path.join(base_path, folder)
        if os.path.isdir(folder_path):
            for file in os.listdir(folder_path):
                if file.endswith(".sqlite"):
                    db_name = folder.replace("_", " ").title()
                    preset_dbs[db_name] = os.path.join(folder_path, file)
    return preset_dbs

# ===== 初始化页面 =====
st.set_page_config(page_title="SQL Agent", layout="wide")
st.title("🧠 SQL Agent")

# ===== 加载模型和 Agent =====
@st.cache_resource
def load_agent():
    model = OpenAIServerModel(
        model_id="gpt-4o",
        base_url="https://apix.wumingai.com/v1",
        api_key="sk-wd1RT6fTZYqhvrSgC3A1D01905934fA4A059Af4b75975f44",  
    )
    return AgentBase(
        tools=[],
        model=model,
        prompt_config_path="./src/prompt/sql_agent_prompts.yaml"
    )

agent = load_agent()

# ===== 侧边栏：数据库选择 =====
st.sidebar.header("📂 数据库选择")
preset_dbs = find_all_sqlite_dbs()
db_name = st.sidebar.selectbox("选择预设数据库", list(preset_dbs.keys()))
selected_db_path = preset_dbs[db_name]

uploaded_file = st.sidebar.file_uploader("或者上传 SQLite 文件", type=["sqlite", "db"])
if uploaded_file:
    with tempfile.NamedTemporaryFile(delete=False, suffix=".sqlite") as tmpfile:
        tmpfile.write(uploaded_file.read())
        selected_db_path = tmpfile.name

st.markdown(f"✅ 当前数据库路径：`{selected_db_path}`")

# ===== 展示表结构 =====
try:
    schema_info = extract_schema_from_sqlite(selected_db_path, num_rows=2)
    table_names = [t['table_name'] for t in schema_info["tables"]]
    st.sidebar.subheader("📋 数据库中的表")
    st.sidebar.json(table_names)
except Exception as e:
    st.error(f"❌ 读取数据库结构失败：{e}")
    st.stop()

# ===== 用户输入任务 =====
st.subheader("📝 输入任务")
task = st.text_area("任务指令（自然语言）", placeholder="例如：查找价格最高的商品", height=100)
user_hint = st.text_area("💡 可选提示信息（如字段解释）", height=70)

# ===== 执行任务 =====
if st.button("🚀 执行任务"):
    if not task:
        st.warning("请先输入任务内容")
        st.stop()
    agent.memory.reset()
    with st.spinner("模型正在推理中..."):
        try:
            result = agent.run(task=task, user_extra_info=user_hint, additional_args={"db_path": selected_db_path})
            st.success("✅ 执行完成")

            # ===== 显示最终结果 =====
            st.subheader("📤 最终结果")
            final = result.get("final_answer", {})
            if isinstance(final, dict):
                # st.markdown("📤 <span style='font-size:24px; font-weight:bold;'>最终结果</span>", unsafe_allow_html=True)

                st.markdown(f"🧠 <span style='font-size:24px; font-weight:bold;'>Explanation:</span> <span style='font-size:18px'>{final.get('explanation', '无')}</span>", unsafe_allow_html=True)

                st.markdown(f"📊 <span style='font-size:24px; font-weight:bold;'>Result:</span>", unsafe_allow_html=True)
                st.code(final.get("final_result", ""), language="text")

                st.markdown(f"🧾 <span style='font-size:24px; font-weight:bold;'>SQL:</span>", unsafe_allow_html=True)
                st.code(final.get("final_sql", ""), language="sql")
            else:
                st.warning(f"⚠️ {final}")

            # ===== 每步推理过程（只展示核心三种类型） =====
            st.subheader("🧠 推理过程步骤")
            for step in agent.memory.steps:
                if isinstance(step, ActionStep):
                    st.markdown("#### 🧠 Finalstep")
                    st.code(step.model_output.strip(), language="markdown")

                elif isinstance(step, SqlStep):
                    st.markdown("#### 📝 SQL 执行")
                    st.code(step.sql, language="sql")
                    st.markdown("**结果：**")
                    st.write(step.sql_result)

                elif isinstance(step, ToolCallStep):
                    st.markdown(f"#### 🛠️ 工具 `{step.tool_name}` 调用")
                    st.code(step.model_input_messages.strip(), language="markdown")
                    st.markdown("**参数：**")
                    st.json(step.tool_args)
                    st.markdown("**返回结果：**")
                    st.json(step.tool_result)

        except Exception as e:
            st.error(f"❌ 执行出错：{e}")