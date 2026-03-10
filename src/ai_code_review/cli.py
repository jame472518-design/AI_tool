from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import click
from rich.console import Console
from rich.markup import escape as rich_escape

from .commit_check import check_commit_message
from .config import DEFAULT_COMMIT_TEMPLATE_FILE, DEFAULT_INCLUDE_EXTENSIONS, DEFAULT_MAX_DIFF_LINES, Config
from .exceptions import ProviderError, ProviderNotConfiguredError
from .formatters import format_json, format_markdown, format_terminal
from .git import GitError, get_push_diff, get_staged_diff
from .llm.base import LLMProvider
from .llm.enterprise import EnterpriseProvider
from .llm.ollama import OllamaProvider
from .llm.openai import OpenAIProvider
from .reviewer import Reviewer

console = Console()


def _build_provider(config: Config, cli_provider: str | None, cli_model: str | None) -> LLMProvider:
    provider_name = config.resolve_provider(cli_provider)
    if not provider_name:
        raise ProviderNotConfiguredError(
            "No provider configured. Available providers: ollama, openai, enterprise.\n"
            "Run: ai-review config set provider default <name>"
        )

    if provider_name == "ollama":
        base_url = config.get("ollama", "base_url") or "http://localhost:11434"
        model = cli_model or config.get("ollama", "model") or "codellama"
        timeout = float(config.get("ollama", "timeout") or 120)
        return OllamaProvider(base_url=base_url, model=model, timeout=timeout)

    elif provider_name == "openai":
        token = config.resolve_token("openai")
        if not token:
            env_var = config.get("openai", "api_key_env") or "OPENAI_API_KEY"
            raise ProviderNotConfiguredError(
                f"OpenAI API key not found. Set env var {env_var} "
                f"(or configure: ai-review config set openai api_key_env <VAR_NAME>)"
            )
        model = cli_model or config.get("openai", "model") or "gpt-4o"
        base_url = config.get("openai", "base_url")
        timeout = float(config.get("openai", "timeout") or 120)
        return OpenAIProvider(api_key=token, model=model, base_url=base_url, timeout=timeout)

    elif provider_name == "enterprise":
        token = config.resolve_token("enterprise") or ""
        base_url = config.get("enterprise", "base_url")
        if not base_url:
            raise ProviderNotConfiguredError(
                "Enterprise base_url not configured.\n"
                "Run: ai-review config set enterprise base_url <URL>"
            )
        api_path = config.get("enterprise", "api_path") or "/v1/chat/completions"
        model = cli_model or config.get("enterprise", "model") or "default"
        auth_type = config.get("enterprise", "auth_type") or "bearer"
        timeout = float(config.get("enterprise", "timeout") or 120)
        return EnterpriseProvider(
            base_url=base_url, api_path=api_path, model=model,
            auth_type=auth_type, auth_token=token, timeout=timeout,
        )

    raise ProviderNotConfiguredError(f"Unknown provider: {provider_name}")


@click.group(invoke_without_command=True)
@click.option("--provider", "cli_provider", default=None, help="LLM provider (ollama/openai/enterprise)")
@click.option("--model", "cli_model", default=None, help="Model name")
@click.option("--format", "output_format", default="terminal", type=click.Choice(["terminal", "markdown", "json"]))
@click.option("--verbose", "-v", is_flag=True, help="Enable debug logging.")
@click.option("--graceful", is_flag=True, help="Don't block on LLM failures (exit 0 instead of 1).")
@click.pass_context
def main(ctx: click.Context, cli_provider: str | None, cli_model: str | None, output_format: str, verbose: bool, graceful: bool) -> None:
    """AI-powered code review for Android BSP teams."""
    ctx.ensure_object(dict)
    ctx.obj["cli_provider"] = cli_provider
    ctx.obj["cli_model"] = cli_model
    ctx.obj["output_format"] = output_format
    ctx.obj["graceful"] = graceful

    if verbose:
        import logging
        logging.basicConfig(level=logging.DEBUG, format="[DEBUG] %(message)s")
        logging.getLogger("ai_code_review").setLevel(logging.DEBUG)

    if ctx.invoked_subcommand is None:
        _review(ctx)


def _review(ctx: click.Context) -> None:
    config = Config()
    cli_provider = ctx.obj["cli_provider"]
    cli_model = ctx.obj["cli_model"]
    output_format = ctx.obj["output_format"]
    graceful = ctx.obj.get("graceful", False)

    ext_raw = config.get("review", "include_extensions") or DEFAULT_INCLUDE_EXTENSIONS
    extensions = [e.strip() for e in ext_raw.split(",") if e.strip()] if ext_raw else None

    try:
        diff = get_staged_diff(extensions=extensions)
    except GitError as e:
        console.print(f"[bold red]{rich_escape(str(e))}[/]")
        sys.exit(1)

    if not diff:
        if extensions:
            console.print(f"[dim]No staged changes matching {rich_escape(', '.join(f'.{e}' for e in extensions))}.[/]")
        else:
            console.print("[dim]No staged changes to review.[/]")
        return

    # Truncate large diffs
    max_lines_raw = config.get("review", "max_diff_lines")
    max_lines = int(max_lines_raw) if max_lines_raw else DEFAULT_MAX_DIFF_LINES
    lines = diff.split("\n")
    if len(lines) > max_lines:
        console.print(f"[yellow]Warning: diff truncated to {max_lines} lines (original: {len(lines)} lines)[/]")
        diff = "\n".join(lines[:max_lines]) + f"\n... (truncated: showing first {max_lines} of {len(lines)} lines)"

    custom_rules = config.get("review", "custom_rules")

    try:
        provider = _build_provider(config, cli_provider, cli_model)
    except ProviderNotConfiguredError as e:
        console.print(f"[bold red]{rich_escape(str(e))}[/]")
        sys.exit(1)
    except ProviderError as e:
        if graceful:
            console.print(f"[yellow]Warning: LLM provider error: {rich_escape(str(e))}[/]")
            return
        console.print(f"[bold red]{rich_escape(str(e))}[/]")
        sys.exit(1)

    reviewer = Reviewer(provider=provider)
    try:
        result = reviewer.review_diff(diff, custom_rules=custom_rules)
    except ProviderError as e:
        if graceful:
            console.print(f"[yellow]Warning: LLM provider error: {rich_escape(str(e))}[/]")
            return
        console.print(f"[bold red]{rich_escape(str(e))}[/]")
        sys.exit(1)

    formatters = {"terminal": format_terminal, "markdown": format_markdown, "json": format_json}
    output = formatters[output_format](result)
    click.echo(output)

    if result.is_blocked:
        sys.exit(1)


@main.command("check-commit")
@click.argument("message_file", required=False)
@click.option("--auto-accept", is_flag=True, help="Auto-accept AI suggestion without prompt.")
@click.option("--format-only", is_flag=True, help="Only check format, skip AI improvement.")
@click.pass_context
def check_commit(ctx: click.Context, message_file: str | None, auto_accept: bool, format_only: bool) -> None:
    """Check commit message format and optionally improve with AI."""
    if message_file:
        msg_path = Path(message_file)
        message = msg_path.read_text(encoding="utf-8").strip()
    else:
        message = click.get_text_stream("stdin").readline().strip()
        msg_path = None

    # Step 1: Format check (pattern/hint from config, falls back to defaults)
    config = Config()
    pattern = config.get("commit", "message_pattern")
    format_hint = config.get("commit", "format_hint")
    result = check_commit_message(message, pattern=pattern, format_hint=format_hint)
    if not result.valid:
        console.print(f"[bold red]{rich_escape(result.error)}[/]")
        sys.exit(1)
    console.print("[green]Commit message format OK.[/]")

    # Step 2: AI improvement (only when we have a file to update and a provider)
    if format_only or msg_path is None:
        return

    try:
        config = Config()
        cli_provider = ctx.obj.get("cli_provider") if ctx.obj else None
        cli_model = ctx.obj.get("cli_model") if ctx.obj else None
        provider = _build_provider(config, cli_provider, cli_model)
    except ProviderNotConfiguredError:
        # No provider configured — skip AI improvement silently
        return

    try:
        diff = get_staged_diff()
    except GitError:
        diff = ""

    if not diff:
        return

    graceful = ctx.obj.get("graceful", False) if ctx.obj else False

    reviewer = Reviewer(provider=provider)
    try:
        improved = reviewer.improve_commit_message(message, diff)
    except ProviderError as e:
        if graceful:
            console.print(f"[yellow]Warning: LLM provider error: {rich_escape(str(e))}[/]")
        else:
            console.print(f"[bold red]{rich_escape(str(e))}[/]")
        return

    if improved and improved.strip() != message:
        console.print(f"\n[dim]Original:[/]  {rich_escape(message)}")
        console.print(f"[bold]Suggested:[/] {rich_escape(improved)}")
        if auto_accept or os.environ.get("AI_REVIEW_AUTO_ACCEPT") == "1":
            choice = "a"
            console.print("[dim](non-interactive: auto-accept)[/]")
        else:
            choice = click.prompt(
                "[A]ccept / [E]dit / [S]kip",
                type=click.Choice(["a", "e", "s"], case_sensitive=False),
                default="a",
            )
        if choice == "a":
            msg_path.write_text(improved + "\n", encoding="utf-8")
            console.print("[green]Commit message updated.[/]")
        elif choice == "e":
            edited = click.edit(improved)
            if edited:
                msg_path.write_text(edited, encoding="utf-8")
                console.print("[green]Commit message updated.[/]")
        # "s" → do nothing, keep original


@main.command("generate-commit-msg")
@click.argument("message_file")
@click.argument("source", required=False, default="")
@click.argument("sha", required=False, default="")
@click.pass_context
def generate_commit_msg_cmd(ctx: click.Context, message_file: str, source: str, sha: str) -> None:
    """Generate commit message from staged diff (used by prepare-commit-msg hook)."""
    # Skip for merge, squash, amend, and user-provided messages
    if source in ("merge", "squash", "commit", "message"):
        return

    graceful = ctx.obj.get("graceful", False) if ctx.obj else False

    config = Config()
    project_id = config.get("commit", "project_id")

    ext_raw = config.get("review", "include_extensions") or DEFAULT_INCLUDE_EXTENSIONS
    extensions = [e.strip() for e in ext_raw.split(",") if e.strip()] if ext_raw else None

    try:
        diff = get_staged_diff(extensions=extensions)
    except GitError:
        return
    if not diff:
        return

    try:
        cli_provider = ctx.obj.get("cli_provider") if ctx.obj else None
        cli_model = ctx.obj.get("cli_model") if ctx.obj else None
        provider = _build_provider(config, cli_provider, cli_model)
    except (ProviderNotConfiguredError, ProviderError) as e:
        if graceful:
            console.print(f"[yellow]Warning: Cannot generate commit message — {rich_escape(str(e))}[/]")
        return

    reviewer = Reviewer(provider=provider)
    try:
        description = reviewer.generate_commit_message(diff)
    except ProviderError as e:
        if graceful:
            console.print(f"[yellow]Warning: Commit message generation failed — {rich_escape(str(e))}[/]")
        return

    if not description:
        return

    if project_id:
        message = f"[{project_id}] {description}"
    else:
        message = description

    msg_path = Path(message_file)
    msg_path.write_text(message + "\n", encoding="utf-8")
    console.print(f"[green]Generated: {rich_escape(message)}[/]")


def _load_template(config: Config) -> str:
    """Load commit message template from config path, config dir, or package."""
    import importlib.resources

    # 1. Config-specified path
    custom_path = config.get("commit", "template_file")
    if custom_path:
        p = Path(custom_path).expanduser()
        if p.exists():
            return p.read_text(encoding="utf-8")

    # 2. Default config dir
    default_path = Path.home() / ".config" / "ai-code-review" / DEFAULT_COMMIT_TEMPLATE_FILE
    if default_path.exists():
        return default_path.read_text(encoding="utf-8")

    # 3. Bundled in package
    try:
        templates = importlib.resources.files("ai_code_review") / "templates"
        src = templates / "commit-template.txt"
        return src.read_text(encoding="utf-8")
    except (FileNotFoundError, TypeError):
        pass

    return "[tag] description\n"


@main.command("prepare-interactive")
@click.argument("message_file")
@click.argument("source", required=False, default="")
@click.argument("sha", required=False, default="")
@click.pass_context
def prepare_interactive(ctx: click.Context, message_file: str, source: str, sha: str) -> None:
    """Interactive commit message preparation (used by prepare-commit-msg hook)."""
    # Skip for merge, squash, amend, and user-provided messages
    if source in ("merge", "squash", "commit", "message"):
        return

    graceful = ctx.obj.get("graceful", False) if ctx.obj else False
    config = Config()
    msg_path = Path(message_file)

    # Show interactive menu
    console.print("\n[bold]Commit Message Assistant[/]")
    console.print("  [bold cyan]1[/] Load template       - 載入模板")
    console.print("  [bold cyan]2[/] LLM optimize        - AI 優化已有文字")
    console.print("  [bold cyan]3[/] LLM auto-generate   - AI 自動生成")
    console.print("  [bold cyan]s[/] Skip                - 跳過，直接進編輯器")

    try:
        choice = click.prompt(
            "Choice",
            type=click.Choice(["1", "2", "3", "s"], case_sensitive=False),
            default="s",
        )
    except (EOFError, click.Abort):
        return

    if choice == "1":
        # Feature 1: Load template
        template_content = _load_template(config)
        msg_path.write_text(template_content, encoding="utf-8")
        console.print("[green]Template loaded.[/]")

    elif choice in ("2", "3"):
        # Shared setup for LLM features
        cli_provider = ctx.obj.get("cli_provider") if ctx.obj else None
        cli_model = ctx.obj.get("cli_model") if ctx.obj else None

        try:
            provider = _build_provider(config, cli_provider, cli_model)
        except (ProviderNotConfiguredError, ProviderError) as e:
            if graceful:
                console.print(f"[yellow]Warning: {rich_escape(str(e))}[/]")
            else:
                console.print(f"[bold red]{rich_escape(str(e))}[/]")
            return

        # Show model info
        provider_name = config.resolve_provider(cli_provider) or "unknown"
        model_name = cli_model or config.get(provider_name, "model") or "default"
        console.print(f"[dim]Provider: {rich_escape(provider_name)} | Model: {rich_escape(model_name)}[/]")

        ext_raw = config.get("review", "include_extensions")
        if ext_raw is None:
            ext_raw = DEFAULT_INCLUDE_EXTENSIONS
        extensions = [e.strip() for e in ext_raw.split(",") if e.strip()] if ext_raw else None

        try:
            diff = get_staged_diff(extensions=extensions)
        except GitError:
            diff = ""

        reviewer = Reviewer(provider=provider)
        project_id = config.get("commit", "project_id")

        # Load template content (strip comment lines) for LLM prompt
        template_content = _load_template(config)
        template_for_llm = "\n".join(
            line for line in template_content.splitlines() if not line.startswith("#")
        ).strip() or None

        if choice == "2":
            # Feature 2: LLM optimize — prompt per template field
            current = msg_path.read_text(encoding="utf-8").strip()
            current = "\n".join(
                line for line in current.splitlines() if not line.startswith("#")
            ).strip()
            if not current:
                # Parse template into fields and prompt each one
                template_lines = [
                    line for line in template_content.splitlines()
                    if line.strip() and not line.startswith("#")
                ]
                if template_lines:
                    console.print("[dim]Fill in each field (leave empty to skip):[/]")
                    filled_lines = []
                    try:
                        for tline in template_lines:
                            user_input = input(f"  {tline}: ")
                            filled_lines.append(user_input.strip() if user_input.strip() else "")
                    except (EOFError, KeyboardInterrupt):
                        console.print("[yellow]Cancelled.[/]")
                        return
                    current = "\n".join(filled_lines).strip()
                else:
                    # No template — fallback to free-form input
                    console.print("[dim]Enter your draft message (press Enter twice to finish):[/]")
                    lines = []
                    try:
                        while True:
                            line = input()
                            if line == "" and lines and lines[-1] == "":
                                break
                            lines.append(line)
                    except EOFError:
                        pass
                    current = "\n".join(lines).strip()
                if not current:
                    console.print("[yellow]Empty draft, skipping.[/]")
                    return

            with console.status(f"[bold cyan]AI optimizing... ({model_name})[/]"):
                try:
                    improved = reviewer.improve_commit_message(current, diff, template=template_for_llm)
                except ProviderError as e:
                    if graceful:
                        console.print(f"[yellow]Warning: LLM optimize failed — {rich_escape(str(e))}[/]")
                    else:
                        console.print(f"[bold red]{rich_escape(str(e))}[/]")
                    return

            if improved and improved.strip():
                if project_id and not improved.startswith("["):
                    improved = f"[{project_id}] {improved}"
                msg_path.write_text(improved + "\n", encoding="utf-8")
                console.print(f"[dim]Original:[/]  {rich_escape(current)}")
                console.print(f"[green]Optimized:[/] {rich_escape(improved)}")

        else:
            # Feature 3: LLM auto-generate from diff
            if not diff:
                console.print("[yellow]No staged changes found.[/]")
                return

            with console.status(f"[bold cyan]AI generating... ({model_name})[/]"):
                try:
                    description = reviewer.generate_commit_message(diff, template=template_for_llm)
                except ProviderError as e:
                    if graceful:
                        console.print(f"[yellow]Warning: LLM generate failed — {rich_escape(str(e))}[/]")
                    else:
                        console.print(f"[bold red]{rich_escape(str(e))}[/]")
                    return

            if not description:
                return

            if project_id:
                message = f"[{project_id}] {description}"
            else:
                message = description

            msg_path.write_text(message + "\n", encoding="utf-8")
            console.print(f"[green]Generated: {rich_escape(message)}[/]")

    # choice == "s": do nothing, editor opens with default content


@main.command("pre-push")
@click.pass_context
def pre_push_cmd(ctx: click.Context) -> None:
    """Review commits before push (used by pre-push hook)."""
    graceful = ctx.obj.get("graceful", False) if ctx.obj else False

    # Read ref data from stdin
    stdin_data = click.get_text_stream("stdin").read().strip()
    if not stdin_data:
        return

    config = Config()
    cli_provider = ctx.obj.get("cli_provider") if ctx.obj else None
    cli_model = ctx.obj.get("cli_model") if ctx.obj else None

    ext_raw = config.get("review", "include_extensions") or DEFAULT_INCLUDE_EXTENSIONS
    extensions = [e.strip() for e in ext_raw.split(",") if e.strip()] if ext_raw else None

    # Collect diffs from all refs being pushed
    all_diff_parts = []
    for line in stdin_data.split("\n"):
        line = line.strip()
        if not line:
            continue
        parts = line.split()
        if len(parts) < 4:
            continue
        local_ref, local_sha, remote_ref, remote_sha = parts[:4]
        try:
            diff = get_push_diff(local_sha, remote_sha, extensions=extensions)
            if diff:
                all_diff_parts.append(diff)
        except GitError:
            continue

    all_diff = "\n".join(all_diff_parts)
    if not all_diff:
        console.print("[dim]No changes to review in push.[/]")
        return

    # Truncate large diffs
    max_lines_raw = config.get("review", "max_diff_lines")
    max_lines = int(max_lines_raw) if max_lines_raw else DEFAULT_MAX_DIFF_LINES
    lines = all_diff.split("\n")
    if len(lines) > max_lines:
        console.print(f"[yellow]Warning: diff truncated to {max_lines} lines (original: {len(lines)} lines)[/]")
        all_diff = "\n".join(lines[:max_lines]) + f"\n... (truncated: showing first {max_lines} of {len(lines)} lines)"

    custom_rules = config.get("review", "custom_rules")

    try:
        provider = _build_provider(config, cli_provider, cli_model)
    except (ProviderNotConfiguredError, ProviderError) as e:
        if graceful:
            console.print(f"[yellow]Warning: AI review unavailable — {rich_escape(str(e))}[/]")
            return
        console.print(f"[bold red]{rich_escape(str(e))}[/]")
        sys.exit(1)

    reviewer = Reviewer(provider=provider)
    try:
        result = reviewer.review_diff(all_diff, custom_rules=custom_rules)
    except ProviderError as e:
        if graceful:
            console.print(f"[yellow]Warning: AI review failed — {rich_escape(str(e))}[/]")
            return
        console.print(f"[bold red]{rich_escape(str(e))}[/]")
        sys.exit(1)

    output_format = ctx.obj.get("output_format", "terminal") if ctx.obj else "terminal"
    formatters = {"terminal": format_terminal, "markdown": format_markdown, "json": format_json}
    output = formatters[output_format](result)
    click.echo(output)

    if result.is_blocked:
        sys.exit(1)


@main.command("health-check")
@click.pass_context
def health_check_cmd(ctx: click.Context) -> None:
    """Check LLM provider connectivity."""
    config = Config()
    cli_provider = ctx.obj.get("cli_provider") if ctx.obj else None
    cli_model = ctx.obj.get("cli_model") if ctx.obj else None

    try:
        provider = _build_provider(config, cli_provider, cli_model)
    except ProviderNotConfiguredError as e:
        console.print(f"[bold red]{rich_escape(str(e))}[/]")
        sys.exit(1)

    provider_name = config.resolve_provider(cli_provider)
    model = cli_model or config.get(provider_name, "model") or "default"
    console.print(f"Provider: {rich_escape(provider_name)} ({rich_escape(model)})")

    ok, msg = provider.health_check()
    if ok:
        console.print(f"[green]Status: OK ({rich_escape(msg)})[/]")
    else:
        console.print(f"[bold red]Status: FAILED — {rich_escape(msg)}[/]")
        sys.exit(1)


@main.group("config")
def config_group() -> None:
    """Manage configuration."""
    pass


@config_group.command("set")
@click.argument("section")
@click.argument("key")
@click.argument("value")
def config_set(section: str, key: str, value: str) -> None:
    """Set a config value: ai-review config set <section> <key> <value>"""
    config = Config()
    config.set(section, key, value)
    console.print(f"[green]Set {rich_escape(section)}.{rich_escape(key)} = {rich_escape(value)}[/]")


@config_group.command("get")
@click.argument("section")
@click.argument("key")
def config_get(section: str, key: str) -> None:
    """Get a config value: ai-review config get <section> <key>"""
    config = Config()
    value = config.get(section, key)
    if value is None:
        console.print(f"[dim]{section}.{key} is not set[/]")
    else:
        console.print(value)


@config_group.command("show")
@click.argument("section", required=False)
def config_show(section: str | None) -> None:
    """Show current configuration."""
    config = Config()
    data = config._data

    if not data:
        console.print("[dim]No configuration set.[/]")
        return

    if section:
        if section not in data:
            console.print(f"[dim]Section '{rich_escape(section)}' not found.[/]")
            return
        _print_config_section(section, data[section])
    else:
        for sect_name, sect_data in data.items():
            _print_config_section(sect_name, sect_data)
            console.print()


@config_group.command("init-template")
@click.option("--force", is_flag=True, help="Overwrite existing template file.")
def config_init_template(force: bool) -> None:
    """Copy bundled commit template to config dir and set config."""
    import importlib.resources

    # Detect source tree: __file__ is under <project>/src/ai_code_review/cli.py
    # so <project> = parent.parent.parent, check for pyproject.toml to confirm
    _pkg_dir = Path(__file__).resolve().parent
    _project_root = _pkg_dir.parent.parent
    _is_source_tree = (_project_root / "pyproject.toml").exists()
    _src_file = _pkg_dir / "templates" / "commit-template.txt"

    if _is_source_tree and _src_file.exists():
        src = _src_file
    else:
        templates = importlib.resources.files("ai_code_review") / "templates"
        src = templates / "commit-template.txt"
        _is_source_tree = False
    content = src.read_text(encoding="utf-8")

    # Write to config dir
    dest_dir = Path.home() / ".config" / "ai-code-review"
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / DEFAULT_COMMIT_TEMPLATE_FILE

    if dest.exists() and not force:
        console.print(f"[yellow]Template already exists: {dest}[/]")
        console.print("[yellow]Use --force to overwrite.[/]")
        return

    dest.write_text(content, encoding="utf-8")
    console.print(f"[green]Template copied to: {dest}[/]")

    # Set config
    config = Config()
    config.set("commit", "template_file", str(dest))
    console.print(f"[green]Config set: commit.template_file = {dest}[/]")

    # Guide user to edit the source template (source tree) or the config copy
    if _is_source_tree:
        console.print(f"[dim]Edit source template: {_src_file}[/]")
        console.print("[dim]After editing, run: ai-review config init-template --force[/]")
    else:
        console.print(f"[dim]Edit template: {dest}[/]")


def _print_config_section(name: str, data: dict) -> None:
    console.print(f"[bold]{rich_escape('[' + name + ']')}[/]")
    for key, value in data.items():
        console.print(f"  {rich_escape(key)} = {rich_escape(str(value))}")


# --- Hook management ---

_GLOBAL_HOOKS_DIR = Path.home() / ".config" / "ai-code-review" / "hooks"
_TEMPLATE_HOOKS_DIR = Path.home() / ".config" / "ai-code-review" / "template" / "hooks"


def _resolve_ai_review_path() -> str:
    """Find the absolute path to the ai-review executable."""
    import shutil

    # 1. Check if ai-review is in PATH
    found = shutil.which("ai-review")
    if found:
        return found

    # 2. Check relative to this Python interpreter (venv/bin/)
    bin_dir = Path(sys.executable).parent
    candidate = bin_dir / "ai-review"
    if candidate.exists():
        return str(candidate)

    return "ai-review"


_HOOK_TYPES = ["pre-commit", "prepare-commit-msg", "commit-msg", "pre-push"]


def _generate_hook_scripts() -> dict[str, str]:
    """Generate hook scripts with the resolved ai-review path."""
    ai_review = _resolve_ai_review_path()
    opt_in_check = """\
# opt-in: only run in repos that have a .ai-review marker file
REPO_ROOT=$(git rev-parse --show-toplevel 2>/dev/null)
if [ ! -f "$REPO_ROOT/.ai-review" ]; then
    exit 0
fi"""
    return {
        "pre-commit": f"""#!/usr/bin/env bash
# Installed by ai-code-review
{opt_in_check}
{ai_review} --graceful
""",
        "prepare-commit-msg": f"""#!/usr/bin/env bash
# Installed by ai-code-review
{opt_in_check}
{ai_review} --graceful prepare-interactive "$1" "$2" "$3" < /dev/tty
""",
        "commit-msg": f"""#!/usr/bin/env bash
# Installed by ai-code-review
{opt_in_check}
{ai_review} --graceful check-commit --format-only "$1"
""",
        "pre-push": f"""#!/usr/bin/env bash
# Installed by ai-code-review
{opt_in_check}
{ai_review} --graceful pre-push
""",
    }


def _generate_template_hook_scripts() -> dict[str, str]:
    """Generate hook scripts that use git config --local for opt-in."""
    ai_review = _resolve_ai_review_path()
    opt_in_check = """\
# opt-in: check git local config
enabled=$(git config --local ai-review.enabled 2>/dev/null)
if [ "$enabled" != "true" ]; then
    exit 0
fi"""
    return {
        "pre-commit": f"""#!/usr/bin/env bash
# Installed by ai-code-review
{opt_in_check}
{ai_review} --graceful
""",
        "prepare-commit-msg": f"""#!/usr/bin/env bash
# Installed by ai-code-review
{opt_in_check}
{ai_review} --graceful prepare-interactive "$1" "$2" "$3" < /dev/tty
""",
        "commit-msg": f"""#!/usr/bin/env bash
# Installed by ai-code-review
{opt_in_check}
{ai_review} --graceful check-commit --format-only "$1"
""",
        "pre-push": f"""#!/usr/bin/env bash
# Installed by ai-code-review
{opt_in_check}
{ai_review} --graceful pre-push
""",
    }


@main.group("hook")
def hook_group() -> None:
    """Manage git hooks (global or per-repo)."""
    pass


@hook_group.command("install")
@click.option("--global", "global_install", is_flag=True, help="Install globally via core.hooksPath (all repos).")
@click.option("--template", "template_install", is_flag=True, help="Install via init.templateDir (recommended for Android).")
@click.argument("hook_type", required=False, type=click.Choice(_HOOK_TYPES))
def hook_install(global_install: bool, template_install: bool, hook_type: str | None) -> None:
    """Install git hooks. Use --template for Android multi-repo teams."""
    if global_install and template_install:
        console.print("[bold red]Cannot use --global and --template together.[/]")
        sys.exit(1)
    if template_install:
        _install_template_hooks()
    elif global_install:
        _install_global_hooks()
    elif hook_type:
        _install_repo_hook(hook_type)
    else:
        console.print("[bold red]Specify a hook type, --global, or --template.[/]")
        sys.exit(1)


@hook_group.command("uninstall")
@click.option("--global", "global_uninstall", is_flag=True, help="Remove global hooks and core.hooksPath.")
@click.option("--template", "template_uninstall", is_flag=True, help="Remove template hooks and init.templateDir.")
@click.argument("hook_type", required=False, type=click.Choice(_HOOK_TYPES))
def hook_uninstall(global_uninstall: bool, template_uninstall: bool, hook_type: str | None) -> None:
    """Uninstall git hooks."""
    if global_uninstall and template_uninstall:
        console.print("[bold red]Cannot use --global and --template together.[/]")
        sys.exit(1)
    if template_uninstall:
        _uninstall_template_hooks()
    elif global_uninstall:
        _uninstall_global_hooks()
    elif hook_type:
        _uninstall_repo_hook(hook_type)
    else:
        console.print("[bold red]Specify a hook type, --global, or --template.[/]")
        sys.exit(1)


@hook_group.command("status")
def hook_status() -> None:
    """Show installed hooks (template, global, and current repo)."""
    import subprocess

    # Template hooks status
    console.print("[bold]Template hooks:[/]")
    try:
        result = subprocess.run(
            ["git", "config", "--global", "init.templateDir"],
            capture_output=True, text=True,
        )
        template_path = result.stdout.strip()
        if template_path:
            console.print(f"  init.templateDir = {template_path}")
            hooks_dir = Path(template_path) / "hooks"
            for hook_type in _HOOK_TYPES:
                hook_path = hooks_dir / hook_type
                if hook_path.exists() and "ai-review" in hook_path.read_text(encoding="utf-8"):
                    console.print(f"  [green]{hook_type}: installed[/]")
                else:
                    console.print(f"  [dim]{hook_type}: not installed[/]")
        else:
            console.print("  [dim]not configured[/]")
    except (subprocess.CalledProcessError, OSError):
        console.print("  [dim]not configured[/]")

    # Global hooks status
    console.print("\n[bold]Global hooks:[/]")
    try:
        result = subprocess.run(
            ["git", "config", "--global", "core.hooksPath"],
            capture_output=True, text=True,
        )
        hooks_path = result.stdout.strip()
        if hooks_path:
            console.print(f"  core.hooksPath = {hooks_path}")
            hooks_dir = Path(hooks_path)
            for hook_type in _HOOK_TYPES:
                hook_path = hooks_dir / hook_type
                if hook_path.exists() and "ai-review" in hook_path.read_text(encoding="utf-8"):
                    console.print(f"  [green]{hook_type}: installed[/]")
                else:
                    console.print(f"  [dim]{hook_type}: not installed[/]")
        else:
            console.print("  [dim]not configured[/]")
    except (subprocess.CalledProcessError, OSError):
        console.print("  [dim]not configured[/]")

    # Current repo status
    console.print("\n[bold]Current repo:[/]")
    try:
        # Check ai-review.enabled
        result = subprocess.run(
            ["git", "config", "--local", "ai-review.enabled"],
            capture_output=True, text=True,
        )
        enabled = result.stdout.strip()
        if enabled:
            console.print(f"  ai-review.enabled = {enabled}")
        else:
            console.print("  [dim]ai-review.enabled: not set[/]")

        # Check repo hooks
        hooks_dir = _get_repo_hooks_dir()
        for hook_type in _HOOK_TYPES:
            hook_path = hooks_dir / hook_type
            if hook_path.exists() and "ai-review" in hook_path.read_text(encoding="utf-8"):
                console.print(f"  [green]{hook_type}: installed[/]")
            else:
                console.print(f"  [dim]{hook_type}: not installed[/]")
    except SystemExit:
        console.print("  [dim]not in a git repository[/]")


def _enable_single_repo(repo_path: Path, quiet: bool = False) -> bool:
    """Enable AI review for a single repo. Returns True if successful."""
    import subprocess

    git_dir = repo_path / ".git"
    if not git_dir.is_dir():
        if not quiet:
            console.print(f"[bold red]Not a git repository: {repo_path}[/]")
        return False

    # 1. Set git config flag
    subprocess.run(
        ["git", "-C", str(repo_path), "config", "--local", "ai-review.enabled", "true"],
        check=True,
    )

    # 2. Copy hook scripts into .git/hooks/
    hooks_dir = git_dir / "hooks"
    hooks_dir.mkdir(exist_ok=True)
    hook_scripts = _generate_template_hook_scripts()
    installed = []
    for hook_type, script in hook_scripts.items():
        hook_path = hooks_dir / hook_type
        if hook_path.exists():
            try:
                if "ai-review" in hook_path.read_text(encoding="utf-8"):
                    continue
            except (OSError, UnicodeDecodeError):
                pass
            if not quiet:
                console.print(f"  [yellow]Skipped {hook_type}: existing hook found[/]")
            continue
        hook_path.write_text(script, encoding="utf-8")
        hook_path.chmod(0o755)
        installed.append(hook_type)

    if not quiet:
        console.print(f"[green]Enabled: {repo_path}[/]")
        if installed:
            console.print(f"  [green]Installed hooks: {', '.join(installed)}[/]")
    return True


def _disable_single_repo(repo_path: Path, quiet: bool = False) -> bool:
    """Disable AI review for a single repo. Returns True if successful."""
    import subprocess

    git_dir = repo_path / ".git"
    if not git_dir.is_dir():
        if not quiet:
            console.print(f"[bold red]Not a git repository: {repo_path}[/]")
        return False

    try:
        subprocess.run(
            ["git", "-C", str(repo_path), "config", "--local", "--unset", "ai-review.enabled"],
            check=True, capture_output=True,
        )
        if not quiet:
            console.print(f"[green]Disabled: {repo_path}[/]")
        return True
    except subprocess.CalledProcessError:
        if not quiet:
            console.print(f"[dim]Not enabled: {repo_path}[/]")
        return False


def _find_git_repos(root: Path) -> list[Path]:
    """Find all git repos under root (non-recursive into nested .git)."""
    repos = []
    for item in sorted(root.iterdir()):
        if not item.is_dir() or item.name.startswith("."):
            continue
        if (item / ".git").is_dir():
            repos.append(item)
        else:
            # Search one more level for nested project structures
            for sub in sorted(item.iterdir()):
                if sub.is_dir() and (sub / ".git").is_dir():
                    repos.append(sub)
    return repos


@hook_group.command("enable")
@click.option("--path", "paths", multiple=True, type=click.Path(exists=True), help="Repo path(s) to enable (repeatable).")
@click.option("--all", "scan_dir", type=click.Path(exists=True), help="Scan directory and enable all git repos found.")
@click.option("--list", "list_only", is_flag=True, help="With --all: only list repos, don't enable.")
def hook_enable(paths: tuple[str, ...], scan_dir: str | None, list_only: bool) -> None:
    """Enable AI review for repo(s). Sets config + installs hooks.

    \b
    Examples:
      ai-review hook enable                          # current repo
      ai-review hook enable --path /path/to/repo     # specific repo
      ai-review hook enable --path repo1 --path repo2
      ai-review hook enable --all /workspace         # all repos under dir
      ai-review hook enable --all /workspace --list  # preview repos
    """
    if scan_dir:
        root = Path(scan_dir).resolve()
        repos = _find_git_repos(root)
        if not repos:
            console.print(f"[yellow]No git repos found under: {root}[/]")
            return
        console.print(f"[bold]Found {len(repos)} repo(s) under {root}:[/]")
        if list_only:
            for r in repos:
                # Check current status
                enabled = _is_repo_enabled(r)
                status = "[green]enabled[/]" if enabled else "[dim]disabled[/]"
                console.print(f"  {r.name}: {status}")
            return
        count = 0
        for r in repos:
            if _enable_single_repo(r, quiet=True):
                count += 1
                console.print(f"  [green]Enabled: {r.name}[/]")
        console.print(f"\n[bold green]{count}/{len(repos)} repos enabled.[/]")
        return

    if paths:
        for p in paths:
            _enable_single_repo(Path(p).resolve())
        return

    # Default: current directory
    _enable_single_repo(Path.cwd())


@hook_group.command("disable")
@click.option("--path", "paths", multiple=True, type=click.Path(exists=True), help="Repo path(s) to disable (repeatable).")
@click.option("--all", "scan_dir", type=click.Path(exists=True), help="Scan directory and disable all git repos found.")
def hook_disable(paths: tuple[str, ...], scan_dir: str | None) -> None:
    """Disable AI review for repo(s).

    \b
    Examples:
      ai-review hook disable                         # current repo
      ai-review hook disable --path /path/to/repo    # specific repo
      ai-review hook disable --all /workspace        # all repos under dir
    """
    if scan_dir:
        root = Path(scan_dir).resolve()
        repos = _find_git_repos(root)
        if not repos:
            console.print(f"[yellow]No git repos found under: {root}[/]")
            return
        count = 0
        for r in repos:
            if _disable_single_repo(r, quiet=True):
                count += 1
                console.print(f"  [dim]Disabled: {r.name}[/]")
        console.print(f"\n[bold]{count}/{len(repos)} repos disabled.[/]")
        return

    if paths:
        for p in paths:
            _disable_single_repo(Path(p).resolve())
        return

    _disable_single_repo(Path.cwd())


def _is_repo_enabled(repo_path: Path) -> bool:
    """Check if ai-review is enabled for a repo."""
    import subprocess
    try:
        result = subprocess.run(
            ["git", "-C", str(repo_path), "config", "--local", "ai-review.enabled"],
            capture_output=True, text=True,
        )
        return result.stdout.strip() == "true"
    except (subprocess.CalledProcessError, OSError):
        return False


def _install_global_hooks() -> None:
    import subprocess

    hook_scripts = _generate_hook_scripts()
    _GLOBAL_HOOKS_DIR.mkdir(parents=True, exist_ok=True)
    for hook_type, script in hook_scripts.items():
        hook_path = _GLOBAL_HOOKS_DIR / hook_type
        hook_path.write_text(script, encoding="utf-8")
        hook_path.chmod(0o755)
        console.print(f"  [green]Created {hook_path}[/]")

    subprocess.run(
        ["git", "config", "--global", "core.hooksPath", str(_GLOBAL_HOOKS_DIR)],
        check=True,
    )
    console.print(f"\n[green]Global hooks installed.[/]")
    console.print(f"[dim]core.hooksPath → {_GLOBAL_HOOKS_DIR}[/]")
    console.print("[dim]Hooks only activate in repos with a .ai-review marker file.[/]")
    console.print("[dim]Enable a repo: touch /path/to/repo/.ai-review[/]")


def _uninstall_global_hooks() -> None:
    import subprocess

    for hook_type in _HOOK_TYPES:
        hook_path = _GLOBAL_HOOKS_DIR / hook_type
        if hook_path.exists():
            hook_path.unlink()
            console.print(f"  [green]Removed {hook_path}[/]")

    try:
        subprocess.run(
            ["git", "config", "--global", "--unset", "core.hooksPath"],
            check=True, capture_output=True,
        )
        console.print("[green]Global hooks uninstalled (core.hooksPath cleared).[/]")
    except subprocess.CalledProcessError:
        console.print("[dim]core.hooksPath was not set.[/]")


def _install_template_hooks() -> None:
    import subprocess

    # Check for conflicting core.hooksPath
    check = subprocess.run(
        ["git", "config", "--global", "core.hooksPath"],
        capture_output=True, text=True,
    )
    if check.stdout.strip():
        console.print(f"[bold yellow]Warning: core.hooksPath is set to {check.stdout.strip()}[/]")
        console.print("[yellow]core.hooksPath overrides .git/hooks/ — template hooks won't run.[/]")
        console.print("[yellow]Run 'ai-review hook uninstall --global' first.[/]")

    hook_scripts = _generate_template_hook_scripts()
    _TEMPLATE_HOOKS_DIR.mkdir(parents=True, exist_ok=True)
    for hook_type, script in hook_scripts.items():
        hook_path = _TEMPLATE_HOOKS_DIR / hook_type
        hook_path.write_text(script, encoding="utf-8")
        hook_path.chmod(0o755)
        console.print(f"  [green]Created {hook_path}[/]")

    template_dir = _TEMPLATE_HOOKS_DIR.parent
    subprocess.run(
        ["git", "config", "--global", "init.templateDir", str(template_dir)],
        check=True,
    )
    console.print(f"\n[green]Template hooks installed.[/]")
    console.print(f"[dim]init.templateDir → {template_dir}[/]")
    console.print("[dim]New clones will auto-copy hooks to .git/hooks/[/]")
    console.print("[dim]Existing repos: run 'git init' to copy hooks[/]")
    console.print("[dim]Enable a repo: git config --local ai-review.enabled true[/]")


def _uninstall_template_hooks() -> None:
    import subprocess

    for hook_type in _HOOK_TYPES:
        hook_path = _TEMPLATE_HOOKS_DIR / hook_type
        if hook_path.exists():
            hook_path.unlink()
            console.print(f"  [green]Removed {hook_path}[/]")

    try:
        subprocess.run(
            ["git", "config", "--global", "--unset", "init.templateDir"],
            check=True, capture_output=True,
        )
        console.print("[green]Template hooks uninstalled (init.templateDir cleared).[/]")
    except subprocess.CalledProcessError:
        console.print("[dim]init.templateDir was not set.[/]")


def _install_repo_hook(hook_type: str) -> None:
    hooks_dir = _get_repo_hooks_dir()
    hook_path = hooks_dir / hook_type
    hook_scripts = _generate_hook_scripts()
    hook_path.write_text(hook_scripts[hook_type], encoding="utf-8")
    hook_path.chmod(0o755)
    console.print(f"[green]Installed {hook_type} hook in current repo.[/]")


def _uninstall_repo_hook(hook_type: str) -> None:
    hooks_dir = _get_repo_hooks_dir()
    hook_path = hooks_dir / hook_type
    if hook_path.exists():
        hook_path.unlink()
        console.print(f"[green]Removed {hook_type} hook.[/]")
    else:
        console.print(f"[dim]{hook_type} hook is not installed.[/]")


def _get_repo_hooks_dir() -> Path:
    try:
        from .git import _run_git
        git_dir = _run_git("rev-parse", "--git-dir").strip()
        hooks_dir = Path(git_dir) / "hooks"
        hooks_dir.mkdir(exist_ok=True)
        return hooks_dir
    except (subprocess.CalledProcessError, OSError, GitError):
        console.print("[bold red]Not in a git repository.[/]")
        sys.exit(1)
