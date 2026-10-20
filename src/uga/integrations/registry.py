from uga.core.contracts import AgentKind, TaskSpec
from uga.orchestrator.worker import validate_task


class AgentRegistry:
    """Discover existing agents without depending on a particular external AI platform."""

    def describe(self):
        return {
            AgentKind.PLAYER: {
                "operations": ["play", "soak"],
                "contract": TaskSpec.model_json_schema(),
            },
            AgentKind.REVERSE: {"operations": ["analyze"], "requires_target_permission": True},
            AgentKind.BUILDER: {"operations": ["generate"]},
            AgentKind.WORKFLOW: {"operations": ["build-play"]},
        }

    def validate(self, task: TaskSpec):
        validate_task(task)
        return task
