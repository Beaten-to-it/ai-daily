from pathlib import Path
import shutil

import pytest

from nbs import assemble, config, publish


def test_home_only_lists_daily():
    text = (Path(config.ROOT) / "hugo.toml").read_text(encoding="utf-8")
    main_sections = text.split("mainSections", 1)[1].split("]", 1)[0]
    assert 'mainSections = ["daily"]' in text
    assert all(old not in main_sections for old in ('"news"', '"posts"', '"ax"', '"usecase"'))


def test_default_rss_template_filters_to_daily():
    text = (Path(config.ROOT) / "layouts" / "home.rss.xml").read_text(encoding="utf-8")
    assert 'where .Site.RegularPages "Section" "daily"' in text
    assert all(f'"{old}"' not in text for old in ("articles", "executive", "guides", "posts", "news"))


def test_real_hugo_renders_valid_daily_only_home_rss(tmp_path):
    if not shutil.which("hugo"):
        pytest.skip("Hugo is not installed")
    content = tmp_path / "content"
    for section in ("daily", "articles", "executive", "guides"):
        path = content / section / f"2026-08-02-{section}.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            f"---\ntitle: {section}\ndate: 2026-08-02\n---\n{section} body\n",
            encoding="utf-8",
        )
    output = tmp_path / "public"
    assert publish._hugo_build(str(output), content_dir=content) == 0
    feed = (output / "index.xml").read_text(encoding="utf-8")
    targets = publish._rss_item_targets(feed)
    assert any("/daily/2026-08-02-daily/" in target for target in targets)
    assert all("/daily/" in target for target in targets)


def test_new_content_sections_have_separate_menus():
    text = (Path(config.ROOT) / "hugo.toml").read_text(encoding="utf-8")
    for name, route in (("Daily", "daily"), ("Articles", "articles"),
                        ("Executive", "executive"), ("Guides", "guides"),
                        ("Tags", "tags")):
        assert f'name = "{name}"' in text
        assert f'url = "{route}/"' in text


def test_volume_status_boundaries():
    assert {count: assemble.volume_status(count) for count in (0, 1, 9, 10, 30)} == {
        0: "empty", 1: "warning", 9: "warning", 10: "normal", 30: "normal"
    }
