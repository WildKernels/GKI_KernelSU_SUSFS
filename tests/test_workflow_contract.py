import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class WorkflowContractTests(unittest.TestCase):
    def read(self, relative_path: str) -> str:
        return (ROOT / relative_path).read_text(encoding="utf-8")

    def test_dispatch_offers_all_root_solutions(self) -> None:
        workflow = self.read(".github/workflows/main.yml")

        for option in ("NONE", "KERNELSU", "SUKISU_ULTRA", "KERNELSU_NEXT", "KOWSU"):
            self.assertIn(f"- {option}", workflow)

    def test_validation_restricts_kpm_to_sukisu_ultra(self) -> None:
        action = self.read(".github/actions/validate-feature-selection/action.yml")

        self.assertIn('"$kpm" == "true" && "$root" != "SUKISU_ULTRA"', action)

    def test_branding_contains_both_approved_suffixes(self) -> None:
        action = self.read(".github/actions/apply-kernel-branding/action.yml")

        self.assertIn("@Coolpak@Kugouzei_NB_LKM", action)
        self.assertIn("@Coolpak@Kugouzei_NB_GKI", action)

    def test_kpm_patch_runs_after_kernel_compilation(self) -> None:
        action = self.read(".github/actions/build-kernel/action.yml")

        self.assertLess(action.index("- name: 'Build Kernel'"), action.index("- name: Apply KPM Image Patch"))


if __name__ == "__main__":
    unittest.main()
