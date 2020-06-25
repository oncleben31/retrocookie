"""GitHub interface."""
from __future__ import annotations

import contextlib
from typing import Callable
from typing import cast
from typing import Iterator
from typing import List
from typing import Optional
from typing import Tuple
from typing import Union

import github3

from . import appname
from . import cache


class PullRequest:
    """Pull request in a GitHub repository."""

    def __init__(
        self,
        pull_request: Union[github3.pulls.PullRequest, github3.pulls.ShortPullRequest],
    ) -> None:
        """Initialize."""
        self.pull_request = pull_request

    @property
    def title(self) -> str:
        """Title of the pull request description."""
        return cast(str, self.pull_request.title)

    @property
    def body(self) -> str:
        """Body of the pull request description."""
        return cast(str, self.pull_request.body)

    @property
    def branch(self) -> str:
        """Branch merged by the pull request."""
        return cast(str, self.pull_request.head.ref)

    @property
    def user(self) -> str:
        """Login of the user that opened the pull request."""
        return cast(str, self.pull_request.user.login)

    @property
    def labels(self) -> List[str]:
        """The labels associated with the pull request."""
        issue = self.pull_request.issue()
        return [label.name for label in issue.labels()]

    def update(self, title: str, body: str, base: str) -> None:
        """Update the pull request."""
        self.pull_request.update(title=title, body=body, base=base)

    def add_labels(self, labels: List[str]) -> None:
        """Add labels to the pull request."""
        self.pull_request.issue().add_labels(*labels)

    def replace_labels(self, labels: List[str]) -> None:
        """Add labels to the pull request."""
        self.pull_request.issue().replace_labels(labels)


class Repository:
    """GitHub Repository."""

    def __init__(self, repository: github3.repos.repo.Repository) -> None:
        """Initialize."""
        self.repository = repository

    def pull_request(self, number: int) -> PullRequest:
        """Return pull request identified by the given number."""
        pull_request = self.repository.pull_request(number)
        return PullRequest(pull_request)

    def pull_request_by_head(self, head: str) -> Optional[PullRequest]:
        """Return pull request for the given head."""
        for pull_request in self.repository.pull_requests(head=head):
            return PullRequest(pull_request)
        return None

    def pull_requests(self) -> Iterator[PullRequest]:
        """List pull requests."""
        for pull_request in self.repository.pull_requests(state="open"):
            yield PullRequest(pull_request)

    def create_pull_request(
        self, *, head: str, title: str, body: str, base: str = "master"
    ) -> PullRequest:
        """Create a pull request."""
        pull_request = self.repository.create_pull(
            title=title, base=base, head=head, body=body
        )
        return PullRequest(pull_request)


CredentialsCallback = Callable[[], Tuple[str, str]]


class GitHub:
    """GitHub API."""

    def __init__(self, github: github3.GitHub) -> None:
        """Initialize."""
        self.github = github

    @classmethod
    def login(cls, get_credentials: CredentialsCallback) -> GitHub:
        """Login to GitHub."""
        github = login(get_credentials)
        return cls(github)

    def repository(self, owner: str, repository: str) -> Repository:
        """Return the repository at owner/repository."""
        return Repository(self.github.repository(owner, repository))


def authorize(
    github: github3.GitHub, username: str, password: str
) -> github3.auths.Authorization:
    """Retrieve or create an OAuth token."""
    for authorization in github.authorizations():
        if authorization.app["name"] == appname:
            if authorization.token:
                return authorization
            authorization.delete()
    return github.authorize(username, password, note=appname, scopes=["user", "repo"])


def login_with_credentials(username: str, password: str) -> github3.GitHub:
    """Login to GitHub using credentials, saving an OAuth token."""
    github = github3.login(username, password)
    authorization = authorize(github, username, password)
    cache.save_token(authorization.token)
    return github


def login_with_token() -> github3.GitHub:
    """Login to GitHub using an existing OAuth token."""
    token = cache.load_token()
    return github3.login(token=token)


def login(get_credentials: CredentialsCallback) -> github3.GitHub:
    """Login to GitHub."""
    with contextlib.suppress(FileNotFoundError):
        return login_with_token()

    username, password = get_credentials()

    return login_with_credentials(username, password)
