from urllib.parse import urlencode

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
        arguments = urlencode(
            {
                "query": tool_input.tool_args["query"],
                "limit": tool_input.tool_args["limit"],
            }
        )
        return await coordinator.client.get(f"/v1/memory/search?{arguments}")


class ExplainBeliefsTool(llm.Tool):
    name = "ExplainHomeclawBeliefs"
    description = "Return current beliefs with evidence IDs, confidence, and expiry."

    async def async_call(self, hass, tool_input: ToolInput, llm_context: LLMContext):
        del tool_input, llm_context
        coordinator = next(iter(hass.data[DOMAIN].values()))
        return await coordinator.client.get("/v1/beliefs")


class GetWorldStateTool(llm.Tool):
    name = "GetHomeclawWorldState"
    description = "Return authoritative working state, source health, and active beliefs."

    async def async_call(self, hass, tool_input: ToolInput, llm_context: LLMContext):
        del tool_input, llm_context
        coordinator = next(iter(hass.data[DOMAIN].values()))
        return await coordinator.client.get("/v1/world")


class GetStandingIntentsTool(llm.Tool):
    name = "GetHomeclawStandingIntents"
    description = "Inspect confirmed, notification-only future household intentions."

    async def async_call(self, hass, tool_input: ToolInput, llm_context: LLMContext):
        del tool_input, llm_context
        coordinator = next(iter(hass.data[DOMAIN].values()))
        return await coordinator.client.get("/v1/standing-intents")


class ReadHouseJournalTool(llm.Tool):
    name = "ReadHomeclawHouseJournal"
    description = (
        "Read evidence-linked Homeclaw observations, hypotheses, conclusions, revisions, "
        "and hour/day/week rollups. Journal prose is interpretation; inspect its evidence IDs."
    )
    parameters = vol.Schema(
        {
            vol.Optional("room"): vol.In(
                [
                    "house",
                    "occupancy",
                    "security",
                    "comfort_iaq",
                    "energy",
                    "equipment",
                    "network",
                ]
            ),
            vol.Optional("level"): vol.In(
                ["event", "situation", "hour", "day", "week", "month", "season"]
            ),
            vol.Optional("limit", default=20): vol.All(int, vol.Range(min=1, max=50)),
        }
    )

    async def async_call(self, hass, tool_input: ToolInput, llm_context: LLMContext):
        del llm_context
        coordinator = next(iter(hass.data[DOMAIN].values()))
        arguments = urlencode(
            {key: value for key, value in tool_input.tool_args.items() if value is not None}
        )
        return await coordinator.client.get(f"/v1/journal/entries?{arguments}")


@callback
def async_get_tools(
    hass: HomeAssistant, llm_context: LLMContext, api_id: str
) -> llm.LLMTools | None:
    del llm_context, api_id
    if not hass.data.get(DOMAIN):
        return None
    return llm.LLMTools(
        tools=[
            SearchTimelineTool(),
            ExplainBeliefsTool(),
            GetWorldStateTool(),
            GetStandingIntentsTool(),
            ReadHouseJournalTool(),
        ],
        prompt=(
            "Use Homeclaw tools only to query shared household evidence and explanations. "
            "House Journal text is derived interpretation, so retain its evidence lineage. "
            "These tools do not expose device control."
        ),
    )
