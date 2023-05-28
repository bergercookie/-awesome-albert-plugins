"""TL;DR pages from albert."""

import re
import subprocess
import traceback
from pathlib import Path
from typing import Dict, Optional, Tuple

from fuzzywuzzy import process

import albert as v0

md_name = "TL;DR pages from albert."
md_description = "View tldr pages from inside albert"
md_iid = "0.5"
md_version = "0.2"
md_maintainers = "Nikos Koukis"
md_url = (
    "https://github.com/bergercookie/awesome-albert-plugins/blob/master/plugins//tldr_pages"
)

icon_path = str(Path(__file__).parent / "tldr_pages")

cache_path = Path(v0.cacheLocation()) / "tldr_pages"
config_path = Path(v0.configLocation()) / "tldr_pages"
data_path = Path(v0.dataLocation()) / "tldr_pages"

tldr_root = cache_path / "tldr"
pages_root = tldr_root / "pages"

page_paths: Dict[str, Path] = {}

# Is the plugin run in development mode?
in_development = False

# plugin main functions -----------------------------------------------------------------------


def reindex_tldr_pages():
    global page_paths
    page_paths = get_page_paths()


# supplementary functions ---------------------------------------------------------------------


def update_tldr_db():
    subprocess.check_call(f"git -C {tldr_root} pull --rebase origin master".split())
    reindex_tldr_pages()


def get_page_paths() -> Dict[str, Path]:
    global page_paths
    paths = list(pages_root.rglob("*.md"))

    return {p.stem: p for p in paths}


def get_cmd_as_item(query, pair: Tuple[str, Path]):
    with open(pair[-1], "r") as f:
        all_lines = f.readlines()
        description_lines = [
            li.lstrip("> ").rstrip().rstrip(".") for li in all_lines if li.startswith("> ")
        ]

        # see if there's a line with more information and a URL
        more_info_url = None
        try:
            more_info = [li for li in all_lines if "more information" in li.lower()][0]
            more_info_url = re.search("<(.*)>", more_info)
            if more_info_url is not None and more_info_url.groups():
                more_info_url = more_info_url.groups()[0]
        except IndexError:
            pass

    actions = [
        ClipAction("Copy command", pair[0]),
        UrlAction(
            "Do a google search", f'https://www.google.com/search?q="{pair[0]}" command'
        ),
    ]
    if more_info_url:
        actions.append(UrlAction("More information", more_info_url))

    return v0.Item(
        id=md_name,
        icon=[icon_path],
        text=pair[0],
        completion=" ".join([query.trigger, pair[0]]),
        subtext=" ".join(description_lines),
        actions=actions,
    )


def get_cmd_sanitized(s: str) -> str:
    return sanitize_string(s.strip("`").replace("{{", "").replace("}}", ""))


def get_cmd_items(pair: Tuple[str, Path]):
    """Return a list of Albert items - one per example."""

    with open(pair[-1], "r") as f:
        lines = [li.strip() for li in f.readlines()]

    items = []
    i = 0
    if len(lines) < 2:
        return items

    while i < len(lines):
        li = lines[i]
        if not li.startswith("- "):
            i += 1
            continue

        desc = li.lstrip("- ")[:-1]

        # Support multine commands ------------------------------------------------------------
        #
        # find the start of the example - parse it differently if it's a single quote or if
        # it's a multiline one
        i += 2
        example_line_start = lines[i]
        if example_line_start.startswith("```"):
            # multi-line string, find end
            j = i + 1
            while j < len(lines) and lines[j] != "```":
                j += 1
                continue

            example_cmd = get_cmd_sanitized("\n".join(lines[i + 1 : j]))
            i = j
        else:
            example_cmd = get_cmd_sanitized(lines[i])

        items.append(
            v0.Item(
                id=md_name,
                icon=[icon_path],
                text=example_cmd,
                subtext=desc,
                actions=[
                    ClipAction("Copy command", example_cmd),
                    UrlAction(
                        "Do a google search",
                        f'https://www.google.com/search?q="{pair[0]}" command',
                    ),
                ],
            )
        )

        i += 1

    return items


def sanitize_string(s: str) -> str:
    return s.replace("<", "&lt;")


def save_data(data: str, data_name: str):
    """Save a piece of data in the configuration directory."""
    with open(config_path / data_name, "w") as f:
        f.write(data)


def load_data(data_name) -> str:
    """Load a piece of data from the configuration directory."""
    with open(config_path / data_name, "r") as f:
        data = f.readline().strip().split()[0]

    return data


# helpers for backwards compatibility ------------------------------------------
class UrlAction(v0.Action):
    def __init__(self, name: str, url: str):
        super().__init__(name, name, lambda: v0.openUrl(url))


class ClipAction(v0.Action):
    def __init__(self, name, copy_text):
        super().__init__(name, name, lambda: v0.setClipboardText(copy_text))


class FuncAction(v0.Action):
    def __init__(self, name, command):
        super().__init__(name, name, command)


# main plugin class ------------------------------------------------------------
class Plugin(v0.QueryHandler):
    def id(self) -> str:
        return __name__

    def name(self) -> str:
        return md_name

    def description(self):
        return md_description

    def defaultTrigger(self):
        return "tldr "

    def synopsis(self):
        return "some command"

    def finalize(self):
        pass

    def initialize(self):
        # Called when the extension is loaded (ticked in the settings) - blocking
        global page_paths

        # create plugin locations
        for p in (cache_path, config_path, data_path):
            p.mkdir(parents=False, exist_ok=True)

        if not pages_root.is_dir():
            subprocess.check_call(
                f"git clone https://github.com/tldr-pages/tldr {tldr_root}".split()
            )

        reindex_tldr_pages()

    def handleQuery(self, query) -> None:
        results = []
        try:
            query_text = query.string.strip()

            if not len(query_text):
                results = [
                    v0.Item(
                        id=md_name,
                        icon=[icon_path],
                        text="Update tldr database",
                        actions=[FuncAction("Update", lambda: update_tldr_db())],
                    ),
                    v0.Item(
                        id=md_name,
                        icon=[icon_path],
                        text="Reindex tldr pages",
                        actions=[FuncAction("Reindex", lambda: reindex_tldr_pages())],
                    ),
                    v0.Item(
                        id=md_name,
                        icon=[icon_path],
                        text="Need at least 1 letter to offer suggestions",
                        actions=[],
                    ),
                ]

                query.add(results)
                return

            if query_text in page_paths.keys():
                # exact match - show examples
                results.extend(get_cmd_items((query_text, page_paths[query_text])))
            else:
                # fuzzy search based on word
                matched = process.extract(query_text, page_paths.keys(), limit=20)

                for m in [elem[0] for elem in matched]:
                    results.append(get_cmd_as_item(query, (m, page_paths[m])))

        except Exception:  # user to report error
            v0.critical(traceback.format_exc())
            if in_development:
                raise

            results.insert(
                0,
                v0.Item(
                    id=md_name,
                    icon=[icon_path],
                    text="Something went wrong! Press [ENTER] to copy error and report it",
                    actions=[
                        ClipAction(
                            f"Copy error - report it to {md_url[8:]}",
                            f"{traceback.format_exc()}",
                        )
                    ],
                ),
            )

        query.add(results)
