from converge.solver.planner import RepairPlan, rank_plans
from converge.validation.sandbox import UVSandbox


class ValidationRunner:
    """
    Validates candidate repair plans by executing tests in a sandbox.
    """

    def __init__(self, sandbox: UVSandbox):
        self.sandbox = sandbox

    def validate_plan(self, plan: RepairPlan, smoke_imports: list[str]) -> bool:
        """
        Applies a plan to the sandbox and checks if smoke_imports are resolvable.
        """
        try:
            self.sandbox.create()
            self.sandbox.apply_plan(plan)

            success = True
            for imp in smoke_imports:
                if not self.sandbox.run_python_cmd(f"import {imp}"):
                    success = False
                    break

            return success
        except Exception:
            return False
        finally:
            self.sandbox.cleanup()

    def score_plans(self, plans: list[RepairPlan], smoke_imports: list[str]) -> dict[str, bool]:
        """
        Scores plans in ranked order (fewest changes first).
        Returns a dict mapping plan ID to Success (True/False).
        """
        results: dict[str, bool] = {}
        for plan in rank_plans(plans):
            results[plan.id] = self.validate_plan(plan, smoke_imports)
        return results

    def select_best_plan(
        self, plans: list[RepairPlan], smoke_imports: list[str]
    ) -> RepairPlan | None:
        for plan in rank_plans(plans):
            if self.validate_plan(plan, smoke_imports):
                return plan
        return None
