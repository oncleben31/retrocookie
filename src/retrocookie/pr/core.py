"""Import pull requests."""
from __future__ import annotations

import contextlib
from dataclasses import dataclass
from typing import Iterable
from typing import Iterator
from typing import Optional
from urllib.parse import urlparse
from urllib.parse import urlunparse

from . import appname
from . import cache
from . import github
from .utils import removeprefix
from .utils import removesuffix
from retrocookie import git
from retrocookie import retrocookie
from retrocookie.core import load_context


@dataclass
class Repository:
    """High-level repository abstraction."""

    github: github.Repository
    clone: git.Repository
    owner: str
    name: str

    @classmethod
    def load(cls, gh: github.GitHub, repository: str) -> Repository:
        """Load all the data associated with a GitHub repository."""
        owner, name = repository.split("/", 1)
        return cls(
            github=gh.repository(owner, name),
            clone=cache.repository(owner, name),
            owner=owner,
            name=name,
        )


def get_pull_request(repository: Repository, spec: str) -> github.PullRequest:
    """Return the pull request matching the provided spec."""
    with contextlib.suppress(ValueError):
        number = int(spec)
        return repository.github.pull_request(number)

    head = spec if ":" in spec else f"{repository.owner}:{spec}"
    pull = repository.github.pull_request_by_head(head)
    if pull is not None:
        return pull

    raise RuntimeError(f"pull request {spec} not found")


def get_pull_requests(
    repository: Repository, specs: Iterable[str] = ()
) -> Iterator[github.PullRequest]:
    """Return pull requests. With specs, filter those matching specs."""
    if specs:
        for spec in specs:
            yield get_pull_request(repository, spec)
    else:
        yield from repository.github.pull_requests()


def list_pull_requests(
    repository: Repository, specs: Iterable[str], *, user: Optional[str] = None
) -> Iterator[github.PullRequest]:
    """List matching pull requests in repository."""
    for pull in get_pull_requests(repository, specs):
        if user is None or pull.user == user:
            yield pull


def import_branch(
    template: Repository,
    template_branch: str,
    instance: Repository,
    instance_branch: str,
    *,
    base: str = "master",
    force: bool = False,
) -> None:
    """Import pull request into the local repository."""
    if template.clone.exists_branch(template_branch) and not force:
        raise RuntimeError(f"{instance_branch} was already imported")

    with cache.worktree(
        template.owner, template.name, template_branch, base=base, force=force
    ) as worktree:
        retrocookie(
            instance.clone.path, branch=instance_branch, path=worktree.path,
        )


def get_push_url(repository: git.Repository) -> str:
    """Build push URL from remote URL and OAuth token."""
    remote = repository.repo.remotes["origin"]
    url = urlparse(remote.url)
    _, _, netloc = url.netloc.rpartition("@")
    token = cache.load_token()
    netloc = "@".join((token, netloc))
    url._replace(netloc=netloc)
    return urlunparse(url)


def push_branch(
    repository: git.Repository, branch: str, *, force: bool = False
) -> None:
    """Push branch to remote."""
    url = get_push_url(repository)
    options = ["--force-with-lease"] if force else []
    # https://stackoverflow.com/a/41153073/1355754
    repository.git("push", *options, url, "+" + branch)


def create_or_update_pull_request(
    template: github.Repository,
    head: str,
    pull: github.PullRequest,
    *,
    base: str = "master",
    force: bool = False,
) -> None:
    """Import pull request into the GitHub repository."""
    previous = template.pull_request_by_head(head)

    if previous is None:
        created = template.create_pull_request(
            head=head, title=pull.title, body=pull.body, base=base,
        )
        created.add_labels(pull.labels)
    elif force:
        previous.update(title=pull.title, body=pull.body, base=base)
        previous.replace_labels(pull.labels)
    else:
        raise RuntimeError(f"pull request for {pull.branch} already opened")


def import_pull_request(
    pull: github.PullRequest,
    instance: Repository,
    template: Repository,
    *,
    base: str = "master",
    force: bool = False,
) -> None:
    """Import the given pull request from the instance into its template."""
    branch = f"{appname}/{pull.branch}"

    import_branch(template, branch, instance, pull.branch, base=base, force=force)
    push_branch(template.clone, branch, force=force)
    create_or_update_pull_request(
        template.github,
        head=f"{template.owner}:{branch}",
        pull=pull,
        base=base,
        force=force,
    )


def find_repository_name(url: str) -> Optional[str]:
    """Extract the repository name from the URL, if possible."""
    for prefix in ("gh:", "git@github.com:"):
        if url.startswith(prefix):
            path = removeprefix(url, prefix)
            return removesuffix(path, ".git")

    result = urlparse(url)
    if result.hostname == "github.com":
        return removesuffix(result.path[1:], ".git")

    return None


def get_instance_name() -> str:
    """Return the repository name of the instance."""
    repository = git.Repository()

    for remote in repository.repo.remotes:
        name = find_repository_name(remote.url)
        if name is not None:
            return name

    raise RuntimeError("instance not on GitHub")


def get_template_name(instance: Repository) -> str:
    """Return the repository name of the template, given the instance."""
    context = load_context(instance.clone, "HEAD")
    name = find_repository_name(context["_template"])
    if name is not None:
        return name

    raise RuntimeError("template not on GitHub")


def import_pull_requests(
    pull_requests: Iterable[str] = (),
    *,
    repository: Optional[str],
    get_credentials: github.CredentialsCallback,
    base: str = "master",
    user: Optional[str] = None,
    force: bool = False,
) -> None:
    """Import pull requests from a repository into its Cookiecutter template."""
    gh = github.GitHub.login(get_credentials)

    instance = Repository.load(gh, repository or get_instance_name())
    template = Repository.load(gh, get_template_name(instance))

    for pull in list_pull_requests(instance, pull_requests, user=user):
        import_pull_request(pull, instance, template, base=base, force=force)
