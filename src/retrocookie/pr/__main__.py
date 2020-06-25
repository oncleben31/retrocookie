"""Command-line interface."""
import getpass
from typing import Iterable
from typing import Optional
from typing import Tuple

import click

from .core import import_pull_requests


def ask_credentials() -> Tuple[str, str]:
    """Prompt the user for their GitHub credentials."""
    username = click.prompt("Username", default=getpass.getuser())
    password = click.prompt("Password", hide_input=True)
    return username, password


@click.command()
@click.argument("pull_requests", metavar="pull-request", nargs=-1)
@click.option(
    "-R", "--repository", help="GitHub repository containing the pull requests",
)
@click.option(
    "--base",
    default="master",
    help="Create pull request against this base",
    show_default=True,
)
@click.option("-u", "--user", help="Import pull requests opened by this GitHub user")
@click.option("--force", is_flag=True, help="Overwrite existing pull requests")
@click.version_option()
def main(
    pull_requests: Iterable[str],
    repository: Optional[str],
    base: str,
    user: Optional[str],
    force: bool,
) -> None:
    """Import pull requests from a repository into its Cookiecutter template."""
    import_pull_requests(
        pull_requests,
        repository=repository,
        get_credentials=ask_credentials,
        base=base,
        user=user,
        force=force,
    )


if __name__ == "__main__":
    main()
