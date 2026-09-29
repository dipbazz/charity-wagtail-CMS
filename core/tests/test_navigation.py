import pytest

from home.models import StandardPage

pytestmark = pytest.mark.django_db


def add_page(parent, title, show_in_menus=True, live=True):
    page = StandardPage(title=title, show_in_menus=show_in_menus, live=live)
    parent.add_child(instance=page)
    return page


def menu_html(client, path="/"):
    html = client.get(path).content.decode()
    start = html.index('<nav class="main-nav"')
    return html[start : html.index("</nav>", start)]


def test_main_menu_lists_live_top_level_pages_marked_show_in_menus(client, home_page):
    add_page(home_page, "About us")
    add_page(home_page, "Our work")
    add_page(home_page, "Privacy policy", show_in_menus=False)
    add_page(home_page, "Draft page", live=False)

    menu = menu_html(client)

    assert "About us" in menu
    assert "Our work" in menu
    assert "Privacy policy" not in menu
    assert "Draft page" not in menu


def test_main_menu_marks_the_current_page(client, home_page):
    about = add_page(home_page, "About us")

    menu = menu_html(client, about.url)

    assert f'<a href="{about.url}" aria-current="page">About us</a>' in menu


def test_main_menu_marks_the_section_containing_the_current_page(client, home_page):
    about = add_page(home_page, "About us")
    team = add_page(about, "Our team", show_in_menus=False)
    work = add_page(home_page, "Our work")

    menu = menu_html(client, team.url)

    assert f'<a href="{about.url}" aria-current="true">About us</a>' in menu
    assert f'<a href="{work.url}">Our work</a>' in menu
