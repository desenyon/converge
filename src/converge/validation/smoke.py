
from converge.solver.planner import RepairPlan
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

            # Smoke tests: ensure we can import the target packages
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
        Scores multiple plans by attempting them in isolated sandboxes.
        Returns a dict mapping plan ID to Success (True/False).
        """
        results = {}
        for plan in plans:
            success = self.validate_plan(plan, smoke_imports)
            results[plan.id] = success
        return results
