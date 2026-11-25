import pytest

from check_docs import check, slug


def write(tmp_path, name, text):
    path = tmp_path / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    return path


def test_passes_on_valid_links_anchors_and_shell_blocks(tmp_path):
    write(tmp_path, "code/app.py", "pass\n")
    other = write(tmp_path, "docs/other.md", "# Title\n\n## Run it\n\n## Run it\n")
    page = write(tmp_path, "docs/page.md", "\n".join([
        "# Page",
        "[same page](#page) [other](other.md#run-it) [second](other.md#run-it-1)",
        "[code](../code/app.py) [folder](../code) [web](https://example.invalid/x#L1)",
        "```sh",
        "echo hello",
        "```",
        "```python",
        "# a comment in Python is fine",
        "```",
        "```text",
        "[not a link](missing.md)",
        "```",
    ]))
    problems, checked = check([page, other])
    assert problems == []
    assert checked == 5


@pytest.mark.parametrize(("line", "message"), [
    ("[gone](missing.md)", "link to a missing file: missing.md"),
    ("[gone](other.md#no-such-heading)", "link to a missing heading: other.md#no-such-heading"),
    ("[gone](#no-such-heading)", "link to a missing heading: #no-such-heading"),
    ("[stale](app.py#L12)", "link to a source line, which goes stale: app.py#L12"),
    ("[stale](app.py#L12-L20)", "link to a source line, which goes stale: app.py#L12-L20"),
])
def test_reports_each_kind_of_bad_link_with_its_line(tmp_path, line, message):
    write(tmp_path, "app.py", "pass\n")
    write(tmp_path, "other.md", "# Other\n")
    page = write(tmp_path, "page.md", f"# Page\n\n{line}\n")
    problems, _ = check([page])
    assert problems == [f"{page}:3: {message}"]


@pytest.mark.parametrize("fence", ["sh", "bash", "zsh", "shell", "SH"])
def test_reports_comment_lines_in_shell_blocks(tmp_path, fence):
    page = write(tmp_path, "page.md", f"# Page\n\n   ```{fence}\n   echo ok\n     # explain\n   ```\n")
    problems, _ = check([page])
    assert len(problems) == 1
    assert problems[0].startswith(f"{page}:5: comment line in a shell block")


def test_heading_anchor_follows_github(tmp_path):
    assert slug("DPoP (Demonstrating Proof of Possession)") == "dpop-demonstrating-proof-of-possession"
    assert slug("Client assertion (`private_key_jwt`)") == "client-assertion-private_key_jwt"
    assert slug("The real Claude Code CLI, offline") == "the-real-claude-code-cli-offline"
    assert slug("A [linked](x.md) heading") == "a-linked-heading"
