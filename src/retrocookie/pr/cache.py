"""Application cache."""
import contextlib
import json
from pathlib import Path
from typing import cast
from typing import Iterator

import appdirs

from . import appname
from retrocookie import git


path = Path(appdirs.user_cache_dir(appname=appname, appauthor=appname))
token_file = path / "token.json"
repositories = path / "repositories"
worktrees = path / "worktrees"


def save_token(token: str) -> None:
    """Save a token."""
    if not token:
        raise RuntimeError("empty token")
    path.mkdir(exist_ok=True, parents=True)
    data = {"token": token}
    with open(token_file, "w") as io:
        json.dump(data, io)


def load_token() -> str:
    """Load a token."""
    with open(token_file) as io:
        data = json.load(io)
    if not data["token"]:
        raise RuntimeError("empty token")
    return cast(str, data["token"])


def repository(owner: str, repository: str) -> git.Repository:
    """Clone or update repository."""
    url = f"https://github.com/{owner}/{repository}.git"
    path = repositories / owner / f"{repository}.git"

    if path.exists():
        git.git("remote", "update", cwd=path)
    else:
        git.git("clone", "--mirror", url, str(path))

    return git.Repository(path)


@contextlib.contextmanager
def worktree(
    owner: str,
    repository: str,
    branch: str,
    *,
    base: str = "HEAD",
    force: bool = False,
) -> Iterator[git.Repository]:
    """Context manager to add and remove a worktree."""
    repo = git.Repository(repositories / owner / f"{repository}.git")
    path = worktrees / owner / repository / branch

    with repo.worktree(
        branch, path, base=base, force=force, force_remove=True
    ) as worktree:
        yield worktree
