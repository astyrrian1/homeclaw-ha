import voluptuous as vol
from homeassistant.components import llm
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.llm import LLMContext, ToolInput

from .const import DOMAIN


class SearchTimelineTool(llm.Tool):
    name = "SearchHomeclawTimeline"
    description = "Search recent evidence and episodes in shared household memory."
    parameters = vol.Schema(
        {
            vol.Required("query"): str,
            vol.Optional("limit", default=20): vol.All(int, vol.Range(min=1, max=50)),
        }
    )

    async def async_call(self, hass, tool_input: ToolInput, llm_context: LLMContext):
        del llm_context
        coordinator = next(iter(hass.data[DOMAIN].values()))
        response = await coordinator.client.get(
            f"/v1/timeline?limit={tool_input.tool_args['limit']}"
        )
        query = tool_input.tool_args["query"].casefold()
        return {
            "items": [item for item in response.get("items", []) if query in str(item).casefold()]
        }


class ExplainBeliefsTool(llm.Tool):
    name = "ExplainHomeclawBeliefs"
    description = "Return current beliefs with evidence IDs, confidence, and expiry."

    async def async_call(self, hass, tool_input: ToolInput, llm_context: LLMContext):
        del tool_input, llm_context
        coordinator = next(iter(hass.data[DOMAIN].values()))
        return await coordinator.client.get("/v1/beliefs")


@callback
def async_get_tools(
    hass: HomeAssistant, llm_context: LLMContext, api_id: str
) -> llm.LLMTools | None:
    del llm_context, api_id
    if not hass.data.get(DOMAIN):
        return None
    return llm.LLMTools(
        tools=[SearchTimelineTool(), ExplainBeliefsTool()],
        prompt=(
            "Use Homeclaw tools only to query shared household evidence and explanations. "
            "They do not expose device control."
        ),
    )
