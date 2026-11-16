import os
import shutil
import subprocess

import pytest

from robot_server.updater import self_update

pytestmark = pytest.mark.skipif(shutil.which("git") is None, reason="git não instalado")

GIT_ENV = {
    "GIT_AUTHOR_NAME": "test",
    "GIT_AUTHOR_EMAIL": "test@example.com",
    "GIT_COMMITTER_NAME": "test",
    "GIT_COMMITTER_EMAIL": "test@example.com",
}


def git(cwd, *args):
    env = {**os.environ, **GIT_ENV}
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, env=env)


def commit(repo, name):
    (repo / name).write_text(name)
    git(repo, "add", name)
    git(repo, "commit", "-m", name)
    git(repo, "push", "origin", "HEAD:master")


@pytest.fixture
def repos(tmp_path):
    origin = tmp_path / "origin.git"
    git(tmp_path, "init", "--bare", "-b", "master", str(origin))
    author = tmp_path / "author"
    git(tmp_path, "clone", str(origin), str(author))
    commit(author, "a.txt")
    robot = tmp_path / "robot"
    git(tmp_path, "clone", str(origin), str(robot))
    return author, robot


def test_not_a_git_repository(tmp_path):
    assert self_update(tmp_path, "master") is False


def test_no_changes(repos):
    _, robot = repos
    assert self_update(robot, "master") is False


def test_pulls_new_commits(repos):
    author, robot = repos
    commit(author, "b.txt")
    assert self_update(robot, "master") is True
    assert (robot / "b.txt").exists()
    assert self_update(robot, "master") is False


def test_failure_keeps_local_version(repos):
    _, robot = repos
    assert self_update(robot, "branch-que-nao-existe") is False
