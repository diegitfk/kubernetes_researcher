from subgraphs.planner_research.planner_graph import PlannerResearchGraph
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.tools import BaseTool

def build_planner_research_graph(llm : BaseChatModel):
    return PlannerResearchGraph(llm=llm)()

