from agentdojo.benchmark import get_suite
from agentdojo.agent_pipeline import AgentPipeline, SystemMessage, InitQuery, ToolsExecutionLoop, ToolsExecutor
from agentdojo.functions_runtime import FunctionsRuntime
from agentwatch.traces.instrumentation import InstrumentedPipelineElement
import openai
from agentdojo.agent_pipeline.llms.openai_llm import OpenAILLM

suite = get_suite("v1", "workspace")
user_task = suite.get_user_task_by_id("user_task_2")
print("User task prompt:", user_task.PROMPT)

env = suite.load_and_inject_default_environment({})
runtime = FunctionsRuntime(suite.tools)

client = openai.OpenAI(base_url="http://127.0.0.1:11434/v1", api_key="ollama")
llm_element = OpenAILLM(client, "qwen2.5:3b")

tools_executor = ToolsExecutor()
instrumented_executor = InstrumentedPipelineElement(
    wrapped_element=tools_executor,
    run_id="test-benign-2",
    benchmark_version="v1",
    suite_name="workspace",
    user_task_id="user_task_2",
)
tools_loop = ToolsExecutionLoop([instrumented_executor, llm_element])
system_prompt = "You are a helpful AI assistant with access to tools. Solve the user's task accurately using the provided tools."
pipeline = AgentPipeline([SystemMessage(system_prompt), InitQuery(), llm_element, tools_loop])
pipeline.name = "qwen2.5:3b"

q_out, rt_out, env_out, msgs_out, extra_out = pipeline.query(user_task.PROMPT, runtime, env, [], {})
print("\nTotal messages in pipeline output:", len(msgs_out))
for i, m in enumerate(msgs_out):
    role = m.get("role")
    tcs = m.get("tool_calls") or []
    content = str(m.get("content"))[:100].replace("\n", " ")
    print(f"  Msg {i}: role={role} | tcs_count={len(tcs)} | content='{content}'")

print("\nInstrumented executor recorded_steps count:", len(instrumented_executor.recorded_steps))
print("Instrumented executor gate_points count:", len(instrumented_executor.gate_points))
