"""Goals 8 and 10: dashboard numbers and understaffed alerts. NOW is Wed 4 Nov 2026 12:00."""
from datetime import datetime, timedelta

from app import clock


def alerts(client, who):
    return client.get("/api/alerts", headers=who).json()


def test_shift_inside_three_days_and_not_full_is_an_alert(client, world, make_shift):
    c = world.auth(world.coord)
    make_shift(day="2026-11-04")                        # today
    make_shift(day="2026-11-07", start="10:00")         # exactly 3 days away: counts
    make_shift(day="2026-11-08", start="11:00")         # 4 days away: too far
    make_shift(day="2026-11-03", start="12:00")         # yesterday: not upcoming
    got = alerts(client, c)
    assert got["count"] == 2
    assert [a["date"] for a in got["items"]] == ["2026-11-04", "2026-11-07"]


def test_filled_and_closed_shifts_are_not_alerts(client, world, make_shift):
    shift = make_shift(day="2026-11-05", headcount=1)
    assert alerts(client, world.auth(world.coord))["count"] == 1
    client.post(f"/api/shifts/{shift['id']}/signups", headers=world.auth(world.vols[0]), json={})
    assert alerts(client, world.auth(world.coord))["count"] == 0


def test_partially_filled_still_counts(client, world, make_shift):
    shift = make_shift(day="2026-11-05", headcount=2)
    client.post(f"/api/shifts/{shift['id']}/signups", headers=world.auth(world.vols[0]), json={})
    assert alerts(client, world.auth(world.coord))["items"][0]["state"] == "partially_filled"


def test_dismiss_hides_from_badge_and_cancellation_from_filled_brings_it_back(client, world, make_shift):
    c = world.auth(world.coord)
    shift = make_shift(day="2026-11-05", headcount=1)
    assert client.post(f"/api/alerts/{shift['id']}/dismiss", headers=c).json()["count"] == 0
    assert alerts(client, c)["items"][0]["dismissed"] is True

    # still short-staffed after dismissal: a signup that does not fill it keeps it dismissed
    assert alerts(client, c)["count"] == 0
    signup = client.post(f"/api/shifts/{shift['id']}/signups", headers=world.auth(world.vols[0]), json={}).json()
    assert alerts(client, c)["items"] == []  # Filled: no alert at all

    client.delete(f"/api/signups/{signup['signups'][0]['id']}", headers=world.auth(world.vols[0]))
    back = alerts(client, c)
    assert back["count"] == 1 and back["items"][0]["dismissed"] is False


def test_dismissal_survives_a_signup_that_stays_understaffed(client, world, make_shift):
    c = world.auth(world.coord)
    shift = make_shift(day="2026-11-05", headcount=3)
    client.post(f"/api/alerts/{shift['id']}/dismiss", headers=c)
    client.post(f"/api/shifts/{shift['id']}/signups", headers=world.auth(world.vols[0]), json={})
    assert alerts(client, c)["count"] == 0  # Open -> Partially Filled is not a drop from Filled


def test_cancelling_a_filled_shift_beyond_three_days_creates_no_alert(client, world, make_shift):
    shift = make_shift(day="2026-11-20", headcount=1)
    signup = client.post(f"/api/shifts/{shift['id']}/signups", headers=world.auth(world.vols[0]), json={}).json()
    client.delete(f"/api/signups/{signup['signups'][0]['id']}", headers=world.auth(world.coord))
    assert alerts(client, world.auth(world.coord))["count"] == 0


def test_cannot_dismiss_a_shift_that_is_not_an_alert(client, world, make_shift):
    far = make_shift(day="2026-11-25")
    r = client.post(f"/api/alerts/{far['id']}/dismiss", headers=world.auth(world.coord))
    assert r.status_code == 409


def test_volunteers_see_alerts_for_their_programs_only(client, world, make_shift):
    mine = make_shift(day="2026-11-05")
    elsewhere = world.make_program("Elsewhere", members=[world.vols[1]])
    make_shift(day="2026-11-05", start="15:00", program_id=elsewhere)
    got = alerts(client, world.auth(world.vols[0]))
    assert [a["id"] for a in got["items"]] == [mine["id"]]


def test_dashboard_headline_numbers(client, world, make_shift):
    c = world.auth(world.coord)
    # this week is Mon 2 Nov .. Sun 8 Nov
    open_one = make_shift(day="2026-11-06", headcount=2)
    full_one = make_shift(day="2026-11-05", headcount=1)
    past_one = make_shift(day="2026-11-02", headcount=2)
    make_shift(day="2026-11-12")  # next week
    client.post(f"/api/shifts/{full_one['id']}/signups", headers=world.auth(world.vols[0]), json={})
    client.post(f"/api/shifts/{past_one['id']}/signups", headers=world.auth(world.vols[1]), json={})
    client.post(f"/api/shifts/{past_one['id']}/close", headers=c)

    d = client.get("/api/dashboard", headers=c).json()
    assert d["shifts_this_week"] == 3
    assert d["open_shifts_this_week"] == 1  # only open_one is entirely unstaffed
    assert d["signups_this_week"] == 2
    assert d["shifts_closed_this_week"] == 1
    assert d["by_state"] == {"open": 2, "partially_filled": 0, "filled": 1, "closed": 1}
    row = d["by_program"][0]
    assert row["program_name"] == "Food Pantry" and row["total"] == 4 and row["closed"] == 1
    assert open_one["id"]


def test_dashboard_signups_per_week_covers_eight_weeks(client, world, make_shift):
    shift = make_shift(day="2026-11-10", headcount=5)
    now = datetime(2026, 11, 4, 12, 0)
    for weeks_ago, vol in ((0, world.vols[0]), (1, world.vols[1]), (7, world.vols[2])):
        clock.set_override(now - timedelta(weeks=weeks_ago))
        client.post(f"/api/shifts/{shift['id']}/signups", headers=world.auth(vol), json={})
    clock.set_override(now)
    weekly = client.get("/api/dashboard", headers=world.auth(world.coord)).json()["signups_per_week"]
    assert len(weekly) == 8
    assert weekly[-1]["week_start"] == "2026-11-02" and weekly[0]["week_start"] == "2026-09-14"
    assert [w["signups"] for w in weekly] == [1, 0, 0, 0, 0, 0, 1, 1]


def test_dashboard_for_volunteers_is_scoped_to_their_programs(client, world, make_shift):
    make_shift(day="2026-11-06")
    other = world.make_program("Elsewhere", members=[world.vols[1]])
    make_shift(day="2026-11-06", start="15:00", program_id=other)
    mine = client.get("/api/dashboard", headers=world.auth(world.vols[0])).json()
    assert mine["shifts_this_week"] == 1 and [p["program_name"] for p in mine["by_program"]] == ["Food Pantry"]
    assert client.get("/api/dashboard", headers=world.auth(world.coord)).json()["shifts_this_week"] == 2
