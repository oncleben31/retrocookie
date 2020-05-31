"""Core module."""
import json
from pathlib import Path
from typing import cast
from typing import Container
from typing import Dict
from typing import Optional

from . import git
from .filter import RepositoryFilter
from .utils import temporary_remote
from .utils import temporary_repository


def guess_instance_url(repository: git.Repository) -> str:
    """Guess the URL of the template instance."""
    url = repository.get_remote_url("origin")
    if url.endswith(".git"):
        url = url[: -len(".git")]
        return f"{url}-instance.git"
    return f"{url}-instance"


def find_template_directory(repository: git.Repository) -> Path:
    """Locate the subdirectory with the project template."""
    tokens = "{{", "cookiecutter", "}}"
    for path in repository.path.iterdir():
        if path.is_dir() and all(x in path.name for x in tokens):
            return path.relative_to(repository.path)
    raise Exception("cannot find template directory")


def load_context(repository: git.Repository) -> Dict[str, str]:
    """Load the context from the .cookiecutter.json file."""
    path = repository.path / ".cookiecutter.json"
    with path.open() as io:
        return cast(Dict[str, str], json.load(io))


def rewrite_commits(
    repository: git.Repository,
    template_directory: Path,
    whitelist: Container[str],
    blacklist: Container[str],
) -> None:
    """Rewrite the repository using template variables."""
    context = load_context(repository)
    RepositoryFilter(
        repository=repository,
        path=template_directory,
        context=context,
        whitelist=whitelist,
        blacklist=blacklist,
    ).run()


def apply_commits(
    repository: git.Repository, remote: str, base: str, ref: str, branch: Optional[str],
) -> None:
    """Create <branch> with commits from <remote>/<base>..<remote>/<ref>."""
    if branch is None:
        branch = ref

    current = repository.get_current_branch()
    repository.fetch_remote(remote, base, ref)
    repository.create_branch(branch, f"{remote}/{ref}")
    repository.rebase(upstream=f"{remote}/{base}", branch=branch, onto=current)


def retrocookie(
    ref: str,
    *,
    base: str = "master",
    branch: Optional[str] = None,
    url: Optional[str] = None,
    whitelist: Container[str] = (),
    blacklist: Container[str] = (),
    path: Optional[Path] = None,
) -> None:
    """Import commits from instance repository into template repository."""
    repository = git.Repository(path)
    template_directory = find_template_directory(repository)
    remote = "retrocookie"

    if url is None:
        url = guess_instance_url(repository)

    with temporary_repository(url) as instance:
        rewrite_commits(instance, template_directory, whitelist, blacklist)

        with temporary_remote(repository, remote, str(instance.path)):
            apply_commits(repository, remote, base, ref, branch)