import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class ProvenanceTest(unittest.TestCase):
    def test_local_defaults_do_not_claim_upstream(self):
        dockerfile = (ROOT / "Dockerfile").read_text()
        self.assertRegex(dockerfile, r"ARG BUILD_SOURCE=unknown")
        self.assertRegex(dockerfile, r"ARG BUILD_REVISION=unknown")

    def test_ci_uses_actual_repository_and_revision(self):
        workflow = (ROOT / ".github/workflows/docker-publish.yml").read_text()
        self.assertIn("BUILD_SOURCE=https://github.com/${{ github.repository }}", workflow)
        self.assertIn("BUILD_REVISION=${{ github.sha }}", workflow)

    def test_labels_are_source_and_revision_labels(self):
        dockerfile = (ROOT / "Dockerfile").read_text()
        for label in (
            "org.opencontainers.image.source",
            "org.opencontainers.image.revision",
            "org.opencontainers.image.version",
            "org.opencontainers.image.created",
        ):
            self.assertIn(label, dockerfile)


if __name__ == "__main__":
    unittest.main()
