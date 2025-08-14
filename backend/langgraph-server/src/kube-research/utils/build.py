from subgraphs.planner_research.planner_graph import PlannerResearchGraph
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.tools import BaseTool

def build_planner_research_graph(reasoning_llm : BaseChatModel , one_shot_llm : BaseChatModel):
    return PlannerResearchGraph(reasoning_llm=reasoning_llm , one_shot_llm=one_shot_llm)()

