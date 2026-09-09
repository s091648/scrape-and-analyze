import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from scripts import generate_terraform_docs as gtd  # noqa: E402


def test_source_paths_point_at_the_migrated_github_terraform_dir():
    """Regression guard: `infra/terraform/railway` was renamed to
    `infra/terraform/github`; TF_ROOT (and MANIFEST / GITHUB_CI_TF derived from
    it) must follow, or `make uml-terraform-docs` / the speckit-github-pages
    workflow reads files that no longer exist at the old path."""
    assert gtd.TF_ROOT.parts[-2:] == ("terraform", "github")
    assert gtd.MANIFEST == gtd.TF_ROOT / "railway-services.json"
    assert gtd.GITHUB_CI_TF == gtd.TF_ROOT / "github-ci.tf"
    assert gtd.RAILWAY_TS.parts[-2:] == (".railway", "railway.ts")

    # When the infra tree is present (host / docs job — it isn't mounted into
    # the unit-test container), the resolved paths must actually exist.
    if (gtd.REPO_ROOT / "infra").is_dir():
        assert gtd.TF_ROOT.is_dir()
        assert gtd.MANIFEST.is_file()
        assert gtd.GITHUB_CI_TF.is_file()
        assert gtd.RAILWAY_TS.is_file()
