from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

from .models import Decision


class VaultMemory:
    def __init__(self, vault: Path) -> None:
        self.vault = vault

    def write_decision(self, d: Decision) -> Path:
        target = self.vault / "Decisions" / f"{d.timestamp[:10]}-{d.decision_id}.md"
        frontmatter = {k: v for k, v in d.to_dict().items() if k != "rationale"}
        body = "---\n" + "\n".join(f"{k}: {json.dumps(v)}" for k, v in frontmatter.items()) + "\n---\n\n"
        body += f"# Market decision {d.decision_id}\n\n## Rationale\n\n{d.rationale}\n\n## Evidence\n\nData SHA-256: `{d.data_sha256}`\n"
        target.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(prefix=target.name, dir=target.parent)
        try:
            with os.fdopen(fd, "w") as handle:
                handle.write(body)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(tmp, target)
        finally:
            if os.path.exists(tmp):
                os.unlink(tmp)
        return target

